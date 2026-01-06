from __future__ import annotations

import subprocess
import shutil
import uuid
import zipfile
import re
import json
import gzip
from pathlib import Path
from typing import Optional

from flask import (
    Flask,
    abort,
    after_this_request,
    jsonify,
    render_template_string,
    request,
    send_file,
)
from werkzeug.exceptions import HTTPException

try:
    from lottie.exporters.gif import export_gif
    from lottie import objects
    HAS_LOTTIE = True
except ImportError:
    HAS_LOTTIE = False

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
OUTPUT_DIR = DATA_DIR / "converted"

for directory in (UPLOAD_DIR, OUTPUT_DIR):
    directory.mkdir(parents=True, exist_ok=True)

MIN_FPS = 1
MAX_FPS = 60
MAX_DURATION = 3600  # seconds
MAX_WEBP_DURATION = 3600  # seconds (for mp4 -> animated webp trim)

app = Flask(__name__)


# ---------------------------- Helpers -------------------------------------

def _validate_fps(raw_fps: Optional[str | int]) -> int:
    try:
        fps = int(raw_fps)
    except (TypeError, ValueError):
        abort(400, "FPS không hợp lệ")

    if not (MIN_FPS <= fps <= MAX_FPS):
        abort(400, f"FPS phải nằm trong khoảng {MIN_FPS}-{MAX_FPS}")
    return fps


def _validate_duration(raw: Optional[str | int]) -> int:
    try:
        val = int(raw)
    except (TypeError, ValueError):
        abort(400, "Thời lượng không hợp lệ")
    if not (1 <= val <= MAX_DURATION):
        abort(400, f"Thời lượng phải trong khoảng 1-{MAX_DURATION} giây")
    return val


def _safe_upload_path(filename: str, base: Path) -> Path:
    """Prevent path traversal by resolving the final location."""
    candidate = (base / filename).resolve()
    if base not in candidate.parents:
        abort(404)
    if not candidate.exists():
        abort(404)
    return candidate


def _validate_positive_int(
    raw: Optional[str | int],
    *,
    name: str,
    min_value: int,
    max_value: int,
) -> int:
    try:
        val = int(raw)
    except (TypeError, ValueError):
        abort(400, f"{name} không hợp lệ")
    if not (min_value <= val <= max_value):
        abort(400, f"{name} phải nằm trong khoảng {min_value}-{max_value}")
    return val


def _allowed_image_suffix(filename: str) -> str | None:
    suffix = (Path(filename).suffix or "").lower()
    if suffix in {".png", ".jpg", ".jpeg"}:
        return suffix
    return None


def _allowed_static_image_suffix(filename: str) -> str | None:
    suffix = (Path(filename).suffix or "").lower()
    if suffix in {".png", ".jpg", ".jpeg", ".webp"}:
        return suffix
    return None


def _allowed_gif_suffix(filename: str) -> str | None:
    suffix = (Path(filename).suffix or "").lower()
    if suffix == ".gif":
        return suffix
    return None


_ZIP_NAME_SAFE_RE = re.compile(r"[^a-zA-Z0-9._-]+")


def _safe_zip_entry_name(raw_stem: str, *, index: int) -> str:
    stem = (raw_stem or "").strip() or f"image_{index:04d}"
    stem = _ZIP_NAME_SAFE_RE.sub("_", stem).strip("._-") or f"image_{index:04d}"
    return f"{index:04d}_{stem}.webp"


def _safe_zip_entry_name_with_ext(raw_stem: str, *, index: int, ext: str) -> str:
    stem = (raw_stem or "").strip() or f"image_{index:04d}"
    stem = _ZIP_NAME_SAFE_RE.sub("_", stem).strip("._-") or f"image_{index:04d}"
    ext = (ext or "").lower().strip()
    if not ext.startswith("."):
        ext = f".{ext}"
    if ext not in {".webp", ".png", ".jpg"}:
        ext = ".png"
    return f"{index:04d}_{stem}{ext}"


def _parse_bool(raw: object | None) -> bool:
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _convert_image(
    input_path: Path,
    *,
    target: str,
    width: int | None = None,
    quality: int | None = None,
    lossless: bool = False,
    output_path: Path | None = None,
    target_size_kb: int | None = None,
) -> Path:
    target = (target or "").strip().lower()
    if target == "jpeg":
        target = "jpg"
    if target not in {"webp", "png", "jpg"}:
        abort(400, "Định dạng output không hợp lệ (format: webp/png/jpg)")

    if output_path is None:
        output_path = OUTPUT_DIR / f"{uuid.uuid4().hex}.{target}"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    vf_parts: list[str] = []
    if width is not None:
        vf_parts.append(f"scale={width}:-1:flags=lanczos")
    vf = ",".join(vf_parts) if vf_parts else None

    # If target size is specified and format supports quality adjustment
    if target_size_kb is not None and target in {"webp", "jpg"}:
        # Try iteratively with decreasing quality
        best_quality = quality if quality is not None else 90
        min_quality = 10

        for q in range(best_quality, min_quality - 1, -5):
            cmd: list[str] = ["ffmpeg", "-y", "-i", str(input_path)]
            if vf:
                cmd += ["-vf", vf]

            if target == "webp":
                cmd += [
                    "-an",
                    "-c:v",
                    "libwebp",
                    "-compression_level",
                    "6",
                    "-lossless",
                    "0",
                    "-q:v",
                    str(q),
                ]
            else:  # jpg
                jpeg_q = int(round(31 - (max(1, min(100, q)) - 1) * (29 / 99)))
                jpeg_q = max(2, min(31, jpeg_q))
                cmd += ["-an", "-q:v", str(jpeg_q)]

            cmd.append(str(output_path))
            _run_ffmpeg(cmd)

            # Check file size
            file_size_kb = output_path.stat().st_size / 1024
            if file_size_kb <= target_size_kb or q <= min_quality:
                break

        return output_path

    # Standard conversion without size constraint
    cmd: list[str] = ["ffmpeg", "-y", "-i", str(input_path)]
    if vf:
        cmd += ["-vf", vf]

    if target == "webp":
        cmd += [
            "-an",
            "-c:v",
            "libwebp",
            "-compression_level",
            "6",
        ]
        if lossless:
            cmd += ["-lossless", "1"]
        else:
            q = 80 if quality is None else quality
            cmd += ["-lossless", "0", "-q:v", str(q)]
    elif target == "png":
        cmd += ["-an", "-c:v", "png"]
    else:  # jpg
        q = 85 if quality is None else quality
        # ffmpeg's JPEG quality scale is ~2(best)..31(worst). Map 1..100 -> 31..2.
        jpeg_q = int(round(31 - (max(1, min(100, q)) - 1) * (29 / 99)))
        jpeg_q = max(2, min(31, jpeg_q))
        cmd += ["-an", "-q:v", str(jpeg_q)]

    cmd.append(str(output_path))
    _run_ffmpeg(cmd)
    return output_path


def _convert_video(
    input_path: Path, fps: int, duration: int | None = None, loop: bool = False
) -> Path:
    output_path = OUTPUT_DIR / f"{uuid.uuid4().hex}.mp4"
    cmd = ["ffmpeg", "-y"]
    if loop and duration:
        cmd += ["-stream_loop", "-1"]  # loop source to satisfy target duration
    cmd += [
        "-i",
        str(input_path),
    ]
    if duration:
        cmd += ["-t", str(duration)]
    cmd += [
        "-filter:v",
        f"fps={fps}",
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-crf",
        "23",
        "-c:a",
        "copy",
        str(output_path),
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.decode("utf-8", errors="ignore"))
    return output_path


def _run_ffmpeg(cmd: list[str]) -> None:
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.decode("utf-8", errors="ignore"))


def _convert_image_to_webp(
    input_path: Path,
    *,
    lossless: bool,
    output_path: Path | None = None,
) -> Path:
    if output_path is None:
        output_path = OUTPUT_DIR / f"{uuid.uuid4().hex}.webp"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(input_path),
        "-c:v",
        "libwebp",
        "-compression_level",
        "6",
    ]
    if lossless:
        cmd += ["-lossless", "1"]
    else:
        cmd += ["-lossless", "0", "-q:v", "80"]
    cmd.append(str(output_path))
    _run_ffmpeg(cmd)
    return output_path


def _convert_images_to_animated_webp(
    frame_paths: list[Path],
    *,
    fps: int,
    width: int | None = None,
    loop: int = 0,
) -> Path:
    if not frame_paths:
        abort(400, "Thiếu ảnh")

    # Keep list file next to frames so rmtree() cleans everything.
    list_path = frame_paths[0].parent / f"{uuid.uuid4().hex}_frames.txt"
    output_path = OUTPUT_DIR / f"{uuid.uuid4().hex}.webp"
    frame_duration = 1.0 / float(fps)

    # Concat demuxer: add final file again (without duration) so the last frame is held.
    lines: list[str] = []
    for frame in frame_paths:
        lines.append(f"file '{frame.as_posix()}'")
        lines.append(f"duration {frame_duration:.6f}")
    if frame_paths:
        lines.append(f"file '{frame_paths[-1].as_posix()}'")

    list_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    vf_parts: list[str] = []
    if width is not None:
        vf_parts.append(f"scale={width}:-1:flags=lanczos")
    vf_parts.append("format=rgba")
    vf = ",".join(vf_parts)

    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(list_path),
        "-vsync",
        "vfr",
        "-vf",
        vf,
        "-an",
        "-loop",
        str(loop),
        "-c:v",
        "libwebp",
        "-preset",
        "default",
        "-q:v",
        "80",
        "-compression_level",
        "6",
        str(output_path),
    ]
    try:
        _run_ffmpeg(cmd)
    finally:
        list_path.unlink(missing_ok=True)
    return output_path


def _convert_video_to_animated_webp(
    input_path: Path,
    *,
    fps: int,
    width: int | None = None,
    duration: int | None = None,
    loop: int = 0,
) -> Path:
    output_path = OUTPUT_DIR / f"{uuid.uuid4().hex}.webp"

    vf_parts: list[str] = [f"fps={fps}"]
    if width is not None:
        vf_parts.append(f"scale={width}:-1:flags=lanczos")
    vf_parts.append("format=rgba")
    vf = ",".join(vf_parts)

    cmd: list[str] = ["ffmpeg", "-y", "-i", str(input_path)]
    if duration:
        cmd += ["-t", str(duration)]
    cmd += [
        "-vf",
        vf,
        "-an",
        "-loop",
        str(loop),
        "-c:v",
        "libwebp",
        "-preset",
        "default",
        "-q:v",
        "80",
        "-compression_level",
        "6",
        "-vsync",
        "0",
        str(output_path),
    ]
    _run_ffmpeg(cmd)
    return output_path


