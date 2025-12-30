"""
Beat and visual flash detector for animals_1.mp4-like videos.

Usage examples:
  python analyze_beats.py animals_1.mp4 --csv beats.csv
  python analyze_beats.py animals_1.mp4 --grid 4x2 --visual-thresh 18

Outputs a CSV with timestamp_ms,event,detail rows combining audio onsets,
green-flash events on 8 tiles, and shuffle spikes.
"""

from __future__ import annotations

import argparse
import csv
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import List, Sequence, Tuple, Optional

import cv2
import numpy as np
import librosa


@dataclass
class VisualEvent:
    ts_ms: float
    label: str
    detail: str


def extract_audio(input_path: Path, tmpdir: Path) -> Path:
    """Dump audio track to a wav file using ffmpeg."""
    wav_path = tmpdir / "audio.wav"
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(input_path),
        "-vn",
        "-acodec",
        "pcm_s16le",
        str(wav_path),
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.decode("utf-8", errors="ignore"))
    return wav_path


def detect_audio_onsets(wav_path: Path, hop_length: int = 256) -> List[float]:
    """Return onset times in milliseconds derived from audio energy peaks."""
    y, sr = librosa.load(wav_path, sr=22050, mono=True)
    onsets = librosa.onset.onset_detect(
        y=y, sr=sr, hop_length=hop_length, backtrack=True, units="time"
    )
    return [float(t * 1000.0) for t in onsets]


def _build_grid(width: int, height: int, cols: int, rows: int, pad: float) -> List[Tuple[int, int, int, int]]:
    """Fallback grid when contour-based detection fails."""
    boxes = []
    cell_w = width / cols
    cell_h = height / rows
    for r in range(rows):
        for c in range(cols):
            x1 = int(c * cell_w + pad * cell_w)
            y1 = int(r * cell_h + pad * cell_h)
            x2 = int((c + 1) * cell_w - pad * cell_w)
            y2 = int((r + 1) * cell_h - pad * cell_h)
            boxes.append((x1, y1, x2 - x1, y2 - y1))  # x, y, w, h
    return boxes


def _find_tiles(video_path: Path, max_probe: int = 220) -> Optional[List[Tuple[int, int, int, int]]]:
    """Locate 8 dark-bordered tiles via contouring early frames."""
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return None
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    x0, x1 = int(0.08 * width), int(0.92 * width)
    y0, y1 = int(0.18 * height), int(0.82 * height)
    rects: Optional[List[Tuple[int, int, int, int]]] = None

    for _ in range(max_probe):
        ok, frame = cap.read()
        if not ok:
            break
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        crop = gray[y0:y1, x0:x1]
        mask = (crop < 60).astype(np.uint8) * 255
        cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cand = []
        for c in cnts:
            x, y, w, h = cv2.boundingRect(c)
            area = w * h
            if area < 4000:
                continue
            cand.append((x + x0, y + y0, w, h))
        if len(cand) >= 8:
            cand = sorted(cand, key=lambda r: (r[1], r[0]))[:8]
            rects = cand
            break

    cap.release()
    return rects


def _laplacian_energy(gray: np.ndarray, rect: Tuple[int, int, int, int], strip: int = 4) -> float:
    x, y, w, h = rect
    x1, y1 = x + w, y + h
    roi = gray[y + strip : y1 - strip, x + strip : x1 - strip]
    if roi.size == 0:
        return 0.0
    return float(cv2.Laplacian(roi, cv2.CV_32F).var())


def _border_green(frame: np.ndarray, rect: Tuple[int, int, int, int], strip: int = 6, g_thr: int = 120, diff: int = 50) -> int:
    x, y, w, h = rect
    x1, y1 = x + w, y + h
    b, g, r = cv2.split(frame)
    g = g.astype(np.int16)
    r = r.astype(np.int16)
    b = b.astype(np.int16)
    mask = (g > g_thr) & ((g - r) > diff) & ((g - b) > diff)
    top = mask[y : y + strip, x:x1].sum()
    bottom = mask[y1 - strip : y1, x:x1].sum()
    left = mask[y:y1, x : x + strip].sum()
    right = mask[y:y1, x1 - strip : x1].sum()
    return int(top + bottom + left + right)


