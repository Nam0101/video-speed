from __future__ import annotations

import subprocess
import shutil
import uuid
import zipfile
import re
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
            <title>Đổi FPS Video</title>
            <style>
                :root {
                    --bg: #0f172a;
                    --card: #111827;
                    --accent: #22d3ee;
                    --text: #e5e7eb;
                    --muted: #94a3b8;
                }
                body {
                    margin: 0; padding: 0;
                    font-family: "Inter", system-ui, -apple-system, sans-serif;
                    background: radial-gradient(circle at 20% 20%, rgba(34,211,238,0.12), transparent 25%),
                                radial-gradient(circle at 80% 10%, rgba(236,72,153,0.12), transparent 22%),
                                var(--bg);
                    color: var(--text);
                    min-height: 100vh;
                    display: flex; align-items: center; justify-content: center;
                }
                .card {
                    width: min(1100px, 95vw);
                    background: var(--card);
                    border: 1px solid rgba(255,255,255,0.05);
                    border-radius: 18px;
                    box-shadow: 0 25px 80px rgba(0,0,0,0.45);
                    padding: 28px 30px 32px;
                }
                h1 { margin: 0 0 12px; font-weight: 700; letter-spacing: -0.01em; }
                p { margin: 0 0 16px; color: var(--muted); }
                .grid { display: grid; grid-template-columns: 320px 1fr; gap: 20px; align-items: start; }
                .control {
                    padding: 14px 16px;
                    border: 1px dashed rgba(255,255,255,0.15);
                    border-radius: 14px;
                    background: rgba(255,255,255,0.02);
                }
                label { display: block; font-weight: 600; margin-bottom: 8px; }
                input[type=file] {
                    width: 100%; padding: 10px; border-radius: 10px;
                    border: 1px solid rgba(255,255,255,0.2);
                    background: rgba(255,255,255,0.04);
                    color: var(--text);
                }
                button {
                    margin-top: 10px;
                    width: 100%;
                    padding: 12px 14px;
                    border-radius: 12px;
                    border: none;
                    font-weight: 700;
                    letter-spacing: 0.01em;
                    background: linear-gradient(90deg, #22d3ee, #8b5cf6);
                    color: #0b1021;
                    cursor: pointer;
                }
                button:disabled { opacity: 0.5; cursor: not-allowed; }
                .slider-row { display: flex; align-items: center; gap: 10px; margin-top: 14px; }
                input[type=range] { flex: 1; }
                .pill { padding: 6px 10px; border-radius: 999px; background: rgba(255,255,255,0.08); font-weight: 600; }
                .icon-btn {
                    width: 40px;
                    height: 40px;
                    border-radius: 12px;
                    border: 1px solid rgba(255,255,255,0.2);
                    background: rgba(255,255,255,0.06);
                    color: var(--text);
                    font-size: 18px;
                    cursor: pointer;
                }
                .icon-btn:disabled { opacity: 0.4; cursor: not-allowed; }
                .status { margin-top: 10px; color: var(--muted); min-height: 20px; font-size: 14px; }
                video { width: 100%; max-height: 520px; background: black; border-radius: 14px; border: 1px solid rgba(255,255,255,0.08); }
                img.preview-img { width: 100%; max-height: 520px; background: rgba(0,0,0,0.35); object-fit: contain; border-radius: 14px; border: 1px solid rgba(255,255,255,0.08); }
                .tag { font-size: 12px; text-transform: uppercase; letter-spacing: 0.08em; color: var(--muted); }
                .section { margin-top: 22px; padding-top: 18px; border-top: 1px solid rgba(255,255,255,0.06); }
                h2 { margin: 0 0 10px; font-size: 18px; letter-spacing: -0.01em; }
                .small { font-size: 13px; color: var(--muted); }
                .row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
                .row-3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; }
                .tabs { display: inline-flex; gap: 8px; background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08); padding: 6px; border-radius: 999px; }
                .tab-btn {
                    padding: 8px 12px;
                    border-radius: 999px;
                    border: 1px solid transparent;
                    background: transparent;
                    color: var(--muted);
                    font-weight: 700;
                    cursor: pointer;
                    width: auto;
                    margin-top: 0;
                }
                .tab-btn.active {
                    color: var(--text);
                    background: rgba(255,255,255,0.08);
                    border-color: rgba(255,255,255,0.12);
                }
                .hidden { display: none !important; }
                input[type=number], select {
                    width: 100%;
                    padding: 10px;
                    border-radius: 10px;
                    border: 1px solid rgba(255,255,255,0.2);
                    background: rgba(255,255,255,0.04);
                    color: var(--text);
                }
                @media (max-width: 900px) { .grid { grid-template-columns: 1fr; } }
                @media (max-width: 900px) { .row, .row-3 { grid-template-columns: 1fr; } }
            </style>
        </head>
        <body>
            <div class="card">
                <div style="display:flex; align-items:center; justify-content: space-between; gap: 10px; flex-wrap: wrap;">
                    <div>
                        <div class="tag">Video tool</div>
                        <h1>Đổi FPS &amp; xem preview tức thì</h1>
                        <p>Tải video, kéo thanh FPS và xem kết quả mới ngay lập tức.</p>
                    </div>
                    <div style="display:flex; align-items:center; gap: 10px; flex-wrap: wrap; justify-content: flex-end;">
                        <div class="tabs" role="tablist" aria-label="Tools">
                            <button class="tab-btn active" id="tabVideo" type="button" role="tab" aria-selected="true">Video</button>
                            <button class="tab-btn" id="tabWebp" type="button" role="tab" aria-selected="false">WebP</button>
                        </div>
                        <div class="pill" id="currentFps">Chưa có video</div>
                    </div>
                </div>

                <div id="videoSection" class="grid" style="margin-top: 16px;">
                    <div class="control">
                        <label for="file">Chọn video</label>
                        <input id="file" type="file" accept="video/*" />
                        <button id="uploadBtn">Tải lên</button>
                        <div class="slider-row">
                            <label for="fpsRange" style="margin:0;">FPS</label>
                            <button class="icon-btn" id="fpsDown" type="button">−</button>
                            <input id="fpsRange" type="range" min="{{min_fps}}" max="{{max_fps}}" step="1" value="24" disabled />
                            <button class="icon-btn" id="fpsUp" type="button">+</button>
                            <div class="pill" id="fpsValue">24</div>
                        </div>
                        <div style="margin-top: 14px;">
                            <label for="durationInput" style="margin:0;">Thời lượng (giây)</label>
                            <input id="durationInput" type="number" min="1" max="{{max_duration}}" step="1" value="5" disabled
                                   style="width:100%; padding:10px; border-radius:10px; border:1px solid rgba(255,255,255,0.2); background: rgba(255,255,255,0.04); color: var(--text);" />
                            <button id="exportBtn" style="margin-top:10px;" disabled>Export &amp; tải về</button>
                        </div>
                        <div class="status" id="status">Chưa có video.</div>
                    </div>

                    <div>
                        <video id="preview" controls playsinline loop muted></video>
                    </div>
                </div>

                <div id="webpSection" class="section hidden">
                    <div style="display:flex; align-items:baseline; justify-content: space-between; gap: 10px; flex-wrap: wrap;">
                        <div>
                            <div class="tag">WebP tools</div>
                            <h2>PNG/JPG → WebP, GIF → WebP, batch ảnh → ZIP WebP, nhiều ảnh → WebP động, MP4 → WebP động</h2>
                            <div class="small">Tất cả chuyển đổi dùng ffmpeg. WebP động sẽ tải về dưới dạng <code>.webp</code>.</div>
                        </div>
                        <div class="pill" id="webpInfo">Sẵn sàng</div>
                    </div>

                    <div class="grid" style="margin-top: 14px;">
                        <div class="control">
                            <label for="imgFile">1) Ảnh (PNG/JPG) → WebP</label>
                            <input id="imgFile" type="file" accept="image/png,image/jpeg" />
                            <button id="imgConvertBtn" type="button">Convert &amp; tải về</button>
                            <div class="status" id="imgStatus">Chưa chọn ảnh.</div>

                            <div style="height: 12px;"></div>
                            <label for="imgFiles">2) Nhiều ảnh → WebP động</label>
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

                            <div style="height: 12px;"></div>
                            <label for="mp4File">3) MP4 → WebP động</label>
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

                            <div style="height: 12px;"></div>
                            <label for="gifFile">4) GIF → WebP động</label>
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

                            <div style="height: 12px;"></div>
                            <label for="batchImgFiles">5) Batch PNG/JPG → ZIP WebP</label>
                            <input id="batchImgFiles" type="file" accept="image/png,image/jpeg" multiple />
                            <button id="batchConvertBtn" type="button">Convert batch → ZIP</button>
                            <div class="status" id="batchStatus">Chưa chọn nhiều ảnh.</div>

                            <div style="height: 12px;"></div>
                            <label for="batch2ImgFiles">6) Batch convert ảnh → ZIP (WebP/PNG/JPG)</label>
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
                            <button id="batch2ConvertBtn" type="button">Convert ảnh → ZIP</button>
                            <div class="status" id="batch2Status">Chưa chọn nhiều ảnh.</div>
                        </div>

                        <div>
                            <img id="webpPreview" class="preview-img" alt="WebP preview" />
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
                const currentFps = document.getElementById('currentFps');
                const durationInput = document.getElementById('durationInput');
                const exportBtn = document.getElementById('exportBtn');

                const tabVideo = document.getElementById('tabVideo');
                const tabWebp = document.getElementById('tabWebp');
                const videoSection = document.getElementById('videoSection');
                const webpSection = document.getElementById('webpSection');

                const webpInfo = document.getElementById('webpInfo');
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

                let fileId = null;
                let debounceTimer = null;
                let activeController = null;

                function setStatus(text) { statusEl.textContent = text; }
                function setWebpInfo(text) { webpInfo.textContent = text; }

                function setActiveTab(which) {
                    const isVideo = which === 'video';
                    tabVideo.classList.toggle('active', isVideo);
                    tabWebp.classList.toggle('active', !isVideo);
                    tabVideo.setAttribute('aria-selected', String(isVideo));
                    tabWebp.setAttribute('aria-selected', String(!isVideo));
                    videoSection.classList.toggle('hidden', !isVideo);
                    webpSection.classList.toggle('hidden', isVideo);
                }
                tabVideo.addEventListener('click', () => setActiveTab('video'));
                tabWebp.addEventListener('click', () => setActiveTab('webp'));

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
                        setStatus('Tải lên thành công. Kéo thanh FPS để xem preview.');
                        currentFps.textContent = `Gốc: ${data.original_fps ?? '—'} fps`;
                    } catch (err) {
                        console.error(err);
                        setStatus('Tải lên thất bại: ' + err.message);
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
                    setWebpInfo('Đang xử lý…');
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
                        setWebpInfo('Hoàn tất');
                    } catch (err) {
                        console.error(err);
                        imgStatus.textContent = 'Lỗi: ' + err.message;
                        setWebpInfo('Lỗi');
                    }
                });

                imgAnimBtn.addEventListener('click', async () => {
                    const files = Array.from(imgFiles.files || []);
                    if (files.length === 0) { imgAnimStatus.textContent = 'Hãy chọn nhiều ảnh.'; return; }
                    if (files.length === 1) { imgAnimStatus.textContent = 'Chọn ít nhất 2 ảnh để thấy “động”.'; }

                    const fps = Number(imgAnimFps.value || 10);
                    const width = Number(imgAnimWidth.value || 640);

                    imgAnimStatus.textContent = 'Đang tạo WebP động...';
                    setWebpInfo('Đang xử lý…');
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
                        setWebpInfo('Hoàn tất');
                    } catch (err) {
                        console.error(err);
                        imgAnimStatus.textContent = 'Lỗi: ' + err.message;
                        setWebpInfo('Lỗi');
                    }
                });

                mp4ToWebpBtn.addEventListener('click', async () => {
                    const file = mp4File.files?.[0];
                    if (!file) { mp4WebpStatus.textContent = 'Hãy chọn MP4.'; return; }

                    const fps = Number(mp4WebpFps.value || 15);
                    const width = Number(mp4WebpWidth.value || 640);
                    const duration = Number(mp4WebpDuration.value || 0);

                    mp4WebpStatus.textContent = 'Đang convert MP4 → WebP...';
                    setWebpInfo('Đang xử lý…');
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
                        setWebpInfo('Hoàn tất');
                    } catch (err) {
                        console.error(err);
                        mp4WebpStatus.textContent = 'Lỗi: ' + err.message;
                        setWebpInfo('Lỗi');
                    }
                });

                gifToWebpBtn.addEventListener('click', async () => {
                    const file = gifFile.files?.[0];
                    if (!file) { gifWebpStatus.textContent = 'Hãy chọn GIF.'; return; }

                    const fps = Number(gifWebpFps.value || 15);
                    const width = Number(gifWebpWidth.value || 640);
                    const duration = Number(gifWebpDuration.value || 0);

                    gifWebpStatus.textContent = 'Đang convert GIF → WebP...';
                    setWebpInfo('Đang xử lý…');
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
                        setWebpInfo('Hoàn tất');
                    } catch (err) {
                        console.error(err);
                        gifWebpStatus.textContent = 'Lỗi: ' + err.message;
                        setWebpInfo('Lỗi');
                    }
                });

                batchConvertBtn.addEventListener('click', async () => {
                    const files = Array.from(batchImgFiles.files || []);
                    if (files.length === 0) { batchStatus.textContent = 'Hãy chọn nhiều ảnh.'; return; }

                    batchStatus.textContent = `Đang convert ${files.length} ảnh...`;
                    setWebpInfo('Đang xử lý…');
                    const form = new FormData();
                    for (const f of files) form.append('files', f);

                    try {
                        const res = await fetch('/images-to-webp-zip', { method: 'POST', body: form });
                        if (!res.ok) throw new Error(await res.text());
                        const blob = await res.blob();
                        downloadBlob(blob, `images_${files.length}_webp.zip`);
                        batchStatus.textContent = `Xong (${files.length} ảnh).`;
                        setWebpInfo('Hoàn tất');
                    } catch (err) {
                        console.error(err);
                        batchStatus.textContent = 'Lỗi: ' + err.message;
                        setWebpInfo('Lỗi');
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
                    setWebpInfo('Đang xử lý…');

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
                        setWebpInfo('Hoàn tất');
                    } catch (err) {
                        console.error(err);
                        batch2Status.textContent = 'Lỗi: ' + err.message;
                        setWebpInfo('Lỗi');
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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