def _resize_animated_media(
    input_path: Path,
    *,
    width: int | None = None,
    height: int | None = None,
    quality: int | None = None,
    target_size_kb: int | None = None,
    output_path: Path | None = None,
) -> Path:
    """Resize animated WebP or GIF with optional size control."""
    suffix = input_path.suffix.lower()
    if suffix not in {".webp", ".gif"}:
        abort(400, "Chỉ hỗ trợ WebP hoặc GIF")

    if output_path is None:
        output_path = OUTPUT_DIR / f"{uuid.uuid4().hex}{suffix}"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Build scale filter
    vf_parts: list[str] = []
    if width is not None and height is not None:
        vf_parts.append(f"scale={width}:{height}:flags=lanczos")
    elif width is not None:
        vf_parts.append(f"scale={width}:-1:flags=lanczos")
    elif height is not None:
        vf_parts.append(f"scale=-1:{height}:flags=lanczos")

    # If target size is specified, try iteratively
    if target_size_kb is not None and suffix == ".webp":
        best_quality = quality if quality is not None else 90
        min_quality = 10

        for q in range(best_quality, min_quality - 1, -5):
            cmd: list[str] = ["ffmpeg", "-y", "-i", str(input_path)]

            if vf_parts:
                vf_parts_copy = vf_parts.copy()
                vf_parts_copy.append("format=rgba")
                cmd += ["-vf", ",".join(vf_parts_copy)]
            else:
                cmd += ["-vf", "format=rgba"]

            cmd += [
                "-an",
                "-c:v",
                "libwebp",
                "-preset",
                "default",
                "-q:v",
                str(q),
                "-compression_level",
                "6",
                "-loop",
                "0",
                str(output_path),
            ]
            _run_ffmpeg(cmd)

            # Check file size
            file_size_kb = output_path.stat().st_size / 1024
            if file_size_kb <= target_size_kb or q <= min_quality:
                break

        return output_path

    # Standard conversion without size constraint
    cmd: list[str] = ["ffmpeg", "-y", "-i", str(input_path)]

    if vf_parts:
        if suffix == ".webp":
            vf_parts.append("format=rgba")
        cmd += ["-vf", ",".join(vf_parts)]
    elif suffix == ".webp":
        cmd += ["-vf", "format=rgba"]

    if suffix == ".webp":
        q = 80 if quality is None else quality
        cmd += [
            "-an",
            "-c:v",
            "libwebp",
            "-preset",
            "default",
            "-q:v",
            str(q),
            "-compression_level",
            "6",
            "-loop",
            "0",
            str(output_path),
        ]
    else:  # gif
        cmd += ["-c:v", "gif", "-loop", "0", str(output_path)]

    _run_ffmpeg(cmd)
    return output_path


def _allowed_tgs_suffix(filename: str) -> bool:
    return Path(filename).suffix.lower() == ".tgs"


def _convert_tgs_to_gif(
    input_path: Path,
    *,
    width: int | None = None,
    quality: int | None = None,
    fps: int = 30,
    output_path: Path | None = None,
) -> Path:
    """Convert TGS (Telegram sticker) to GIF.

    TGS files are gzipped Lottie JSON animations.
    We decompress, load as Lottie, and export to GIF.
    """
    if not HAS_LOTTIE:
        abort(500, "Lottie library không được cài đặt. Cần cài đặt 'lottie'.")

    if output_path is None:
        output_path = OUTPUT_DIR / f"{uuid.uuid4().hex}.gif"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # TGS files are gzipped Lottie JSON
    try:
        with gzip.open(input_path, 'rb') as f:
            lottie_data = json.load(f)

        # Parse Lottie animation
        animation = objects.Animation.load(lottie_data)

        # Calculate dimensions
        if width:
            # Maintain aspect ratio
            aspect_ratio = animation.height / animation.width
            height = int(width * aspect_ratio)
        else:
            width = int(animation.width)
            height = int(animation.height)

        # Export to GIF
        export_gif(
            animation,
            str(output_path),
            width=width,
            height=height,
            quality=quality if quality else 80,
            fps=fps,
        )

        return output_path

    except Exception as e:
        abort(500, f"Lỗi chuyển đổi TGS sang GIF: {str(e)}")


# ---------------------------- Routes --------------------------------------