def _mad(arr: np.ndarray) -> float:
    med = np.median(arr)
    return float(np.median(np.abs(arr - med))) or 1.0


def detect_round_events(
    video_path: Path,
    expect_rounds: int = 5,
    cluster_gap_ms: float = 1200.0,
    green_k: float = 3.5,
    appear_k: float = 3.5,
    shuffle_k: float = 3.5,
    appear_diff_k: float = 4.0,
    appear_min_ms: float = 0.0,
    force_shuffle: bool = True,
) -> Tuple[List[VisualEvent], float]:
    """
    Vision-only detector tuned to produce 8 appear + 8 green + (1+8)*(expect_rounds-1) events.
    """
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {video_path}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    rects = _find_tiles(video_path)
    if rects is None:
        rects = _build_grid(width, height, cols=4, rows=2, pad=0.1)

    union_x0 = min(r[0] for r in rects)
    union_y0 = min(r[1] for r in rects)
    union_x1 = max(r[0] + r[2] for r in rects)
    union_y1 = max(r[1] + r[3] for r in rects)

    green_sig: List[List[int]] = [[] for _ in rects]
    tile_diffs: List[List[float]] = [[] for _ in rects]
    diffs: List[float] = []

    ok, prev = cap.read()
    if not ok:
        cap.release()
        raise RuntimeError("Cannot read first frame")
    prev_gray = cv2.cvtColor(prev, cv2.COLOR_BGR2GRAY)

    while True:
        frame = prev
        for i, rect in enumerate(rects):
            green_sig[i].append(_border_green(frame, rect))

        ok, nxt = cap.read()
        if not ok:
            break
        nxt_gray = cv2.cvtColor(nxt, cv2.COLOR_BGR2GRAY)

        for i, (x, y, w, h) in enumerate(rects):
            roi_prev = prev_gray[y : y + h, x : x + w]
            roi_next = nxt_gray[y : y + h, x : x + w]
            tile_diffs[i].append(float(np.mean(cv2.absdiff(roi_prev, roi_next))))

        diff_val = float(
            np.mean(cv2.absdiff(prev_gray[union_y0:union_y1, union_x0:union_x1], nxt_gray[union_y0:union_y1, union_x0:union_x1]))
        )
        diffs.append(diff_val)

        prev = nxt
        prev_gray = nxt_gray

    cap.release()

    events: List[VisualEvent] = []

    # Green: rising edges per tile
    min_gap_frames = int(fps * 0.4)
    green_events: List[Tuple[int, int]] = []  # (frame, tile)
    for i, series in enumerate(green_sig):
        arr = np.array(series, dtype=np.float32)
        if arr.size == 0:
            continue
        base = np.median(arr)
        thr = max(base + green_k * _mad(arr), np.percentile(arr, 92))
        last_fire = -10_000
        for f in range(1, len(arr)):
            if arr[f] > thr and arr[f - 1] <= thr and (f - last_fire) >= min_gap_frames:
                green_events.append((f, i))
                last_fire = f

    # Appear: look for first strong diff before the first green event
    first_green_frame = green_events[0][0] if green_events else len(tile_diffs[0]) if tile_diffs and tile_diffs[0] else 0
    for i, series in enumerate(tile_diffs):
        arr = np.array(series, dtype=np.float32)
        if arr.size == 0:
            continue
        search_upto = min(len(arr), first_green_frame) if first_green_frame > 0 else len(arr)
        if search_upto < 5:
            continue
        window = arr[:search_upto]
        thr = max(np.percentile(window, 97), np.median(window) + appear_diff_k * _mad(window))
        idxs = np.where(window >= thr)[0]
        if idxs.size:
            # pick first peak occurring after appear_min_ms
            for idx in idxs:
                ts_ms = (idx + 1) * 1000.0 / fps
                if ts_ms >= appear_min_ms:
                    events.append(VisualEvent(ts_ms=ts_ms, label=f"cell_{i}", detail="appear"))
                    break

    # Cluster green events into rounds
    green_events.sort(key=lambda x: x[0])
    clusters: List[List[Tuple[int, int]]] = []
    for f, tile in green_events:
        if not clusters:
            clusters.append([(f, tile)])
            continue
        last_f = clusters[-1][-1][0]
        if (f - last_f) * 1000.0 / fps <= cluster_gap_ms:
            clusters[-1].append((f, tile))
        else:
            clusters.append([(f, tile)])
    clusters = clusters[:expect_rounds]

    for round_idx, cluster in enumerate(clusters):
        seen = set()
        for f, tile in cluster:
            if tile in seen:
                continue
            seen.add(tile)
            ts_ms = f * 1000.0 / fps
            events.append(VisualEvent(ts_ms=ts_ms, label=f"cell_{tile}", detail=f"green_round{round_idx+1}"))

    # Shuffle: pick the strongest diff peak between green clusters
    if diffs and clusters:
        diff_arr = np.array(diffs, dtype=np.float32)
        base = np.median(diff_arr)
        thr = base + shuffle_k * _mad(diff_arr)
        for idx in range(len(clusters) - 1):
            start_f = clusters[idx][-1][0] + 1
            end_f = clusters[idx + 1][0][0] - 1
            if end_f <= start_f:
                continue
            window = diff_arr[start_f:end_f]
            if window.size == 0:
                continue
            peak_rel = int(np.argmax(window))
            peak_val = float(window[peak_rel])
            peak_f = start_f + peak_rel
            if peak_val > thr or force_shuffle:
                ts_ms = (peak_f + 1) * 1000.0 / fps
                detail = f"shuffle_round{idx+2}"
                if peak_val <= thr:
                    detail += "_lowconf"
                events.append(VisualEvent(ts_ms=ts_ms, label="layout", detail=detail))

    events.sort(key=lambda e: e.ts_ms)
    return events, fps