@app.get("/")
def index():
    return render_template_string(
        """
        <!doctype html>
        <html lang="vi">
        <head>
            <meta charset="UTF-8" />
            <meta name="viewport" content="width=device-width, initial-scale=1" />
            <title>🎬 Media Converter Pro</title>
            <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
            <style>
                * { box-sizing: border-box; }
                :root {
                    --bg-gradient-1: #0a0e27;
                    --bg-gradient-2: #1a1f3a;
                    --card-bg: rgba(17, 24, 39, 0.8);
                    --card-border: rgba(255, 255, 255, 0.08);
                    --primary: #3b82f6;
                    --primary-light: #60a5fa;
                    --secondary: #8b5cf6;
                    --accent: #10b981;
                    --accent-pink: #ec4899;
                    --text: #f1f5f9;
                    --text-muted: #94a3b8;
                    --text-dim: #64748b;
                    --input-bg: rgba(15, 23, 42, 0.6);
                    --input-border: rgba(148, 163, 184, 0.2);
                    --input-focus: rgba(59, 130, 246, 0.5);
                    --success: #10b981;
                    --warning: #f59e0b;
                    --error: #ef4444;
                }
                body {
                    margin: 0; padding: 20px 0;
                    font-family: 'Inter', -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
                    background: linear-gradient(135deg, var(--bg-gradient-1) 0%, var(--bg-gradient-2) 100%);
                    background-attachment: fixed;
                    color: var(--text);
                    min-height: 100vh;
                    line-height: 1.6;
                }
                body::before {
                    content: '';
                    position: fixed;
                    top: 0; left: 0; right: 0; bottom: 0;
                    background:
                        radial-gradient(circle at 20% 20%, rgba(59, 130, 246, 0.15), transparent 40%),
                        radial-gradient(circle at 80% 80%, rgba(139, 92, 246, 0.15), transparent 40%),
                        radial-gradient(circle at 50% 50%, rgba(236, 72, 153, 0.08), transparent 50%);
                    pointer-events: none;
                    z-index: 0;
                }
                .container {
                    max-width: 1400px;
                    margin: 0 auto;
                    padding: 0 20px;
                    position: relative;
                    z-index: 1;
                }
                .header {
                    text-align: center;
                    margin-bottom: 40px;
                    animation: fadeInDown 0.6s ease;
                }
                .header h1 {
                    margin: 0 0 12px;
                    font-size: 3rem;
                    font-weight: 800;
                    background: linear-gradient(135deg, #3b82f6, #8b5cf6, #ec4899);
                    -webkit-background-clip: text;
                    -webkit-text-fill-color: transparent;
                    background-clip: text;
                    letter-spacing: -0.02em;
                }
                .header p {
                    margin: 0;
                    color: var(--text-muted);
                    font-size: 1.1rem;
                }
                .card {
                    background: var(--card-bg);
                    backdrop-filter: blur(20px);
                    border: 1px solid var(--card-border);
                    border-radius: 24px;
                    padding: 32px;
                    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.4);
                    margin-bottom: 24px;
                    transition: transform 0.3s ease, box-shadow 0.3s ease;
                    animation: fadeInUp 0.6s ease;
                }
                .card:hover {
                    transform: translateY(-2px);
                    box-shadow: 0 24px 70px rgba(0, 0, 0, 0.5);
                }
                .tabs {
                    display: flex;
                    gap: 8px;
                    background: rgba(15, 23, 42, 0.6);
                    border: 1px solid var(--card-border);
                    padding: 6px;
                    border-radius: 16px;
                    margin-bottom: 32px;
                    overflow-x: auto;
                }
                .tab-btn {
                    padding: 12px 24px;
                    border-radius: 12px;
                    border: none;
                    background: transparent;
                    color: var(--text-muted);
                    font-weight: 600;
                    font-size: 0.95rem;
                    cursor: pointer;
                    transition: all 0.3s ease;
                    white-space: nowrap;
                    position: relative;
                    overflow: hidden;
                }
                .tab-btn::before {
                    content: '';
                    position: absolute;
                    top: 0; left: 0; right: 0; bottom: 0;
                    background: linear-gradient(135deg, var(--primary), var(--secondary));
                    opacity: 0;
                    transition: opacity 0.3s ease;
                }
                .tab-btn:hover { color: var(--text); }
                .tab-btn.active {
                    color: white;
                    background: linear-gradient(135deg, var(--primary), var(--secondary));
                    box-shadow: 0 4px 16px rgba(59, 130, 246, 0.4);
                }
                .grid { display: grid; grid-template-columns: 420px 1fr; gap: 24px; align-items: start; }
                .controls-panel {
                    background: rgba(15, 23, 42, 0.4);
                    border: 1px solid var(--card-border);
                    border-radius: 20px;
                    padding: 24px;
                    max-height: 80vh;
                    overflow-y: auto;
                    overflow-x: hidden;
                }
                .controls-panel::-webkit-scrollbar { width: 8px; }
                .controls-panel::-webkit-scrollbar-track { background: rgba(255,255,255,0.05); border-radius: 10px; }
                .controls-panel::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.15); border-radius: 10px; }
                .controls-panel::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,0.25); }
                .feature-card {
                    background: rgba(255, 255, 255, 0.02);
                    border: 1px solid rgba(255, 255, 255, 0.06);
                    border-radius: 16px;
                    padding: 20px;
                    margin-bottom: 16px;
                    transition: all 0.3s ease;
                }
                .feature-card:hover {
                    background: rgba(255, 255, 255, 0.04);
                    border-color: rgba(255, 255, 255, 0.12);
                    transform: translateX(4px);
                }
                .feature-title {
                    font-size: 0.9rem;
                    font-weight: 700;
                    color: var(--primary-light);
                    margin: 0 0 16px;
                    display: flex;
                    align-items: center;
                    gap: 8px;
                }
                .feature-title::before {
                    content: '✨';
                    font-size: 1.2rem;
                }
                label {
                    display: block;
                    font-weight: 600;
                    font-size: 0.875rem;
                    margin-bottom: 8px;
                    color: var(--text);
                }
                input[type=file] {
                    width: 100%;
                    padding: 12px 16px;
                    border-radius: 12px;
                    border: 2px dashed var(--input-border);
                    background: var(--input-bg);
                    color: var(--text);
                    font-size: 0.875rem;
                    cursor: pointer;
                    transition: all 0.3s ease;
                    position: relative;
                }
                input[type=file]:hover {
                    border-color: var(--primary);
                    background: rgba(59, 130, 246, 0.1);
                }
                input[type=file]:focus {
                    outline: none;
                    border-color: var(--primary);
                    box-shadow: 0 0 0 3px var(--input-focus);
                }
                /* Drag and drop styles */
                .drop-zone {
                    position: relative;
                    min-height: 120px;
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    justify-content: center;
                    padding: 24px;
                    border-radius: 12px;
                    border: 2px dashed var(--input-border);
                    background: var(--input-bg);
                    transition: all 0.3s ease;
                    cursor: pointer;
                }
                .drop-zone:hover {
                    border-color: var(--primary);
                    background: rgba(59, 130, 246, 0.1);
                }
                .drop-zone.drag-over {
                    border-color: var(--accent);
                    background: rgba(16, 185, 129, 0.15);
                    transform: scale(1.02);
                    box-shadow: 0 8px 24px rgba(16, 185, 129, 0.3);
                }
                .drop-zone-icon {
                    font-size: 3rem;
                    margin-bottom: 12px;
                    opacity: 0.6;
                }
                .drop-zone-text {
                    font-size: 0.95rem;
                    font-weight: 600;
                    color: var(--text);
                    margin-bottom: 4px;
                }
                .drop-zone-hint {
                    font-size: 0.8rem;
                    color: var(--text-dim);
                }
                .drop-zone input[type=file] {
                    position: absolute;
                    top: 0;
                    left: 0;
                    width: 100%;
                    height: 100%;
                    opacity: 0;
                    cursor: pointer;
                }
                .file-list {
                    margin-top: 12px;
                    padding: 12px;
                    background: rgba(255, 255, 255, 0.02);
                    border-radius: 8px;
                    border: 1px solid rgba(255, 255, 255, 0.06);
                }
                .file-item {
                    display: flex;
                    align-items: center;
                    gap: 8px;
                    padding: 8px;
                    background: rgba(255, 255, 255, 0.03);
                    border-radius: 6px;
                    margin-bottom: 6px;
                    font-size: 0.85rem;
                }
                .file-item:last-child {
                    margin-bottom: 0;
                }
                .file-item-icon {
                    font-size: 1.2rem;
                }
                .file-item-name {
                    flex: 1;
                    white-space: nowrap;
                    overflow: hidden;
                    text-overflow: ellipsis;
                }
                .file-item-size {
                    color: var(--text-dim);
                    font-size: 0.75rem;
                }
                input[type=number], select {
                    width: 100%;
                    padding: 12px 16px;
                    border-radius: 12px;
                    border: 1px solid var(--input-border);
                    background: var(--input-bg);
                    color: var(--text);
                    font-size: 0.875rem;
                    font-weight: 500;
                    transition: all 0.3s ease;
                }
                input[type=number]:focus, select:focus {
                    outline: none;
                    border-color: var(--primary);
                    box-shadow: 0 0 0 3px var(--input-focus);
                }
                button {
                    width: 100%;
                    padding: 14px 20px;
                    border-radius: 12px;
                    border: none;
                    font-weight: 700;
                    font-size: 0.95rem;
                    letter-spacing: 0.02em;
                    background: linear-gradient(135deg, var(--primary), var(--secondary));
                    color: white;
                    cursor: pointer;
                    transition: all 0.3s ease;
                    box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
                    margin-top: 12px;
                    position: relative;
                    overflow: hidden;
                }
                button::before {
                    content: '';
                    position: absolute;
                    top: 0; left: -100%; right: 100%; bottom: 0;
                    background: linear-gradient(90deg, transparent, rgba(255,255,255,0.3), transparent);
                    transition: left 0.5s ease;
                }
                button:hover::before { left: 100%; }
                button:hover {
                    transform: translateY(-2px);
                    box-shadow: 0 6px 20px rgba(59, 130, 246, 0.5);
                }
                button:active { transform: translateY(0); }
                button:disabled {
                    opacity: 0.5;
                    cursor: not-allowed;
                    transform: none;
                }
                .slider-row { display: flex; align-items: center; gap: 12px; margin-top: 16px; }
                input[type=range] {
                    flex: 1;
                    height: 8px;
                    border-radius: 10px;
                    background: rgba(148, 163, 184, 0.2);
                    outline: none;
                    -webkit-appearance: none;
                }
                input[type=range]::-webkit-slider-thumb {
                    -webkit-appearance: none;
                    width: 20px;
                    height: 20px;
                    border-radius: 50%;
                    background: linear-gradient(135deg, var(--primary), var(--secondary));
                    cursor: pointer;
                    box-shadow: 0 2px 8px rgba(59, 130, 246, 0.5);
                    transition: transform 0.2s ease;
                }
                input[type=range]::-webkit-slider-thumb:hover { transform: scale(1.2); }
                .pill {
                    padding: 8px 14px;
                    border-radius: 999px;
                    background: rgba(59, 130, 246, 0.15);
                    color: var(--primary-light);
                    font-weight: 700;
                    font-size: 0.9rem;
                    border: 1px solid rgba(59, 130, 246, 0.3);
                }
                .icon-btn {
                    width: 44px;
                    height: 44px;
                    border-radius: 12px;
                    border: 1px solid var(--input-border);
                    background: var(--input-bg);
                    color: var(--text);
                    font-size: 1.2rem;
                    cursor: pointer;
                    transition: all 0.3s ease;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                }
                .icon-btn:hover {
                    background: rgba(59, 130, 246, 0.2);
                    border-color: var(--primary);
                    transform: scale(1.05);
                }
                .icon-btn:disabled { opacity: 0.4; cursor: not-allowed; }
                .status {
                    margin-top: 12px;
                    padding: 12px 16px;
                    border-radius: 10px;
                    background: rgba(148, 163, 184, 0.1);
                    color: var(--text-muted);
                    font-size: 0.875rem;
                    border-left: 3px solid var(--text-dim);
                    min-height: 20px;
                    animation: fadeIn 0.3s ease;
                }
                .status.success {
                    background: rgba(16, 185, 129, 0.1);
                    color: var(--success);
                    border-left-color: var(--success);
                }
                .status.error {
                    background: rgba(239, 68, 68, 0.1);
                    color: var(--error);
                    border-left-color: var(--error);
                }
                .preview-container {
                    background: rgba(0, 0, 0, 0.3);
                    border-radius: 20px;
                    padding: 20px;
                    border: 1px solid var(--card-border);
                    min-height: 400px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                }
                video, img.preview-img {
                    width: 100%;
                    max-height: 600px;
                    background: black;
                    border-radius: 16px;
                    box-shadow: 0 12px 40px rgba(0, 0, 0, 0.6);
                    object-fit: contain;
                }
                .row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
                .row-3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; }
                .hidden { display: none !important; }
                .small { font-size: 0.8rem; color: var(--text-dim); margin-top: 8px; line-height: 1.5; }
                .divider {
                    height: 1px;
                    background: linear-gradient(90deg, transparent, rgba(255,255,255,0.1), transparent);
                    margin: 20px 0;
                }

                /* Top Navigation Bar */
                .top-navbar {
                    position: sticky;
                    top: 0;
                    z-index: 100;
                    background: rgba(17, 24, 39, 0.95);
                    backdrop-filter: blur(20px);
                    border-bottom: 1px solid var(--card-border);
                    margin: -32px -32px 32px -32px;
                    padding: 0 32px;
                    box-shadow: 0 4px 24px rgba(0, 0, 0, 0.3);
                }
                .nav-menu {
                    display: flex;
                    gap: 4px;
                    padding: 12px 0;
                    overflow-x: auto;
                    scrollbar-width: none;
                }
                .nav-menu::-webkit-scrollbar {
                    display: none;
                }
                .nav-item {
                    padding: 10px 20px;
                    border-radius: 10px;
                    background: transparent;
                    color: var(--text-muted);
                    font-weight: 600;
                    font-size: 0.9rem;
                    border: none;
                    cursor: pointer;
                    transition: all 0.3s ease;
                    white-space: nowrap;
                    display: flex;
                    align-items: center;
                    gap: 8px;
                }
                .nav-item:hover {
                    background: rgba(255, 255, 255, 0.05);
                    color: var(--text);
                }
                .nav-item.active {
                    background: linear-gradient(135deg, var(--primary), var(--secondary));
                    color: white;
                    box-shadow: 0 4px 12px rgba(59, 130, 246, 0.4);
                }
                .nav-icon {
                    font-size: 1.2rem;
                }
                .section-content {
                    animation: fadeIn 0.4s ease;
                }
                @keyframes fadeInUp {
                    from { opacity: 0; transform: translateY(20px); }
                    to { opacity: 1; transform: translateY(0); }
                }
                @keyframes fadeInDown {
                    from { opacity: 0; transform: translateY(-20px); }
                    to { opacity: 1; transform: translateY(0); }
                }
                @keyframes fadeIn {
                    from { opacity: 0; }
                    to { opacity: 1; }
                }
                @media (max-width: 1024px) {
                    .grid { grid-template-columns: 1fr; }
                    .header h1 { font-size: 2.5rem; }
                }
                @media (max-width: 768px) {
                    .row, .row-3 { grid-template-columns: 1fr; }
                    .header h1 { font-size: 2rem; }
                    .card { padding: 20px; }
                    .controls-panel { padding: 16px; }
                    .nav-item { padding: 8px 14px; font-size: 0.85rem; }
                    .top-navbar { margin: -20px -20px 24px -20px; padding: 0 20px; }
                }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🎬 Media Converter Pro</h1>
                    <p>Chuyển đổi video, ảnh và sticker chuyên nghiệp</p>
                </div>

                <div class="card">
                    <!-- Top Navigation Bar -->
                    <div class="top-navbar">
                        <nav class="nav-menu">
                            <button class="nav-item active" id="navVideoFps" data-section="video-fps">
                                <span class="nav-icon">🎥</span>
                                <span>Video FPS</span>
                            </button>
                            <button class="nav-item" id="navImageConvert" data-section="image-convert">
                                <span class="nav-icon">🖼️</span>
                                <span>Image Convert</span>
                            </button>
                            <button class="nav-item" id="navGifWebp" data-section="gif-webp">
                                <span class="nav-icon">🎞️</span>
                                <span>GIF → WebP</span>
                            </button>
                            <button class="nav-item" id="navVideoWebp" data-section="video-webp">
                                <span class="nav-icon">📹</span>
                                <span>Video → WebP</span>
                            </button>
                            <button class="nav-item" id="navBatchConvert" data-section="batch-convert">
                                <span class="nav-icon">📦</span>
                                <span>Batch Convert</span>
                            </button>
                             <button class="nav-item" id="navBatchResize" data-section="batch-resize">
                                <span class="nav-icon">🔧</span>
                                <span>Batch Resize</span>
                            </button>
                            <button class="nav-item" id="navTgsGif" data-section="tgs-gif">
                                <span class="nav-icon">🎨</span>
                                <span>TGS → GIF</span>
                            </button>
                        </nav>
                    </div>

                    <div id="videoSection" class="section-content grid">
                        <div class="controls-panel">
                            <div class="feature-card">
                                <div class="feature-title">Upload Video</div>
                                <div class="drop-zone" id="videoDropZone">
                                    <div class="drop-zone-icon">🎬</div>
                                    <div class="drop-zone-text">Kéo thả video vào đây</div>
                                    <div class="drop-zone-hint">hoặc click để chọn file</div>
                                    <input id="file" type="file" accept="video/*" />
                                </div>
                                <div id="videoFileList" class="file-list hidden"></div>
                                <button id="uploadBtn">📤 Tải lên</button>
                                <div class="status" id="status">Chưa có video.</div>
                            </div>

                            <div class="divider"></div>

                            <div class="feature-card">
                                <div class="feature-title">FPS Control</div>
                                <div class="slider-row">
                                    <button class="icon-btn" id="fpsDown" type="button">−</button>
                                    <input id="fpsRange" type="range" min="{{min_fps}}" max="{{max_fps}}" step="1" value="24" disabled />
                                    <button class="icon-btn" id="fpsUp" type="button">+</button>
                                    <div class="pill" id="fpsValue">24</div>
                                </div>
                                <div class="small">Kéo thanh để thay đổi FPS ({{min_fps}}-{{max_fps}})</div>
                            </div>

                            <div class="divider"></div>

                            <div class="feature-card">
                                <div class="feature-title">Export</div>
                                <label for="durationInput">Thời lượng (giây)</label>
                                <input id="durationInput" type="number" min="1" max="{{max_duration}}" step="1" value="5" disabled />
                                <button id="exportBtn" disabled>💾 Export & tải về</button>
                                <div class="small">Video sẽ tự động lặp nếu thời lượng dài hơn video gốc</div>
                            </div>
                        </div>

                        <div class="preview-container">
                            <video id="preview" controls playsinline loop muted></video>
                        </div>
                    </div>

                    
                    <!-- Image Convert Section -->
                    <div id="imageConvertSection" class="section-content hidden">
                        <div class="grid">
                            <div class="controls-panel">
                                <div class="feature-card">
                                    <div class="feature-title">Ảnh PNG/JPG → WebP</div>
                                    <label for="imgFile">Chọn ảnh</label>
                                    <input id="imgFile" type="file" accept="image/png,image/jpeg" />
                                    <button id="imgConvertBtn" type="button">🖼️ Convert & tải về</button>
                                    <div class="status" id="imgStatus">Chưa chọn ảnh.</div>
                                </div>
                            </div>
                            <div class="preview-container">
                                <img id="webpPreview" class="preview-img" alt="WebP preview" style="display:none;" />
                                <div style="text-align: center; color: var(--text-muted);">
                                    <div style="font-size: 4rem; margin-bottom: 16px;">🖼️</div>
                                    <div style="font-size: 1.1rem; font-weight: 600;">Preview Area</div>
                                    <div class="small">Ảnh đã convert sẽ hiển thị tại đây</div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- GIF to WebP Section -->
                    <div id="gifWebpSection" class="section-content hidden">
                        <div class="grid">
                            <div class="controls-panel">
                                <div class="feature-card">
                                    <div class="feature-title">GIF → WebP động</div>
                                    <label for="gifFile">Chọn GIF</label>
                                    <input id="gifFile" type="file" accept="image/gif" />
                                    <div class="row-3" style="margin-top: 10px;">
                                        <div>
                                            <label for="gifWebpFps" style="margin-bottom:6px;">FPS</label>
                                            <input id="gifWebpFps" type="number" min="1" max="60" value="15" />
                                        </div>
                                        <div>
                                            <label for="gifWebpWidth" style="margin-bottom:6px;">Width (px)</label>
                                            <input id="gifWebpWidth" type="number" min="64" max="2048" value="640" />
                                        </div>
                                        <div>
                                            <label for="gifWebpDuration" style="margin-bottom:6px;">Cắt (giây)</label>
                                            <input id="gifWebpDuration" type="number" min="0" max="{{max_webp_duration}}" value="0" />
                                        </div>
                                    </div>
                                    <button id="gifToWebpBtn" type="button">Convert GIF → WebP</button>
                                    <div class="status" id="gifWebpStatus">Chưa chọn GIF.</div>
                                </div>
                            </div>
                            <div class="preview-container">
                                <img id="gifWebpPreview" class="preview-img" alt="Preview" style="display:none;" />
                                <div style="text-align: center; color: var(--text-muted);">
                                    <div style="font-size: 4rem; margin-bottom: 16px;">🎞️</div>
                                    <div style="font-size: 1.1rem; font-weight: 600;">GIF Preview</div>
                                    <div class="small">Preview sẽ hiển thị tại đây</div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Video to WebP Section -->
                    <div id="videoWebpSection" class="section-content hidden">
                        <div class="grid">
                            <div class="controls-panel">
                                <div class="feature-card">
                                    <div class="feature-title">MP4 → WebP động</div>
                                    <label for="mp4File">Chọn video</label>
                                    <input id="mp4File" type="file" accept="video/mp4,video/*" />
                                    <div class="row-3" style="margin-top: 10px;">
                                        <div>
                                            <label for="mp4WebpFps" style="margin-bottom:6px;">FPS</label>
                                            <input id="mp4WebpFps" type="number" min="1" max="60" value="15" />
                                        </div>
                                        <div>
                                            <label for="mp4WebpWidth" style="margin-bottom:6px;">Width (px)</label>
                                            <input id="mp4WebpWidth" type="number" min="64" max="2048" value="640" />
                                        </div>
                                        <div>
                                            <label for="mp4WebpDuration" style="margin-bottom:6px;">Cắt (giây)</label>
                                            <input id="mp4WebpDuration" type="number" min="1" max="{{max_webp_duration}}" value="6" />
                                        </div>
                                    </div>
                                    <button id="mp4ToWebpBtn" type="button">Convert MP4 → WebP</button>
                                    <div class="status" id="mp4WebpStatus">Chưa chọn MP4.</div>
                                </div>

                                <div class="divider"></div>

                                <div class="feature-card">
                                    <div class="feature-title">Nhiều ảnh → WebP động</div>
                                    <label for="imgFiles">Chọn nhiều ảnh</label>
                                    <input id="imgFiles" type="file" accept="image/png,image/jpeg" multiple />
                                    <div class="row-3" style="margin-top: 10px;">
                                        <div>
                                            <label for="imgAnimFps" style="margin-bottom:6px;">FPS</label>
                                            <input id="imgAnimFps" type="number" min="1" max="60" value="10" />
                                        </div>
                                        <div>
                                            <label for="imgAnimWidth" style="margin-bottom:6px;">Width (px)</label>
                                            <input id="imgAnimWidth" type="number" min="64" max="2048" value="640" />
                                        </div>
                                        <div>
                                            <label style="margin-bottom:6px;">&nbsp;</label>
                                            <button id="imgAnimBtn" type="button" style="margin-top:0;">Tạo WebP động</button>
                                        </div>
                                    </div>
                                    <div class="status" id="imgAnimStatus">Chưa chọn nhiều ảnh.</div>
                                </div>
                            </div>
                            <div class="preview-container">
                                <img id="videoWebpPreview" class="preview-img" alt="Preview" style="display:none;" />
                                <div style="text-align: center; color: var(--text-muted);">
                                    <div style="font-size: 4rem; margin-bottom: 16px;">📹</div>
                                    <div style="font-size: 1.1rem; font-weight: 600;">Video → WebP</div>
                                    <div class="small">Preview sẽ hiển thị tại đây</div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Batch Convert Section -->
                    <div id="batchConvertSection" class="section-content hidden">
                        <div class="grid">
                            <div class="controls-panel">
                                <div class="feature-card">
                                    <div class="feature-title">Batch PNG/JPG → ZIP WebP</div>
                                    <label for="batchImgFiles">Chọn nhiều ảnh</label>
                                    <input id="batchImgFiles" type="file" accept="image/png,image/jpeg" multiple />
                                    <button id="batchConvertBtn" type="button">Convert batch → ZIP</button>
                                    <div class="status" id="batchStatus">Chưa chọn nhiều ảnh.</div>
                                </div>

                                <div class="divider"></div>

                                <div class="feature-card">
                                    <div class="feature-title">Batch convert ảnh → ZIP (WebP/PNG/JPG)</div>
                                    <label for="batch2ImgFiles">Chọn nhiều ảnh</label>
                                    <input id="batch2ImgFiles" type="file" accept="image/png,image/jpeg,image/webp" multiple />
                                    <div class="row-3" style="margin-top: 10px;">
                                        <div>
                                            <label for="batch2Format" style="margin-bottom:6px;">Format</label>
                                            <select id="batch2Format">
                                                <option value="webp" selected>webp</option>
                                                <option value="png">png</option>
                                                <option value="jpg">jpg</option>
                                            </select>
                                        </div>
                                        <div id="batch2QualityWrap">
                                            <label for="batch2Quality" style="margin-bottom:6px;">Quality (1–100)</label>
                                            <input id="batch2Quality" type="number" min="1" max="100" value="80" />
                                        </div>
                                        <div>
                                            <label for="batch2Width" style="margin-bottom:6px;">Resize width (px)</label>
                                            <input id="batch2Width" type="number" min="0" max="4096" value="0" />
                                        </div>
                                    </div>
                                    <div id="batch2LosslessWrap" style="margin-top: 10px;">
                                        <label style="margin: 0; display: flex; align-items: center; gap: 10px;">
                                            <input id="batch2Lossless" type="checkbox" />
                                            Lossless WebP (bỏ qua quality)
                                        </label>
                                        <div class="small" style="margin-top:6px;">Nếu không chọn lossless, PNG sẽ tự dùng lossless, còn JPG/WebP sẽ dùng lossy theo quality.</div>
                                    </div>
                                    <button id="batch2ConvertBtn" type="button">📦 Convert ảnh → ZIP</button>
                                    <div class="status" id="batch2Status">Chưa chọn nhiều ảnh.</div>
                                </div>
                            </div>
                            <div class="preview-container">
                                <div style="text-align: center; color: var(--text-muted);">
                                    <div style="font-size: 4rem; margin-bottom: 16px;">📦</div>
                                    <div style="font-size: 1.1rem; font-weight: 600;">Batch Convert</div>
                                    <div class="small">Converted files will be downloaded as ZIP</div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Batch Resize Section -->
                    <div id="batchResizeSection" class="section-content hidden">
                        <div class="grid">
                            <div class="controls-panel">
                                <div class="feature-card">
                                    <div class="feature-title">Batch WebP/GIF Resize → ZIP</div>
                                    <label for="animatedResizeFiles">Chọn nhiều file WebP/GIF</label>
                                    <input id="animatedResizeFiles" type="file" accept="image/webp,.gif" multiple />
                                    <div class="row-3" style="margin-top: 10px;">
                                        <div>
                                            <label for="animatedResizeWidth" style="margin-bottom:6px;">Width (px, 0=giữ nguyên)</label>
                                            <input id="animatedResizeWidth" type="number" min="0" max="4096" value="0" placeholder="0" />
                                        </div>
                                        <div>
                                            <label for="animatedResizeHeight" style="margin-bottom:6px;">Height (px, 0=giữ nguyên)</label>
                                            <input id="animatedResizeHeight" type="number" min="0" max="4096" value="0" placeholder="0" />
                                        </div>
                                        <div>
                                            <label for="animatedResizeTargetKB" style="margin-bottom:6px;">Target size (KB, 0=giữ nguyên)</label>
                                            <input id="animatedResizeTargetKB" type="number" min="0" max="10240" value="0" placeholder="0" />
                                        </div>
                                    </div>
                                    <div style="margin-top: 10px;">
                                        <label for="animatedResizeQuality" style="margin-bottom:6px;">Quality WebP (1–100, chỉ áp dụng cho WebP)</label>
                                        <input id="animatedResizeQuality" type="number" min="1" max="100" value="80" />
                                    </div>
                                    <button id="animatedResizeBtn" type="button">🎬 Resize WebP/GIF → ZIP</button>
                                    <div class="status" id="animatedResizeStatus">Chưa chọn file.</div>
                                    <div class="small" style="margin-top:6px;">
                                        Batch resize WebP/GIF (bao gồm cả animated). Mọi thông số đều optional:
                                        <br>• Width/Height = 0: giữ nguyên kích thước
                                        <br>• Target size = 0: không giới hạn dung lượng
                                        <br>• Nếu chỉ nhập Width, height sẽ tự scale theo tỷ lệ (và ngược lại)
                                        <br>• Format output giữ nguyên như input (.webp → .webp, .gif → .gif)
                                    </div>
                                </div>

                                <div class="divider"></div>

                                <div class="feature-card">
                                    <div class="feature-title">Batch Image Resize + Size Control → ZIP</div>
                                    <label for="webpResizeFiles">Chọn nhiều ảnh</label>
                                    <input id="webpResizeFiles" type="file" accept="image/png,image/jpeg,image/webp" multiple />
                                    <div class="row-3" style="margin-top: 10px;">
                                        <div>
                                            <label for="webpResizeFormat" style="margin-bottom:6px;">Format</label>
                                            <select id="webpResizeFormat">
                                                <option value="webp" selected>webp</option>
                                                <option value="png">png</option>
                                                <option value="jpg">jpg</option>
                                            </select>
                                        </div>
                                        <div>
                                            <label for="webpResizeWidth" style="margin-bottom:6px;">Width (px)</label>
                                            <input id="webpResizeWidth" type="number" min="16" max="4096" value="800" />
                                        </div>
                                        <div>
                                            <label for="webpResizeTargetKB" style="margin-bottom:6px;">Target size (KB)</label>
                                            <input id="webpResizeTargetKB" type="number" min="0" max="10240" value="0" placeholder="0=auto" />
                                        </div>
                                    </div>
                                    <div style="margin-top: 10px;">
                                        <label for="webpResizeQuality" style="margin-bottom:6px;">Quality (1–100, starting point if target size set)</label>
                                        <input id="webpResizeQuality" type="number" min="1" max="100" value="85" />
                                    </div>
                                    <button id="webpResizeBtn" type="button">🔧 Resize + Compress → ZIP</button>
                                    <div class="status" id="webpResizeStatus">Chưa chọn file.</div>
                                    <div class="small" style="margin-top:6px;">
                                        Chọn nhiều ảnh (WebP/PNG/JPG), resize về 1 kích thước và giới hạn dung lượng file (KB).
                                        Nếu target size = 0, chỉ resize và dùng quality cố định.
                                        Nếu target size > 0, tool sẽ tự giảm quality để đạt kích thước mong muốn.
                                    </div>
                                </div>
                            </div>
                            <div class="preview-container">
                                <div style="text-align: center; color: var(--text-muted);">
                                    <div style="font-size: 4rem; margin-bottom: 16px;">🔧</div>
                                    <div style="font-size: 1.1rem; font-weight: 600;">Batch Resize</div>
                                    <div class="small">Resized files will be downloaded as ZIP</div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- TGS to GIF Section -->
                    <div id="tgsGifSection" class="section-content hidden">
                        <div class="grid">
                            <div class="controls-panel">
                                <div class="feature-card">
                                    <div class="feature-title">Batch TGS → GIF (ZIP)</div>
                                    <div class="drop-zone" id="tgsDropZone">
                                        <div class="drop-zone-icon">🎨</div>
                                        <div class="drop-zone-text">Kéo thả file TGS vào đây</div>
                                        <div class="drop-zone-hint">hoặc click để chọn nhiều file</div>
                                        <input id="tgsFiles" type="file" accept=".tgs" multiple />
                                    </div>
                                    <div id="tgsFileList" class="file-list hidden"></div>
                                    <div class="row-3" style="margin-top: 10px;">
                                        <div>
                                            <label for="tgsFps" style="margin-bottom:6px;">FPS</label>
                                            <input id="tgsFps" type="number" min="1" max="60" value="30" />
                                        </div>
                                        <div>
                                            <label for="tgsQuality" style="margin-bottom:6px;">Quality (1–100)</label>
                                            <input id="tgsQuality" type="number" min="1" max="100" value="80" />
                                        </div>
                                        <div>
                                            <label for="tgsWidth" style="margin-bottom:6px;">Width (px, 0=auto)</label>
                                            <input id="tgsWidth" type="number" min="0" max="2048" value="0" placeholder="Auto" />
                                        </div>
                                    </div>
                                    <button id="tgsConvertBtn" type="button">🎨 Convert TGS → GIF ZIP</button>
                                    <div class="status" id="tgsStatus">Chưa chọn file TGS.</div>
                                    <div class="small">TGS là Telegram animated sticker. Upload nhiều file để convert sang GIF và tải về dưới dạng ZIP.</div>
                                </div>
                            </div>
                            <div class="preview-container">
                                <div style="text-align: center; color: var(--text-muted);">
                                    <div style="font-size: 4rem; margin-bottom: 16px;">🎨</div>
                                    <div style="font-size: 1.1rem; font-weight: 600;">TGS → GIF Converter</div>
                                    <div class="small">Preview và download ZIP sau khi convert</div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <script>
                const uploadBtn = document.getElementById('uploadBtn');
                const fileInput = document.getElementById('file');
                const statusEl = document.getElementById('status');
                const preview = document.getElementById('preview');
                const fpsRange = document.getElementById('fpsRange');
                const fpsDown = document.getElementById('fpsDown');
                const fpsUp = document.getElementById('fpsUp');
                const fpsValue = document.getElementById('fpsValue');
                const durationInput = document.getElementById('durationInput');
                const exportBtn = document.getElementById('exportBtn');

                // Removed unused variables for sections here to avoid confusion with initNavigation
                const webpPreview = document.getElementById('webpPreview');
                const imgFile = document.getElementById('imgFile');
                const imgConvertBtn = document.getElementById('imgConvertBtn');
                const imgStatus = document.getElementById('imgStatus');

                const imgFiles = document.getElementById('imgFiles');
                const imgAnimFps = document.getElementById('imgAnimFps');
                const imgAnimWidth = document.getElementById('imgAnimWidth');
                const imgAnimBtn = document.getElementById('imgAnimBtn');
                const imgAnimStatus = document.getElementById('imgAnimStatus');

                const mp4File = document.getElementById('mp4File');
                const mp4WebpFps = document.getElementById('mp4WebpFps');
                const mp4WebpWidth = document.getElementById('mp4WebpWidth');
                const mp4WebpDuration = document.getElementById('mp4WebpDuration');
                const mp4ToWebpBtn = document.getElementById('mp4ToWebpBtn');
                const mp4WebpStatus = document.getElementById('mp4WebpStatus');

                const gifFile = document.getElementById('gifFile');
                const gifWebpFps = document.getElementById('gifWebpFps');
                const gifWebpWidth = document.getElementById('gifWebpWidth');
                const gifWebpDuration = document.getElementById('gifWebpDuration');
                const gifToWebpBtn = document.getElementById('gifToWebpBtn');
                const gifWebpStatus = document.getElementById('gifWebpStatus');

                const batchImgFiles = document.getElementById('batchImgFiles');
                const batchConvertBtn = document.getElementById('batchConvertBtn');
                const batchStatus = document.getElementById('batchStatus');

                const batch2ImgFiles = document.getElementById('batch2ImgFiles');
                const batch2Format = document.getElementById('batch2Format');
                const batch2QualityWrap = document.getElementById('batch2QualityWrap');
                const batch2Quality = document.getElementById('batch2Quality');
                const batch2Width = document.getElementById('batch2Width');
                const batch2LosslessWrap = document.getElementById('batch2LosslessWrap');
                const batch2Lossless = document.getElementById('batch2Lossless');
                const batch2ConvertBtn = document.getElementById('batch2ConvertBtn');
                const batch2Status = document.getElementById('batch2Status');

                const tgsFiles = document.getElementById('tgsFiles');
                const tgsFps = document.getElementById('tgsFps');
                const tgsQuality = document.getElementById('tgsQuality');
                const tgsWidth = document.getElementById('tgsWidth');
                const tgsConvertBtn = document.getElementById('tgsConvertBtn');
                const tgsStatus = document.getElementById('tgsStatus');

                let fileId = null;
                let debounceTimer = null;
                let activeController = null;

                // Enhanced status functions with visual feedback
                function setStatus(text, type = 'info') {
                    statusEl.textContent = text;
                    statusEl.className = 'status';
                    if (type === 'success') statusEl.classList.add('success');
                    if (type === 'error') statusEl.classList.add('error');
                }

                function updateStatus(element, text, type = 'info') {
                    element.textContent = text;
                    element.className = 'status';
                    if (type === 'success') element.classList.add('success');
                    if (type === 'error') element.classList.add('error');
                }

                // Drag and drop utilities
                function formatFileSize(bytes) {
                    if (bytes === 0) return '0 Bytes';
                    const k = 1024;
                    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
                    const i = Math.floor(Math.log(bytes) / Math.log(k));
                    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
                }

                function displayFileList(files, listElement) {
                    if (!files || files.length === 0) {
                        listElement.classList.add('hidden');
                        return;
                    }

                    listElement.classList.remove('hidden');
                    listElement.innerHTML = '';

                    Array.from(files).forEach(file => {
                        const fileItem = document.createElement('div');
                        fileItem.className = 'file-item';
                        fileItem.innerHTML = `
                            <span class="file-item-icon">📄</span>
                            <span class="file-item-name">${file.name}</span>
                            <span class="file-item-size">${formatFileSize(file.size)}</span>
                        `;
                        listElement.appendChild(fileItem);
                    });
                }

                function setupDropZone(dropZone, fileInput, fileListElement) {
                    // Prevent default drag behaviors
                    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
                        dropZone.addEventListener(eventName, e => {
                            e.preventDefault();
                            e.stopPropagation();
                        });
                    });

                    // Highlight drop zone when dragging over
                    ['dragenter', 'dragover'].forEach(eventName => {
                        dropZone.addEventListener(eventName, () => {
                            dropZone.classList.add('drag-over');
                        });
                    });

                    ['dragleave', 'drop'].forEach(eventName => {
                        dropZone.addEventListener(eventName, () => {
                            dropZone.classList.remove('drag-over');
                        });
                    });

                    // Handle dropped files
                    dropZone.addEventListener('drop', e => {
                        const dt = e.dataTransfer;
                        const files = dt.files;
                        fileInput.files = files;

                        // Trigger change event
                        const event = new Event('change', { bubbles: true });
                        fileInput.dispatchEvent(event);

                        if (fileListElement) {
                            displayFileList(files, fileListElement);
                        }
                    });

                    // Also show file list when using file picker
                    fileInput.addEventListener('change', () => {
                        if (fileListElement) {
                            displayFileList(fileInput.files, fileListElement);
                        }
                    });
                }

                // Setup drop zones
                setupDropZone(
                    document.getElementById('videoDropZone'),
                    fileInput,
                    document.getElementById('videoFileList')
                );

                setupDropZone(
                    document.getElementById('tgsDropZone'),
                    document.getElementById('tgsFiles'),
                    document.getElementById('tgsFileList')
                );

                // Navigation handling - Initialize after DOM elements are available
                function initNavigation() {
                    const navItems = document.querySelectorAll('.nav-item');
                    const videoSection = document.getElementById('videoSection');
                    const imageConvertSection = document.getElementById('imageConvertSection');
                    const gifWebpSection = document.getElementById('gifWebpSection');
                    const videoWebpSection = document.getElementById('videoWebpSection');
                    const batchConvertSection = document.getElementById('batchConvertSection');
                    const batchResizeSection = document.getElementById('batchResizeSection');
                    const tgsGifSection = document.getElementById('tgsGifSection');

                    const allSections = [
                        videoSection,
                        imageConvertSection,
                        gifWebpSection,
                        videoWebpSection,
                        batchConvertSection,
                        batchResizeSection,
                        tgsGifSection
                    ];

                    console.log('Navigation initialized. Nav items:', navItems.length);

                    function setActiveSection(sectionName) {
                        console.log('Switching to section:', sectionName);

                        // Remove active from all nav items
                        navItems.forEach(item => item.classList.remove('active'));

                        // Add active to clicked item
                        const activeNav = document.querySelector(`[data-section="${sectionName}"]`);
                        if (activeNav) {
                            activeNav.classList.add('active');
                        }

                        // Hide all sections first
                        allSections.forEach(section => {
                            if (section) section.classList.add('hidden');
                        });

                        // Show the selected section
                        const sectionMap = {
                            'video-fps': videoSection,
                            'image-convert': imageConvertSection,
                            'gif-webp': gifWebpSection,
                            'video-webp': videoWebpSection,
                            'batch-convert': batchConvertSection,
                            'batch-resize': batchResizeSection,
                            'tgs-gif': tgsGifSection
                        };

                        const targetSection = sectionMap[sectionName];
                        if (targetSection) {
                            targetSection.classList.remove('hidden');
                            console.log('Showing section:', sectionName);
                        }
                    }

                    // Add click handlers to all nav items
                    navItems.forEach(item => {
                        item.addEventListener('click', () => {
                            const section = item.getAttribute('data-section');
                            setActiveSection(section);
                        });
                    });
                }

                // Initialize navigation
                initNavigation();

                function enableControls(enabled) {
                    fpsRange.disabled = !enabled;
                    fpsDown.disabled = !enabled;
                    fpsUp.disabled = !enabled;
                    durationInput.disabled = !enabled;
                    exportBtn.disabled = !enabled;
                }

                uploadBtn.addEventListener('click', async () => {
                    const file = fileInput.files?.[0];
                    if (!file) { setStatus('Hãy chọn một file video.'); return; }

                    setStatus('Đang tải lên...');
                    const form = new FormData();
                    form.append('file', file);

                    try {
                        const res = await fetch('/upload', { method: 'POST', body: form });
                        if (!res.ok) throw new Error(await res.text());
                        const data = await res.json();
                        fileId = data.file_id;
                        preview.src = data.file_url;
                        preview.play();
                        enableControls(true);
                        setStatus(`✅ Tải lên thành công! FPS gốc: ${data.original_fps ?? '—'}`, 'success');
                    } catch (err) {
                        console.error(err);
                        setStatus('❌ Tải lên thất bại: ' + err.message, 'error');
                    }
                });

                fpsRange.addEventListener('input', () => {
                    const fps = Number(fpsRange.value);
                    fpsValue.textContent = fps;
                    if (!fileId) { setStatus('Tải video trước.'); return; }
                    if (debounceTimer) clearTimeout(debounceTimer);
                    debounceTimer = setTimeout(() => requestConvert(fps), 350);
                });

                const clamp = (val) => Math.min(Number(fpsRange.max), Math.max(Number(fpsRange.min), val));
                function nudge(delta) {
                    const next = clamp(Number(fpsRange.value) + delta);
                    fpsRange.value = next;
                    fpsRange.dispatchEvent(new Event('input'));
                }
                fpsDown.addEventListener('click', () => nudge(-1));
                fpsUp.addEventListener('click', () => nudge(1));

                exportBtn.addEventListener('click', async () => {
                    if (!fileId) { setStatus('Tải video trước.'); return; }
                    const fps = Number(fpsRange.value);
                    const duration = Number(durationInput.value);
                    if (!duration || duration < 1) { setStatus('Nhập thời lượng hợp lệ.'); return; }
                    setStatus('Đang export...');

                    try {
                        const res = await fetch('/export', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ fps, duration, file_id: fileId }),
                        });
                        if (!res.ok) throw new Error(await res.text());
                        const blob = await res.blob();
                        const url = URL.createObjectURL(blob);
                        const a = document.createElement('a');
                        a.href = url;
                        a.download = `export_${fps}fps_${duration}s.mp4`;
                        document.body.appendChild(a);
                        a.click();
                        a.remove();
                        URL.revokeObjectURL(url);
                        setStatus(`Đã export ${duration}s @ ${fps} fps`);
                    } catch (err) {
                        console.error(err);
                        setStatus('Lỗi export: ' + err.message);
                    }
                });

                async function requestConvert(fps) {
                    if (activeController) activeController.abort();
                    const controller = new AbortController();
                    activeController = controller;
                    setStatus('Đang chuyển đổi...');

                    try {
                        const res = await fetch('/convert', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ fps, file_id: fileId }),
                            signal: controller.signal,
                        });
                        if (!res.ok) throw new Error(await res.text());
                        const blob = await res.blob();
                        const url = URL.createObjectURL(blob);
                        preview.src = url;
                        preview.play();
                        setStatus(`Preview ở ${fps} fps`);
                    } catch (err) {
                        if (err.name === 'AbortError') return;
                        console.error(err);
                        setStatus('Lỗi chuyển đổi: ' + err.message);
                        }
                }

                function downloadBlob(blob, filename) {
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = filename;
                    document.body.appendChild(a);
                    a.click();
                    a.remove();
                    URL.revokeObjectURL(url);
                }

                function setWebpPreviewFromBlob(blob) {
                    const url = URL.createObjectURL(blob);
                    webpPreview.src = url;
                    // Revoke when a new image is set later; simplest: keep last URL on element.
                    if (webpPreview.dataset.url) URL.revokeObjectURL(webpPreview.dataset.url);
                    webpPreview.dataset.url = url;
                }

                imgConvertBtn.addEventListener('click', async () => {
                    const file = imgFile.files?.[0];
                    if (!file) { imgStatus.textContent = 'Hãy chọn PNG/JPG.'; return; }

                    imgStatus.textContent = 'Đang convert...';
                    const form = new FormData();
                    form.append('file', file);

                    try {
                        const res = await fetch('/png-to-webp', { method: 'POST', body: form });
                        if (!res.ok) throw new Error(await res.text());
                        const blob = await res.blob();
                        setWebpPreviewFromBlob(blob);
                        const outName = (file.name?.replace(/[.](png|jpg|jpeg)$/i, '') || 'image') + '.webp';
                        downloadBlob(blob, outName);
                        imgStatus.textContent = 'Xong.';
                    } catch (err) {
                        console.error(err);
                        imgStatus.textContent = 'Lỗi: ' + err.message;
                    }
                });

                imgAnimBtn.addEventListener('click', async () => {
                    const files = Array.from(imgFiles.files || []);
                    if (files.length === 0) { imgAnimStatus.textContent = 'Hãy chọn nhiều ảnh.'; return; }
                    if (files.length === 1) { imgAnimStatus.textContent = 'Chọn ít nhất 2 ảnh để thấy “động”.'; }

                    const fps = Number(imgAnimFps.value || 10);
                    const width = Number(imgAnimWidth.value || 640);

                    imgAnimStatus.textContent = 'Đang tạo WebP động...';
                    const form = new FormData();
                    for (const f of files) form.append('files', f);
                    form.append('fps', String(fps));
                    form.append('width', String(width));

                    try {
                        const res = await fetch('/images-to-animated-webp', { method: 'POST', body: form });
                        if (!res.ok) throw new Error(await res.text());
                        const blob = await res.blob();
                        setWebpPreviewFromBlob(blob);
                        downloadBlob(blob, `images_${files.length}frames_${fps}fps.webp`);
                        imgAnimStatus.textContent = `Xong (${files.length} ảnh @ ${fps} fps).`;
                    } catch (err) {
                        console.error(err);
                        imgAnimStatus.textContent = 'Lỗi: ' + err.message;
                    }
                });

                mp4ToWebpBtn.addEventListener('click', async () => {
                    const file = mp4File.files?.[0];
                    if (!file) { mp4WebpStatus.textContent = 'Hãy chọn MP4.'; return; }

                    const fps = Number(mp4WebpFps.value || 15);
                    const width = Number(mp4WebpWidth.value || 640);
                    const duration = Number(mp4WebpDuration.value || 0);

                    mp4WebpStatus.textContent = 'Đang convert MP4 → WebP...';
                    const form = new FormData();
                    form.append('file', file);
                    form.append('fps', String(fps));
                    form.append('width', String(width));
                    form.append('duration', String(duration));

                    try {
                        const res = await fetch('/mp4-to-animated-webp', { method: 'POST', body: form });
                        if (!res.ok) throw new Error(await res.text());
                        const blob = await res.blob();
                        setWebpPreviewFromBlob(blob);
                        downloadBlob(blob, `video_${fps}fps_${duration || 'full'}s.webp`);
                        mp4WebpStatus.textContent = `Xong (${fps} fps, width ${width}px, cắt ${duration}s).`;
                    } catch (err) {
                        console.error(err);
                        mp4WebpStatus.textContent = 'Lỗi: ' + err.message;
                    }
                });

                gifToWebpBtn.addEventListener('click', async () => {
                    const file = gifFile.files?.[0];
                    if (!file) { gifWebpStatus.textContent = 'Hãy chọn GIF.'; return; }

                    const fps = Number(gifWebpFps.value || 15);
                    const width = Number(gifWebpWidth.value || 640);
                    const duration = Number(gifWebpDuration.value || 0);

                    gifWebpStatus.textContent = 'Đang convert GIF → WebP...';
                    const form = new FormData();
                    form.append('file', file);
                    form.append('fps', String(fps));
                    form.append('width', String(width));
                    form.append('duration', String(duration));

                    try {
                        const res = await fetch('/gif-to-webp', { method: 'POST', body: form });
                        if (!res.ok) throw new Error(await res.text());
                        const blob = await res.blob();
                        setWebpPreviewFromBlob(blob);
                        const base = (file.name?.replace(/[.]gif$/i, '') || 'gif');
                        downloadBlob(blob, `${base}_${fps}fps_${duration || 'full'}s.webp`);
                        gifWebpStatus.textContent = `Xong (${fps} fps, width ${width}px, cắt ${duration || 'full'}).`;
                    } catch (err) {
                        console.error(err);
                        gifWebpStatus.textContent = 'Lỗi: ' + err.message;
                    }
                });

                batchConvertBtn.addEventListener('click', async () => {
                    const files = Array.from(batchImgFiles.files || []);
                    if (files.length === 0) { batchStatus.textContent = 'Hãy chọn nhiều ảnh.'; return; }

                    batchStatus.textContent = `Đang convert ${files.length} ảnh...`;
                    const form = new FormData();
                    for (const f of files) form.append('files', f);

                    try {
                        const res = await fetch('/images-to-webp-zip', { method: 'POST', body: form });
                        if (!res.ok) throw new Error(await res.text());
                        const blob = await res.blob();
                        downloadBlob(blob, `images_${files.length}_webp.zip`);
                        batchStatus.textContent = `Xong (${files.length} ảnh).`;
                    } catch (err) {
                        console.error(err);
                        batchStatus.textContent = 'Lỗi: ' + err.message;
                    }
                });

                function syncBatch2Ui() {
                    const fmt = String(batch2Format.value || 'webp');
                    batch2LosslessWrap.classList.toggle('hidden', fmt !== 'webp');
                    batch2QualityWrap.classList.toggle('hidden', fmt === 'png');
                }
                batch2Format.addEventListener('change', syncBatch2Ui);
                syncBatch2Ui();

                batch2ConvertBtn.addEventListener('click', async () => {
                    const files = Array.from(batch2ImgFiles.files || []);
                    if (files.length === 0) { batch2Status.textContent = 'Hãy chọn nhiều ảnh.'; return; }

                    const fmt = String(batch2Format.value || 'webp');
                    const quality = Number(batch2Quality.value || 0);
                    const width = Number(batch2Width.value || 0);
                    const lossless = Boolean(batch2Lossless.checked);

                    batch2Status.textContent = `Đang convert ${files.length} ảnh → ${fmt}...`;

                    const form = new FormData();
                    for (const f of files) form.append('files', f);
                    form.append('format', fmt);
                    if (width && width > 0) form.append('width', String(width));
                    if (fmt !== 'png' && quality && quality > 0) form.append('quality', String(quality));
                    // Only send lossless when forcing it; otherwise server auto-picks lossless for PNG inputs.
                    if (fmt === 'webp' && lossless) form.append('lossless', '1');

                    try {
                        const res = await fetch('/images-convert-zip', { method: 'POST', body: form });
                        if (!res.ok) throw new Error(await res.text());
                        const blob = await res.blob();
                        downloadBlob(blob, `images_${files.length}_${fmt}.zip`);
                        batch2Status.textContent = `Xong (${files.length} ảnh → ${fmt}).`;
                    } catch (err) {
                        console.error(err);
                        batch2Status.textContent = 'Lỗi: ' + err.message;
                    }
                });

                // Animated WebP/GIF batch resize
                const animatedResizeFiles = document.getElementById('animatedResizeFiles');
                const animatedResizeWidth = document.getElementById('animatedResizeWidth');
                const animatedResizeHeight = document.getElementById('animatedResizeHeight');
                const animatedResizeTargetKB = document.getElementById('animatedResizeTargetKB');
                const animatedResizeQuality = document.getElementById('animatedResizeQuality');
                const animatedResizeBtn = document.getElementById('animatedResizeBtn');
                const animatedResizeStatus = document.getElementById('animatedResizeStatus');

                animatedResizeBtn.addEventListener('click', async () => {
                    const files = Array.from(animatedResizeFiles.files || []);
                    if (files.length === 0) {
                        animatedResizeStatus.textContent = 'Hãy chọn file WebP/GIF.';
                        return;
                    }

                    const width = Number(animatedResizeWidth.value || 0);
                    const height = Number(animatedResizeHeight.value || 0);
                    const targetKB = Number(animatedResizeTargetKB.value || 0);
                    const quality = Number(animatedResizeQuality.value || 80);

                    animatedResizeStatus.textContent = `Đang xử lý ${files.length} file...`;

                    const form = new FormData();
                    for (const f of files) form.append('files', f);
                    if (width > 0) form.append('width', String(width));
                    if (height > 0) form.append('height', String(height));
                    if (targetKB > 0) form.append('target_size_kb', String(targetKB));
                    if (quality > 0) form.append('quality', String(quality));

                    try {
                        const res = await fetch('/batch-animated-resize-zip', { method: 'POST', body: form });
                        if (!res.ok) throw new Error(await res.text());
                        const blob = await res.blob();
                        downloadBlob(blob, `animated_resized_${files.length}.zip`);

                        const params = [];
                        if (width > 0 || height > 0) params.push(`${width || 'auto'}x${height || 'auto'}`);
                        if (targetKB > 0) params.push(`${targetKB}KB`);
                        animatedResizeStatus.textContent = `Xong (${files.length} file${params.length ? ', ' + params.join(', ') : ''}).`;
                    } catch (err) {
                        console.error(err);
                        animatedResizeStatus.textContent = 'Lỗi: ' + err.message;
                    }
                });

                // WebP resize with size control batch conversion
                const webpResizeFiles = document.getElementById('webpResizeFiles');
                const webpResizeFormat = document.getElementById('webpResizeFormat');
                const webpResizeWidth = document.getElementById('webpResizeWidth');
                const webpResizeTargetKB = document.getElementById('webpResizeTargetKB');
                const webpResizeQuality = document.getElementById('webpResizeQuality');
                const webpResizeBtn = document.getElementById('webpResizeBtn');
                const webpResizeStatus = document.getElementById('webpResizeStatus');

                webpResizeBtn.addEventListener('click', async () => {
                    const files = Array.from(webpResizeFiles.files || []);
                    if (files.length === 0) {
                        webpResizeStatus.textContent = 'Hãy chọn file.';
                        return;
                    }

                    const fmt = String(webpResizeFormat.value || 'webp');
                    const width = Number(webpResizeWidth.value || 800);
                    const targetKB = Number(webpResizeTargetKB.value || 0);
                    const quality = Number(webpResizeQuality.value || 85);

                    webpResizeStatus.textContent = `Đang xử lý ${files.length} ảnh...`;

                    const form = new FormData();
                    for (const f of files) form.append('files', f);
                    form.append('format', fmt);
                    form.append('width', String(width));
                    if (targetKB > 0) form.append('target_size_kb', String(targetKB));
                    if (quality > 0) form.append('quality', String(quality));

                    try {
                        const res = await fetch('/webp-resize-zip', { method: 'POST', body: form });
                        if (!res.ok) throw new Error(await res.text());
                        const blob = await res.blob();
                        downloadBlob(blob, `resized_${files.length}_${fmt}.zip`);
                        webpResizeStatus.textContent = `Xong (${files.length} ảnh, ${width}px, ${targetKB ? targetKB + 'KB target' : 'quality ' + quality}).`;
                    } catch (err) {
                        console.error(err);
                        webpResizeStatus.textContent = 'Lỗi: ' + err.message;
                    }
                });

                // TGS to GIF batch conversion
                tgsConvertBtn.addEventListener('click', async () => {
                    const files = tgsFiles.files;
                    if (!files || files.length === 0) {
                        tgsStatus.textContent = 'Chọn ít nhất 1 file .tgs';
                        return;
                    }

                    const fps = Number(tgsFps.value) || 30;
                    const quality = Number(tgsQuality.value) || 80;
                    const width = Number(tgsWidth.value) || 0;

                    tgsStatus.textContent = `Đang chuyển đổi ${files.length} file TGS...`;

                    try {
                        const form = new FormData();
                        for (const f of files) form.append('files', f);
                        form.append('fps', String(fps));
                        form.append('quality', String(quality));
                        if (width > 0) form.append('width', String(width));

                        const res = await fetch('/tgs-to-gif-zip', { method: 'POST', body: form });
                        if (!res.ok) throw new Error(await res.text());
                        const blob = await res.blob();
                        downloadBlob(blob, `tgs_to_gif_${files.length}.zip`);
                        tgsStatus.textContent = `Xong (${files.length} TGS → GIF).`;
                    } catch (err) {
                        console.error(err);
                        tgsStatus.textContent = 'Lỗi: ' + err.message;
                    }
                });
            </script>
        </body>
        </html>
        """,
        min_fps=MIN_FPS,
        max_fps=MAX_FPS,
        max_duration=MAX_DURATION,
        max_webp_duration=MAX_WEBP_DURATION,
    )