def merge_events(audio_ms: Sequence[float], visuals: Sequence[VisualEvent], tolerance_ms: float = 120.0) -> List[Tuple[float, str, str]]:
    """Join audio onsets to nearest visual event within tolerance."""
    output: List[Tuple[float, str, str]] = []
    vis_ts = np.array([v.ts_ms for v in visuals]) if visuals else np.array([])

    for a_ms in audio_ms:
        if vis_ts.size:
            idx = int(np.argmin(np.abs(vis_ts - a_ms)))
            delta = abs(vis_ts[idx] - a_ms)
            if delta <= tolerance_ms:
                v = visuals[idx]
                output.append((a_ms, "audio+visual", f"{v.label}:{v.detail}"))
                continue
        output.append((a_ms, "audio_only", "onset"))

    for v in visuals:
        if not vis_ts.size:
            output.append((v.ts_ms, v.label, v.detail))
            continue
        nearest = float(np.min(np.abs(np.array(audio_ms) - v.ts_ms))) if audio_ms else float("inf")
        if nearest > tolerance_ms:
            output.append((v.ts_ms, v.label, v.detail))

    output.sort(key=lambda x: x[0])
    return output


def write_csv(rows: Sequence[Tuple[float, str, str]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp_ms", "event", "detail"])
        for ts, ev, detail in rows:
            writer.writerow([f"{ts:.1f}", ev, detail])


def _windows_from_events(events: Sequence[Tuple[float, str, str]], flash_ms: float) -> List[Tuple[float, float]]:
    half = flash_ms / 2.0
    return [(ts - half, ts + half) for ts, _, _ in events]


def render_flashes(
    video_path: Path,
    events: Sequence[Tuple[float, str, str]],
    out_path: Path,
    flash_ms: float = 120.0,
    border_px: int = 12,
    border_color=(0, 0, 255),
    copy_audio: bool = True,
) -> None:
    """Render a red border flash around each detected event and export a new video."""
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_no_audio = out_path.parent / f"{out_path.stem}_noaudio.mp4"
    out = cv2.VideoWriter(str(tmp_no_audio), fourcc, fps, (width, height))

    windows = _windows_from_events(events, flash_ms)
    windows.sort(key=lambda w: w[0])
    w_idx = 0

    frame_idx = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        ts_ms = (frame_idx / fps) * 1000.0

        while w_idx + 1 < len(windows) and ts_ms > windows[w_idx][1]:
            w_idx += 1

        flash = False
        if windows:
            start, end = windows[w_idx]
            if start <= ts_ms <= end:
                flash = True

        if flash:
            cv2.rectangle(frame, (0, 0), (width - 1, height - 1), border_color, border_px)

        out.write(frame)
        frame_idx += 1

    cap.release()
    out.release()

    # Re-encode to H.264 for wide compatibility (yuv420p)
    def _transcode(cmd: list) -> bool:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return res.returncode == 0

    if copy_audio:
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(tmp_no_audio),
            "-i",
            str(video_path),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            "-c:a",
            "copy",
            "-movflags",
            "+faststart",
            "-shortest",
            str(out_path),
        ]
        ok = _transcode(cmd)
        if not ok:
            # fallback: video only
            fallback = [
                "ffmpeg",
                "-y",
                "-i",
                str(tmp_no_audio),
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-preset",
                "veryfast",
                "-crf",
                "23",
                "-an",
                str(out_path),
            ]
            _transcode(fallback)
    else:
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(tmp_no_audio),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            "-an",
            str(out_path),
        ]
        _transcode(cmd)

    tmp_no_audio.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Detect beats and flashes in a video.")
    parser.add_argument("video", type=Path, help="Input video path")
    parser.add_argument("--csv", type=Path, default=Path("beats.csv"), help="Output CSV path")
    parser.add_argument("--grid", default="4x2", help="(legacy) grid hint, kept for compatibility")
    parser.add_argument("--visual-thresh", type=float, default=18.0, help="(legacy) unused")
    parser.add_argument("--shuffle-sigma", type=float, default=2.5, help="(legacy) unused")
    parser.add_argument("--merge-window", type=float, default=120.0, help="(legacy) unused")
    parser.add_argument("--expect-rounds", type=int, default=5, help="Total rounds of green (incl. round 1)")
    parser.add_argument("--cluster-gap-ms", type=float, default=1200.0, help="Gap between green clusters to start new round")
    parser.add_argument("--green-k", type=float, default=3.5, help="MAD multiplier for green detection")
    parser.add_argument("--appear-k", type=float, default=3.0, help="MAD multiplier for appear detection")
    parser.add_argument("--shuffle-k", type=float, default=3.0, help="MAD multiplier for shuffle detection")
    parser.add_argument("--appear-min-ms", type=float, default=2000.0, help="Ignore appear events earlier than this (ms)")
    parser.add_argument("--no-force-shuffle", action="store_true", help="Do not force a shuffle between rounds when below threshold")
    parser.add_argument(
        "--render-video",
        nargs="?",
        const="AUTO",
        type=str,
        help="Export highlighted video. If no path given, saves alongside input as <name>_highlight.mp4",
    )
    parser.add_argument("--flash-ms", type=float, default=200.0, help="Flash duration (ms) per event")
    parser.add_argument("--border-px", type=int, default=20, help="Border thickness for flashes")
    parser.add_argument("--no-audio", action="store_true", help="Do not copy source audio into render")
    args = parser.parse_args()

    video_path = args.video
    if not video_path.exists():
        raise SystemExit(f"Video not found: {video_path}")

    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        events, fps = detect_round_events(
            video_path=video_path,
            expect_rounds=args.expect_rounds,
            cluster_gap_ms=args.cluster_gap_ms,
            green_k=args.green_k,
            appear_k=args.appear_k,
            shuffle_k=args.shuffle_k,
            appear_min_ms=args.appear_min_ms,
            force_shuffle=not args.no_force_shuffle,
        )
        merged = [(e.ts_ms, e.label, e.detail) for e in events]
        write_csv(merged, args.csv)
        if args.render_video:
            if args.render_video == "AUTO":
                out_path = video_path.with_name(f"{video_path.stem}_highlight.mp4")
            else:
                out_path = Path(args.render_video)
            render_flashes(
                video_path=video_path,
                events=merged,
                out_path=out_path,
                flash_ms=args.flash_ms,
                border_px=args.border_px,
                copy_audio=not args.no_audio,
            )

    msg = f"Found {len(merged)} events; fps={fps:.3f}; saved to {args.csv}"
    if args.render_video:
        if args.render_video == "AUTO":
            msg += f"; rendered {video_path.with_name(f'{video_path.stem}_highlight.mp4')}"
        else:
            msg += f"; rendered {args.render_video}"
    print(msg)


if __name__ == "__main__":
    main()