@app.post("/upload")
def upload():
    file = request.files.get("file")
    if file is None or file.filename == "":
        abort(400, "Thiếu file video")

    suffix = Path(file.filename).suffix or ".mp4"
    file_id = f"{uuid.uuid4().hex}{suffix}"
    save_path = UPLOAD_DIR / file_id
    file.save(save_path)

    return jsonify(
        {
            "file_id": file_id,
            "file_url": f"/files/uploads/{file_id}",
            "original_fps": None,
        }
    )


@app.post("/convert")
def convert():
    payload = request.get_json(silent=True) or {}
    fps = _validate_fps(payload.get("fps"))
    file_id = payload.get("file_id")
    if not file_id:
        abort(400, "Thiếu file_id")

    input_path = _safe_upload_path(file_id, UPLOAD_DIR)

    try:
        output_path = _convert_video(input_path, fps)
    except Exception as exc:  # pragma: no cover - logs forwarded to client
        abort(500, f"Lỗi ffmpeg: {exc}")

    @after_this_request
    def cleanup(response):  # type: ignore
        try:
            output_path.unlink(missing_ok=True)
        except OSError:
            pass
        return response

    return send_file(output_path, mimetype="video/mp4", as_attachment=False)


@app.post("/export")
def export():
    payload = request.get_json(silent=True) or {}
    fps = _validate_fps(payload.get("fps"))
    duration = _validate_duration(payload.get("duration"))
    file_id = payload.get("file_id")
    if not file_id:
        abort(400, "Thiếu file_id")

    input_path = _safe_upload_path(file_id, UPLOAD_DIR)

    try:
        output_path = _convert_video(input_path, fps, duration=duration, loop=True)
    except Exception as exc:  # pragma: no cover
        abort(500, f"Lỗi ffmpeg: {exc}")

    @after_this_request
    def cleanup(response):  # type: ignore
        try:
            output_path.unlink(missing_ok=True)
        except OSError:
            pass
        return response

    return send_file(
        output_path,
        mimetype="video/mp4",
        as_attachment=True,
        download_name=f"export_{fps}fps_{duration}s.mp4",
    )


@app.get("/files/uploads/<path:filename>")
def serve_upload(filename: str):
    file_path = _safe_upload_path(filename, UPLOAD_DIR)
    return send_file(file_path, mimetype="video/mp4")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/png-to-webp")
def png_to_webp():
    """Convert an uploaded PNG/JPG image to WebP and return the converted file."""
    file = request.files.get("file")
    if file is None or file.filename == "":
        abort(400, "Thiếu file ảnh")

    filename = file.filename
    suffix = _allowed_image_suffix(filename)
    if suffix is None:
        abort(400, "Chỉ chấp nhận PNG/JPG/JPEG")

    input_name = f"{uuid.uuid4().hex}{suffix}"
    input_path = UPLOAD_DIR / input_name
    file.save(input_path)

    try:
        output_path = _convert_image_to_webp(input_path, lossless=(suffix == ".png"))
    except Exception as exc:  # pragma: no cover
        abort(500, f"Lỗi ffmpeg: {exc}")

    @after_this_request
    def cleanup(response):  # type: ignore
        input_path.unlink(missing_ok=True)
        output_path.unlink(missing_ok=True)
        return response

    return send_file(
        output_path,
        mimetype="image/webp",
        as_attachment=True,
        download_name=Path(filename).stem + ".webp",
    )


@app.post("/images-to-animated-webp")
def images_to_animated_webp():
    files = request.files.getlist("files")
    if not files:
        abort(400, "Thiếu danh sách ảnh (files)")

    fps = _validate_positive_int(request.form.get("fps"), name="FPS", min_value=1, max_value=60)
    width_raw = request.form.get("width")
    width: int | None = None
    if width_raw not in (None, "", "0"):
        width = _validate_positive_int(width_raw, name="Width", min_value=64, max_value=2048)

    batch_dir = OUTPUT_DIR / f"frames_{uuid.uuid4().hex}"
    batch_dir.mkdir(parents=True, exist_ok=True)
    frame_paths: list[Path] = []
    output_path: Path | None = None

    try:
        for index, f in enumerate(files, start=1):
            if f.filename is None or f.filename == "":
                continue
            suffix = _allowed_image_suffix(f.filename)
            if suffix is None:
                abort(400, "Chỉ chấp nhận PNG/JPG/JPEG (trong danh sách ảnh)")
            frame_path = batch_dir / f"frame_{index:04d}{suffix}"
            f.save(frame_path)
            frame_paths.append(frame_path)

        if not frame_paths:
            abort(400, "Không có ảnh hợp lệ")

        output_path = _convert_images_to_animated_webp(frame_paths, fps=fps, width=width, loop=0)
    except HTTPException:
        shutil.rmtree(batch_dir, ignore_errors=True)
        raise
    except Exception as exc:  # pragma: no cover
        shutil.rmtree(batch_dir, ignore_errors=True)
        abort(500, f"Lỗi ffmpeg: {exc}")

    @after_this_request
    def cleanup(response):  # type: ignore
        shutil.rmtree(batch_dir, ignore_errors=True)
        if output_path is not None:
            output_path.unlink(missing_ok=True)
        return response

    return send_file(
        output_path,
        mimetype="image/webp",
        as_attachment=True,
        download_name=f"images_{len(frame_paths)}frames_{fps}fps.webp",
    )


@app.post("/mp4-to-animated-webp")
def mp4_to_animated_webp():
    file = request.files.get("file")
    if file is None or file.filename == "":
        abort(400, "Thiếu file MP4")

    fps = _validate_positive_int(request.form.get("fps"), name="FPS", min_value=1, max_value=60)
    width_raw = request.form.get("width")
    width: int | None = None
    if width_raw not in (None, "", "0"):
        width = _validate_positive_int(width_raw, name="Width", min_value=64, max_value=2048)

    duration_raw = request.form.get("duration")
    duration: int | None = None
    if duration_raw not in (None, "", "0"):
        duration = _validate_positive_int(
            duration_raw, name="Thời lượng", min_value=1, max_value=MAX_WEBP_DURATION
        )

    suffix = Path(file.filename).suffix or ".mp4"
    input_path = UPLOAD_DIR / f"{uuid.uuid4().hex}{suffix}"
    file.save(input_path)

    try:
        output_path = _convert_video_to_animated_webp(
            input_path, fps=fps, width=width, duration=duration, loop=0
        )
    except Exception as exc:  # pragma: no cover
        input_path.unlink(missing_ok=True)
        abort(500, f"Lỗi ffmpeg: {exc}")

    @after_this_request
    def cleanup(response):  # type: ignore
        input_path.unlink(missing_ok=True)
        output_path.unlink(missing_ok=True)
        return response

    return send_file(
        output_path,
        mimetype="image/webp",
        as_attachment=True,
        download_name=f"video_{fps}fps_{duration or 'full'}s.webp",
    )


@app.post("/gif-to-webp")
def gif_to_webp():
    file = request.files.get("file")
    if file is None or file.filename == "":
        abort(400, "Thiếu file GIF")

    if _allowed_gif_suffix(file.filename) is None:
        abort(400, "Chỉ chấp nhận GIF")

    fps = _validate_positive_int(request.form.get("fps"), name="FPS", min_value=1, max_value=60)
    width_raw = request.form.get("width")
    width: int | None = None
    if width_raw not in (None, "", "0"):
        width = _validate_positive_int(width_raw, name="Width", min_value=64, max_value=2048)

    duration_raw = request.form.get("duration")
    duration: int | None = None
    if duration_raw not in (None, "", "0"):
        duration = _validate_positive_int(
            duration_raw, name="Thời lượng", min_value=1, max_value=MAX_WEBP_DURATION
        )

    input_path = UPLOAD_DIR / f"{uuid.uuid4().hex}.gif"
    file.save(input_path)

    try:
        output_path = _convert_video_to_animated_webp(
            input_path, fps=fps, width=width, duration=duration, loop=0
        )
    except Exception as exc:  # pragma: no cover
        input_path.unlink(missing_ok=True)
        abort(500, f"Lỗi ffmpeg: {exc}")

    @after_this_request
    def cleanup(response):  # type: ignore
        input_path.unlink(missing_ok=True)
        output_path.unlink(missing_ok=True)
        return response

    return send_file(
        output_path,
        mimetype="image/webp",
        as_attachment=True,
        download_name=f"gif_{fps}fps_{duration or 'full'}s.webp",
    )


@app.post("/images-to-webp-zip")
def images_to_webp_zip():
    files = request.files.getlist("files")
    if not files:
        abort(400, "Thiếu danh sách ảnh (files)")

    batch_dir = OUTPUT_DIR / f"webp_batch_{uuid.uuid4().hex}"
    batch_dir.mkdir(parents=True, exist_ok=True)
    zip_path = batch_dir / "webp_images.zip"

    output_paths: list[Path] = []
    try:
        for index, f in enumerate(files, start=1):
            if f.filename is None or f.filename == "":
                continue
            suffix = _allowed_image_suffix(f.filename)
            if suffix is None:
                abort(400, "Chỉ chấp nhận PNG/JPG/JPEG (trong danh sách ảnh)")

            input_path = batch_dir / f"input_{index:04d}{suffix}"
            f.save(input_path)

            output_name = _safe_zip_entry_name(Path(f.filename).stem, index=index)
            output_path = batch_dir / output_name
            _convert_image_to_webp(input_path, lossless=(suffix == ".png"), output_path=output_path)
            output_paths.append(output_path)

        if not output_paths:
            abort(400, "Không có ảnh hợp lệ")

        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for output_path in output_paths:
                zf.write(output_path, arcname=output_path.name)
    except HTTPException:
        shutil.rmtree(batch_dir, ignore_errors=True)
        raise
    except Exception as exc:  # pragma: no cover
        shutil.rmtree(batch_dir, ignore_errors=True)
        abort(500, f"Lỗi ffmpeg/zip: {exc}")

    @after_this_request
    def cleanup(response):  # type: ignore
        shutil.rmtree(batch_dir, ignore_errors=True)
        return response

    return send_file(
        zip_path,
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"images_{len(output_paths)}_webp.zip",
    )


@app.post("/images-convert-zip")
def images_convert_zip():
    files = request.files.getlist("files")
    if not files:
        abort(400, "Thiếu danh sách ảnh (files)")

    target = (request.form.get("format") or "").strip().lower()
    if target == "jpeg":
        target = "jpg"
    if target not in {"webp", "png", "jpg"}:
        abort(400, "Thiếu/ sai format (webp/png/jpg)")

    width_raw = request.form.get("width")
    width: int | None = None
    if width_raw not in (None, "", "0"):
        width = _validate_positive_int(width_raw, name="Width", min_value=16, max_value=4096)

    quality_raw = request.form.get("quality")
    quality: int | None = None
    if target in {"webp", "jpg"} and quality_raw not in (None, "", "0"):
        quality = _validate_positive_int(quality_raw, name="Quality", min_value=1, max_value=100)

    lossless_override: bool | None = None
    if target == "webp" and request.form.get("lossless") is not None:
        lossless_override = _parse_bool(request.form.get("lossless"))

    batch_dir = OUTPUT_DIR / f"img_convert_{uuid.uuid4().hex}"
    batch_dir.mkdir(parents=True, exist_ok=True)
    zip_path = batch_dir / "converted_images.zip"

    output_paths: list[Path] = []
    try:
        for index, f in enumerate(files, start=1):
            if f.filename is None or f.filename == "":
                continue

            suffix = _allowed_static_image_suffix(f.filename)
            if suffix is None:
                abort(400, "Chỉ chấp nhận PNG/JPG/JPEG/WebP (trong danh sách ảnh)")

            input_path = batch_dir / f"input_{index:04d}{suffix}"
            f.save(input_path)

            output_ext = f".{target}"
            output_name = _safe_zip_entry_name_with_ext(Path(f.filename).stem, index=index, ext=output_ext)
            output_path = batch_dir / output_name

            lossless = False
            if target == "webp":
                if lossless_override is None:
                    lossless = suffix == ".png"
                else:
                    lossless = lossless_override

            _convert_image(
                input_path,
                target=target,
                width=width,
                quality=quality,
                lossless=lossless,
                output_path=output_path,
            )
            output_paths.append(output_path)

        if not output_paths:
            abort(400, "Không có ảnh hợp lệ")

        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for output_path in output_paths:
                zf.write(output_path, arcname=output_path.name)
    except HTTPException:
        shutil.rmtree(batch_dir, ignore_errors=True)
        raise
    except Exception as exc:  # pragma: no cover
        shutil.rmtree(batch_dir, ignore_errors=True)
        abort(500, f"Lỗi ffmpeg/zip: {exc}")

    @after_this_request
    def cleanup(response):  # type: ignore
        shutil.rmtree(batch_dir, ignore_errors=True)
        return response

    return send_file(
        zip_path,
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"images_{len(output_paths)}_{target}.zip",
    )


@app.post("/tgs-to-gif-zip")
def tgs_to_gif_zip():
    """Batch convert TGS files to GIF and return as ZIP."""
    files = request.files.getlist("files")
    if not files:
        abort(400, "Thiếu danh sách file TGS (files)")

    # Optional parameters
    width_raw = request.form.get("width")
    width: int | None = None
    if width_raw not in (None, "", "0"):
        width = _validate_positive_int(width_raw, name="Width", min_value=16, max_value=2048)

    quality_raw = request.form.get("quality")
    quality: int | None = None
    if quality_raw not in (None, "", "0"):
        quality = _validate_positive_int(quality_raw, name="Quality", min_value=1, max_value=100)

    fps_raw = request.form.get("fps")
    fps: int = 30  # default FPS
    if fps_raw not in (None, "", "0"):
        fps = _validate_positive_int(fps_raw, name="FPS", min_value=1, max_value=60)

    # Create batch directory
    batch_dir = OUTPUT_DIR / f"tgs_convert_{uuid.uuid4().hex}"
    batch_dir.mkdir(parents=True, exist_ok=True)
    zip_path = batch_dir / "converted_gifs.zip"

    output_paths: list[Path] = []
    try:
        for index, f in enumerate(files, start=1):
            if f.filename is None or f.filename == "":
                continue

            if not _allowed_tgs_suffix(f.filename):
                abort(400, "Chỉ chấp nhận file .tgs (Telegram sticker)")

            # Save input TGS file
            input_path = batch_dir / f"input_{index:04d}.tgs"
            f.save(input_path)

            # Generate output filename
            output_name = _safe_zip_entry_name_with_ext(Path(f.filename).stem, index=index, ext=".gif")
            output_path = batch_dir / output_name

            # Convert TGS to GIF
            _convert_tgs_to_gif(
                input_path,
                width=width,
                quality=quality,
                fps=fps,
                output_path=output_path,
            )
            output_paths.append(output_path)

        if not output_paths:
            abort(400, "Không có file TGS hợp lệ")

        # Create ZIP file
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for output_path in output_paths:
                zf.write(output_path, arcname=output_path.name)

    except HTTPException:
        shutil.rmtree(batch_dir, ignore_errors=True)
        raise
    except Exception as exc:
        shutil.rmtree(batch_dir, ignore_errors=True)
        abort(500, f"Lỗi chuyển đổi TGS: {exc}")

    # Cleanup after request
    @after_this_request
    def cleanup(response):  # type: ignore
        shutil.rmtree(batch_dir, ignore_errors=True)
        return response

    return send_file(
        zip_path,
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"tgs_to_gif_{len(output_paths)}.zip",
    )


@app.post("/batch-animated-resize-zip")
def batch_animated_resize_zip():
    """Batch resize WebP/GIF (including animated) with optional width, height, and size control."""
    files = request.files.getlist("files")
    if not files:
        abort(400, "Thiếu danh sách file (files)")

    # Optional width
    width_raw = request.form.get("width")
    width: int | None = None
    if width_raw not in (None, "", "0"):
        width = _validate_positive_int(width_raw, name="Width", min_value=16, max_value=4096)

    # Optional height
    height_raw = request.form.get("height")
    height: int | None = None
    if height_raw not in (None, "", "0"):
        height = _validate_positive_int(height_raw, name="Height", min_value=16, max_value=4096)

    # Optional target file size in KB
    target_size_raw = request.form.get("target_size_kb")
    target_size_kb: int | None = None
    if target_size_raw not in (None, "", "0"):
        target_size_kb = _validate_positive_int(
            target_size_raw, name="Target Size KB", min_value=1, max_value=10240
        )

    # Optional quality (for WebP)
    quality_raw = request.form.get("quality")
    quality: int | None = None
    if quality_raw not in (None, "", "0"):
        quality = _validate_positive_int(quality_raw, name="Quality", min_value=1, max_value=100)

    batch_dir = OUTPUT_DIR / f"animated_resize_{uuid.uuid4().hex}"
    batch_dir.mkdir(parents=True, exist_ok=True)
    zip_path = batch_dir / "resized_animated.zip"

    output_paths: list[Path] = []
    try:
        for index, f in enumerate(files, start=1):
            if f.filename is None or f.filename == "":
                continue

            # Check if it's WebP or GIF
            suffix = Path(f.filename).suffix.lower()
            if suffix not in {".webp", ".gif"}:
                abort(400, "Chỉ chấp nhận WebP hoặc GIF")

            input_path = batch_dir / f"input_{index:04d}{suffix}"
            f.save(input_path)

            output_name = _safe_zip_entry_name_with_ext(
                Path(f.filename).stem, index=index, ext=suffix
            )
            output_path = batch_dir / output_name

            # Resize with optional parameters
            _resize_animated_media(
                input_path,
                width=width,
                height=height,
                quality=quality,
                target_size_kb=target_size_kb,
                output_path=output_path,
            )
            output_paths.append(output_path)

        if not output_paths:
            abort(400, "Không có file hợp lệ")

        # Create ZIP file
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for output_path in output_paths:
                zf.write(output_path, arcname=output_path.name)

    except HTTPException:
        shutil.rmtree(batch_dir, ignore_errors=True)
        raise
    except Exception as exc:
        shutil.rmtree(batch_dir, ignore_errors=True)
        abort(500, f"Lỗi xử lý: {exc}")

    @after_this_request
    def cleanup(response):  # type: ignore
        shutil.rmtree(batch_dir, ignore_errors=True)
        return response

    return send_file(
        zip_path,
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"resized_{len(output_paths)}_animated.zip",
    )


@app.post("/webp-resize-zip")
def webp_resize_zip():
    """Batch convert WebP files with resize and target file size control."""
    files = request.files.getlist("files")
    if not files:
        abort(400, "Thiếu danh sách file WebP (files)")

    # Target format (default to webp)
    target = (request.form.get("format") or "webp").strip().lower()
    if target == "jpeg":
        target = "jpg"
    if target not in {"webp", "png", "jpg"}:
        abort(400, "Định dạng output không hợp lệ (format: webp/png/jpg)")

    # Resize width (required)
    width_raw = request.form.get("width")
    width: int | None = None
    if width_raw not in (None, "", "0"):
        width = _validate_positive_int(width_raw, name="Width", min_value=16, max_value=4096)

    # Target file size in KB (optional)
    target_size_raw = request.form.get("target_size_kb")
    target_size_kb: int | None = None
    if target_size_raw not in (None, "", "0"):
        target_size_kb = _validate_positive_int(
            target_size_raw, name="Target Size KB", min_value=1, max_value=10240
        )

    # Quality (optional, used as starting point if target_size is set)
    quality_raw = request.form.get("quality")
    quality: int | None = None
    if quality_raw not in (None, "", "0"):
        quality = _validate_positive_int(quality_raw, name="Quality", min_value=1, max_value=100)

    batch_dir = OUTPUT_DIR / f"webp_resize_{uuid.uuid4().hex}"
    batch_dir.mkdir(parents=True, exist_ok=True)
    zip_path = batch_dir / "resized_images.zip"

    output_paths: list[Path] = []
    try:
        for index, f in enumerate(files, start=1):
            if f.filename is None or f.filename == "":
                continue

            suffix = _allowed_static_image_suffix(f.filename)
            if suffix is None:
                abort(400, "Chỉ chấp nhận PNG/JPG/JPEG/WebP")

            input_path = batch_dir / f"input_{index:04d}{suffix}"
            f.save(input_path)

            output_ext = f".{target}"
            output_name = _safe_zip_entry_name_with_ext(
                Path(f.filename).stem, index=index, ext=output_ext
            )
            output_path = batch_dir / output_name

            # Convert with size constraints
            _convert_image(
                input_path,
                target=target,
                width=width,
                quality=quality,
                lossless=False,
                output_path=output_path,
                target_size_kb=target_size_kb,
            )
            output_paths.append(output_path)

        if not output_paths:
            abort(400, "Không có file hợp lệ")

        # Create ZIP file
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for output_path in output_paths:
                zf.write(output_path, arcname=output_path.name)

    except HTTPException:
        shutil.rmtree(batch_dir, ignore_errors=True)
        raise
    except Exception as exc:
        shutil.rmtree(batch_dir, ignore_errors=True)
        abort(500, f"Lỗi chuyển đổi: {exc}")

    @after_this_request
    def cleanup(response):  # type: ignore
        shutil.rmtree(batch_dir, ignore_errors=True)
        return response

    return send_file(
        zip_path,
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"resized_{len(output_paths)}_{target}.zip",
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
