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
from datetime import datetime
import sqlite3

from flask import (
    Flask,
    abort,
    after_this_request,
    jsonify,
    render_template_string,
    request,
    send_file,
    Response,
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
DB_PATH = DATA_DIR / "logs.db"

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    try:
        conn = get_db_connection()
        conn.execute('''
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                event_name TEXT,
                device_name TEXT,
                version_code TEXT,
                params TEXT
            )
        ''')
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"DB Init Error: {e}")

# Initialize DB on start
init_db()


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
    return f"{stem}.webp"


def _safe_zip_entry_name_with_ext(raw_stem: str, *, index: int, ext: str) -> str:
    stem = (raw_stem or "").strip() or f"image_{index:04d}"
    stem = _ZIP_NAME_SAFE_RE.sub("_", stem).strip("._-") or f"image_{index:04d}"
    ext = (ext or "").lower().strip()
    if not ext.startswith("."):
        ext = f".{ext}"
    if ext not in {".webp", ".png", ".jpg", ".gif"}:
        ext = ".png"
    return f"{stem}{ext}"


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

        # Map width to renderer DPI (96 is the base scale).
        dpi = 96
        if width:
            scale = width / animation.width if animation.width else 1
            dpi = max(1, int(round(96 * scale)))

        # Map requested fps to skip_frames (renderer uses original frame rate).
        skip_frames = 1
        if fps and animation.frame_rate:
            skip_frames = max(1, int(round(animation.frame_rate / fps)))

        # Export to GIF
        export_gif(
            animation,
            str(output_path),
            dpi=dpi,
            skip_frames=skip_frames,
        )

        return output_path

    except Exception as e:
        abort(500, f"Lỗi chuyển đổi TGS sang GIF: {str(e)}")


def _convert_webm_to_gif(
    input_path: Path,
    *,
    fps: int = 15,
    width: int = 640,
    output_path: Path | None = None,
) -> Path:
    if output_path is None:
        output_path = OUTPUT_DIR / f"{uuid.uuid4().hex}.gif"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Palette generation for better quality
    # filters: fps -> scale -> split to generate palette -> paletteuse
    vf = f"fps={fps},scale={width}:-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse"

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(input_path),
        "-vf",
        vf,
        str(output_path),
    ]
    _run_ffmpeg(cmd)
    return output_path


# ---------------------------- Routes --------------------------------------

@app.get("/")
def index():
    return render_template_string(
        r"""
        <!doctype html>
        <html lang="vi">
        <head>
            <meta charset="UTF-8" />
            <meta name="viewport" content="width=device-width, initial-scale=1" />
            <title>Media Converter Pro</title>
            <meta name="description" content="Công cụ chuyển đổi video, ảnh và sticker chuyên nghiệp - Convert MP4, WebP, GIF, TGS" />
            <link rel="preconnect" href="https://fonts.googleapis.com">
            <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
            <link href="https://fonts.googleapis.com/css2?family=Open+Sans:wght@300;400;500;600;700&family=Poppins:wght@500;600;700;800&display=swap" rel="stylesheet">
            <style>
                *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
                
                html { scroll-behavior: smooth; }
                
                @media (prefers-reduced-motion: reduce) {
                    *, *::before, *::after {
                        animation-duration: 0.01ms !important;
                        animation-iteration-count: 1 !important;
                        transition-duration: 0.01ms !important;
                        scroll-behavior: auto !important;
                    }
                }
                
                :root {
                    /* Soft UI Evolution - Color Palette */
                    --bg-primary: #0A0E27;
                    --bg-secondary: #111827;
                    --bg-elevated: #1F2937;
                    
                    --surface: rgba(17, 24, 39, 0.85);
                    --surface-hover: rgba(31, 41, 55, 0.9);
                    --border: rgba(255, 255, 255, 0.06);
                    --border-hover: rgba(255, 255, 255, 0.12);
                    
                    --primary: #3B82F6;
                    --primary-light: #60A5FA;
                    --primary-dark: #2563EB;
                    --secondary: #60A5FA;
                    --accent: #10B981;
                    --cta: #F97316;
                    --cta-hover: #EA580C;
                    
                    --text-primary: #F8FAFC;
                    --text-secondary: #CBD5E1;
                    --text-muted: #94A3B8;
                    --text-dim: #64748B;
                    
                    --success: #10B981;
                    --warning: #F59E0B;
                    --error: #EF4444;
                    
                    --input-bg: rgba(15, 23, 42, 0.7);
                    --input-border: rgba(148, 163, 184, 0.15);
                    --input-focus: rgba(59, 130, 246, 0.4);
                    
                    /* Soft UI Shadows */
                    --shadow-sm: 0 2px 8px rgba(0, 0, 0, 0.15);
                    --shadow-md: 0 8px 24px rgba(0, 0, 0, 0.2);
                    --shadow-lg: 0 16px 48px rgba(0, 0, 0, 0.25);
                    --shadow-glow: 0 0 40px rgba(59, 130, 246, 0.15);
                    
                    /* Typography */
                    --font-heading: 'Poppins', -apple-system, BlinkMacSystemFont, sans-serif;
                    --font-body: 'Open Sans', -apple-system, BlinkMacSystemFont, sans-serif;
                    
                    /* Z-Index Scale */
                    --z-base: 1;
                    --z-elevated: 10;
                    --z-sticky: 20;
                    --z-dropdown: 30;
                    --z-modal: 50;
                    
                    /* Transitions */
                    --transition-fast: 150ms ease;
                    --transition-normal: 250ms ease;
                    --transition-slow: 350ms ease;
                }
                
                body {
                    margin: 0;
                    padding: 0;
                    font-family: var(--font-body);
                    font-size: 15px;
                    font-weight: 400;
                    background: var(--bg-primary);
                    background-image: 
                        radial-gradient(ellipse 80% 50% at 20% 30%, rgba(59, 130, 246, 0.08), transparent),
                        radial-gradient(ellipse 60% 40% at 80% 70%, rgba(249, 115, 22, 0.05), transparent);
                    background-attachment: fixed;
                    color: var(--text-primary);
                    min-height: 100vh;
                    line-height: 1.65;
                    -webkit-font-smoothing: antialiased;
                    -moz-osx-font-smoothing: grayscale;
                }
                
                /* Icon System - Lucide SVG Icons */
                .icon {
                    width: 20px;
                    height: 20px;
                    stroke: currentColor;
                    stroke-width: 2;
                    stroke-linecap: round;
                    stroke-linejoin: round;
                    fill: none;
                    flex-shrink: 0;
                }
                .icon-sm { width: 16px; height: 16px; }
                .icon-lg { width: 24px; height: 24px; }
                .icon-xl { width: 32px; height: 32px; }
                
                .container {
                    max-width: 1440px;
                    margin: 0 auto;
                    padding: 1.5rem 1rem;
                    position: relative;
                    z-index: var(--z-base);
                }
                
                @media (min-width: 768px) {
                    .container { padding: 2rem 1.5rem; }
                }
                
                @media (min-width: 1024px) {
                    .container { padding: 2rem; }
                }
                
                /* Header */
                .header {
                    text-align: center;
                    margin-bottom: 2rem;
                    animation: fadeInDown 0.5s var(--transition-normal);
                }
                
                .header h1 {
                    margin: 0 0 0.5rem;
                    font-size: clamp(1.75rem, 4vw, 2.5rem);
                    font-weight: 700;
                    font-family: var(--font-heading);
                    background: linear-gradient(135deg, var(--primary-light) 0%, var(--cta) 100%);
                    -webkit-background-clip: text;
                    -webkit-text-fill-color: transparent;
                    background-clip: text;
                    letter-spacing: -0.02em;
                }
                
                .header-subtitle {
                    margin: 0;
                    color: var(--text-muted);
                    font-size: 1rem;
                    font-weight: 400;
                }
                
                /* Card Component */
                .card {
                    background: var(--surface);
                    backdrop-filter: blur(24px);
                    -webkit-backdrop-filter: blur(24px);
                    border: 1px solid var(--border);
                    border-radius: 1.25rem;
                    padding: 1.5rem;
                    box-shadow: var(--shadow-lg);
                    margin-bottom: 1.25rem;
                    transition: transform var(--transition-normal), box-shadow var(--transition-normal);
                    animation: fadeInUp 0.5s ease-out;
                }
                
                .card:hover {
                    box-shadow: var(--shadow-lg), var(--shadow-glow);
                }
                
                /* Grid Layout */
                .grid { 
                    display: grid; 
                    grid-template-columns: 400px 1fr; 
                    gap: 1.25rem; 
                    align-items: start; 
                }
                
                @media (max-width: 1024px) {
                    .grid { grid-template-columns: 1fr; }
                }
                
                /* Controls Panel */
                .controls-panel {
                    background: rgba(15, 23, 42, 0.5);
                    border: 1px solid var(--border);
                    border-radius: 1rem;
                    padding: 1.25rem;
                    max-height: 80vh;
                    overflow-y: auto;
                    overflow-x: hidden;
                }
                
                .controls-panel::-webkit-scrollbar { width: 6px; }
                .controls-panel::-webkit-scrollbar-track { background: transparent; }
                .controls-panel::-webkit-scrollbar-thumb { 
                    background: rgba(255,255,255,0.1); 
                    border-radius: 3px;
                }
                .controls-panel::-webkit-scrollbar-thumb:hover { 
                    background: rgba(255,255,255,0.2); 
                }
                
                /* Feature Card */
                .feature-card {
                    background: rgba(255, 255, 255, 0.02);
                    border: 1px solid var(--border);
                    border-left: 3px solid var(--primary);
                    border-radius: 0.75rem;
                    padding: 1.25rem;
                    margin-bottom: 1rem;
                    transition: all var(--transition-normal);
                }
                
                .feature-card:hover {
                    background: rgba(255, 255, 255, 0.04);
                    border-left-color: var(--cta);
                    box-shadow: var(--shadow-sm);
                }
                
                .feature-title {
                    font-size: 0.9375rem;
                    font-weight: 600;
                    font-family: var(--font-heading);
                    color: var(--primary-light);
                    margin: 0 0 0.875rem;
                    display: flex;
                    align-items: center;
                    gap: 0.625rem;
                /* Form Elements */
                label {
                    display: block;
                    font-weight: 600;
                    font-size: 0.8125rem;
                    font-family: var(--font-body);
                    margin-bottom: 0.375rem;
                    color: var(--text-secondary);
                    letter-spacing: 0.01em;
                }
                
                input[type=file] {
                    width: 100%;
                    padding: 0.625rem 0.875rem;
                    border-radius: 0.625rem;
                    border: 2px dashed var(--input-border);
                    background: var(--input-bg);
                    color: var(--text-primary);
                    font-size: 0.875rem;
                    font-family: var(--font-body);
                    cursor: pointer;
                    transition: all var(--transition-fast);
                }
                
                input[type=file]:hover {
                    border-color: var(--primary);
                    background: rgba(59, 130, 246, 0.08);
                }
                
                input[type=file]:focus {
                    outline: none;
                    border-color: var(--primary);
                    box-shadow: 0 0 0 3px var(--input-focus);
                }
                
                /* Drop Zone */
                .drop-zone {
                    position: relative;
                    min-height: 100px;
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    justify-content: center;
                    padding: 1.25rem;
                    border-radius: 0.75rem;
                    border: 2px dashed var(--input-border);
                    background: var(--input-bg);
                    transition: all var(--transition-fast);
                    cursor: pointer;
                }
                
                .drop-zone:hover {
                    border-color: var(--primary);
                    background: rgba(59, 130, 246, 0.06);
                }
                
                .drop-zone.drag-over {
                    border-color: var(--accent);
                    background: rgba(16, 185, 129, 0.12);
                    box-shadow: var(--shadow-md);
                }
                
                .drop-zone-icon {
                    margin-bottom: 0.5rem;
                    color: var(--text-muted);
                }
                
                .drop-zone-text {
                    font-size: 0.875rem;
                    font-weight: 600;
                    font-family: var(--font-body);
                    color: var(--text-primary);
                    margin-bottom: 0.125rem;
                }
                
                .drop-zone-hint {
                    font-size: 0.75rem;
                    color: var(--text-dim);
                }
                
                .drop-zone input[type=file] {
                    position: absolute;
                    inset: 0;
                    opacity: 0;
                    cursor: pointer;
                }
                
                /* File List */
                .file-list {
                    margin-top: 0.625rem;
                    padding: 0.625rem;
                    background: rgba(255, 255, 255, 0.02);
                    border-radius: 0.5rem;
                    border: 1px solid var(--border);
                }
                
                .file-item {
                    display: flex;
                    align-items: center;
                    gap: 0.5rem;
                    padding: 0.375rem 0.5rem;
                    background: rgba(255, 255, 255, 0.02);
                    border-radius: 0.375rem;
                    margin-bottom: 0.25rem;
                    font-size: 0.8125rem;
                }
                
                .file-item:last-child { margin-bottom: 0; }
                
                .file-item-icon { color: var(--text-muted); }
                
                .file-item-name {
                    flex: 1;
                    white-space: nowrap;
                    overflow: hidden;
                    text-overflow: ellipsis;
                    color: var(--text-secondary);
                }
                
                .file-item-size {
                    color: var(--text-dim);
                    font-size: 0.6875rem;
                    font-weight: 500;
                }
                
                /* Number Input & Select */
                input[type=number], select {
                    width: 100%;
                    height: 2.375rem;
                    padding: 0 0.875rem;
                    border-radius: 0.625rem;
                    border: 1px solid var(--input-border);
                    background: var(--input-bg);
                    color: var(--text-primary);
                    font-size: 0.875rem;
                    font-weight: 500;
                    font-family: var(--font-body);
                    transition: all var(--transition-fast);
                }
                
                input[type=number]:focus, select:focus {
                    outline: none;
                    border-color: var(--primary);
                    box-shadow: 0 0 0 3px var(--input-focus);
                }
                
                input[type=number]:disabled, select:disabled {
                    opacity: 0.5;
                    cursor: not-allowed;
                    background: rgba(15, 23, 42, 0.4);
                }
                
                /* Buttons */
                button {
                    width: 100%;
                    height: 2.625rem;
                    padding: 0 1.125rem;
                    border-radius: 0.625rem;
                    border: none;
                    font-weight: 600;
                    font-size: 0.875rem;
                    font-family: var(--font-body);
                    letter-spacing: 0.01em;
                    background: var(--cta);
                    color: white;
                    cursor: pointer;
                    transition: all var(--transition-fast);
                    box-shadow: 0 2px 8px rgba(249, 115, 22, 0.25);
                    margin-top: 0.625rem;
                    display: inline-flex;
                    align-items: center;
                    justify-content: center;
                    gap: 0.5rem;
                }
                
                button:hover {
                    background: var(--cta-hover);
                    box-shadow: 0 4px 12px rgba(249, 115, 22, 0.35);
                }
                
                button:active {
                    transform: translateY(1px);
                }
                
                button:disabled {
                    opacity: 0.5;
                    cursor: not-allowed;
                    box-shadow: none;
                }
                
                button:focus-visible {
                    outline: 2px solid var(--cta);
                    outline-offset: 2px;
                }
                
                /* Slider Row */
                .slider-row { 
                    display: flex; 
                    align-items: center; 
                    gap: 0.75rem; 
                    margin-top: 1rem; 
                }
                
                input[type=range] {
                    flex: 1;
                    height: 6px;
                    border-radius: 3px;
                    background: rgba(148, 163, 184, 0.2);
                    outline: none;
                    -webkit-appearance: none;
                    cursor: pointer;
                }
                
                input[type=range]::-webkit-slider-thumb {
                    -webkit-appearance: none;
                    width: 18px;
                    height: 18px;
                    border-radius: 50%;
                    background: var(--primary);
                    cursor: pointer;
                    box-shadow: 0 2px 8px rgba(59, 130, 246, 0.4);
                    transition: transform var(--transition-fast);
                }
                
                input[type=range]::-webkit-slider-thumb:hover { 
                    transform: scale(1.15); 
                }
                
                input[type=range]:focus-visible::-webkit-slider-thumb {
                    box-shadow: 0 0 0 3px var(--input-focus);
                }
                
                /* Pill Badge */
                .pill {
                    padding: 0.5rem 1rem;
                    border-radius: 999px;
                    background: rgba(59, 130, 246, 0.12);
                    color: var(--primary-light);
                    font-weight: 600;
                    font-size: 0.875rem;
                    border: 1px solid rgba(59, 130, 246, 0.2);
                    font-family: var(--font-body);
                }
                
                /* Icon Button */
                .icon-btn {
                    width: 40px;
                    height: 40px;
                    border-radius: 0.625rem;
                    border: 1px solid var(--input-border);
                    background: var(--input-bg);
                    color: var(--text-primary);
                    font-size: 1.25rem;
                    cursor: pointer;
                    transition: all var(--transition-fast);
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    margin-top: 0;
                    box-shadow: none;
                }
                
                .icon-btn:hover {
                    background: rgba(59, 130, 246, 0.15);
                    border-color: var(--primary);
                }
                
                .icon-btn:disabled { 
                    opacity: 0.4; 
                    cursor: not-allowed; 
                }
                
                /* Status Message */
                .status {
                    margin-top: 0.75rem;
                    padding: 0.75rem 1rem;
                    border-radius: 0.625rem;
                    background: rgba(148, 163, 184, 0.08);
                    color: var(--text-muted);
                    font-size: 0.8125rem;
                    border-left: 3px solid var(--text-dim);
                    min-height: 1.25rem;
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
                
                /* Preview Container */
                .preview-container {
                    background: rgba(0, 0, 0, 0.25);
                    border-radius: 1rem;
                    padding: 1.25rem;
                    border: 1px solid var(--border);
                    min-height: 350px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                }
                
                video, img.preview-img {
                    width: 100%;
                    max-height: 550px;
                    background: black;
                    border-radius: 0.75rem;
                    box-shadow: var(--shadow-lg);
                    object-fit: contain;
                }
                
                /* Utility Classes */
                .row { display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem; }
                .row-3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 0.75rem; }
                .hidden { display: none !important; }
                .small { font-size: 0.75rem; color: var(--text-dim); margin-top: 0.5rem; line-height: 1.5; }
                
                .divider {
                    height: 1px;
                    background: linear-gradient(90deg, transparent, var(--border), transparent);
                    margin: 1.25rem 0;
                }

                /* Top Navigation Bar */
                .top-navbar {
                    position: sticky;
                    top: 0;
                    z-index: var(--z-sticky);
                    background: rgba(17, 24, 39, 0.92);
                    backdrop-filter: blur(16px);
                    -webkit-backdrop-filter: blur(16px);
                    border-bottom: 1px solid var(--border);
                    margin: -1.5rem -1.5rem 1.5rem -1.5rem;
                    padding: 0 1.5rem;
                    box-shadow: var(--shadow-md);
                }
                
                .nav-menu {
                    display: flex;
                    gap: 0.25rem;
                    padding: 0.75rem 0;
                    overflow-x: auto;
                    scrollbar-width: none;
                }
                
                .nav-menu::-webkit-scrollbar { display: none; }
                
                .nav-item {
                    padding: 0.625rem 1rem;
                    border-radius: 0.5rem;
                    background: transparent;
                    color: var(--text-muted);
                    font-weight: 500;
                    font-size: 0.8125rem;
                    border: none;
                    cursor: pointer;
                    transition: all var(--transition-fast);
                    white-space: nowrap;
                    display: flex;
                    align-items: center;
                    gap: 0.5rem;
                    margin-top: 0;
                    box-shadow: none;
                    height: auto;
                    width: auto;
                }
                
                .nav-item:hover {
                    background: rgba(255, 255, 255, 0.06);
                    color: var(--text-primary);
                }
                
                .nav-item.active {
                    background: var(--primary);
                    color: white;
                    box-shadow: 0 2px 8px rgba(59, 130, 246, 0.3);
                }
                
                .nav-icon {
                    display: flex;
                    align-items: center;
                }
                
                .section-content {
                    animation: fadeIn 0.3s ease;
                }
                
                /* Animations */
                @keyframes fadeInUp {
                    from { opacity: 0; transform: translateY(16px); }
                    to { opacity: 1; transform: translateY(0); }
                }
                
                @keyframes fadeInDown {
                    from { opacity: 0; transform: translateY(-16px); }
                    to { opacity: 1; transform: translateY(0); }
                }
                
                @keyframes fadeIn {
                    from { opacity: 0; }
                    to { opacity: 1; }
                }
                
                /* Responsive */
                @media (max-width: 1024px) {
                    .grid { grid-template-columns: 1fr; }
                    .header h1 { font-size: 2rem; }
                }
                
                @media (max-width: 768px) {
                    .row, .row-3 { grid-template-columns: 1fr; }
                    .header h1 { font-size: 1.75rem; }
                    .card { padding: 1.25rem; }
                    .controls-panel { padding: 1rem; }
                    .nav-item { padding: 0.5rem 0.875rem; font-size: 0.8125rem; }
                    .top-navbar { margin: -1rem -1rem 1.25rem -1rem; padding: 0 1rem; }
                }

                /* Logs Table Styles */
                .logs-container {
                    background: rgba(15, 23, 42, 0.5);
                    border-radius: 0.75rem;
                    border: 1px solid var(--border);
                    overflow: hidden;
                }
                
                .logs-table {
                    width: 100%;
                    border-collapse: collapse;
                    font-size: 0.8125rem;
                }
                
                .logs-table thead th {
                    text-align: left;
                    padding: 0.875rem 1rem;
                    background: rgba(255, 255, 255, 0.02);
                    color: var(--text-muted);
                    font-weight: 600;
                    border-bottom: 1px solid var(--border);
                    position: sticky;
                    top: 0;
                    backdrop-filter: blur(8px);
                }
                
                .logs-table tbody tr {
                    border-bottom: 1px solid rgba(255, 255, 255, 0.03);
                    transition: background var(--transition-fast);
                }
                
                .logs-table tbody tr:hover {
                    background: rgba(255, 255, 255, 0.02);
                }
                
                .logs-table td {
                    padding: 0.75rem 1rem;
                    color: var(--text-primary);
                    vertical-align: top;
                }
                
                .log-time {
                    font-family: 'Monaco', 'Consolas', monospace;
                    font-size: 0.75rem;
                    color: var(--text-dim);
                    white-space: nowrap;
                }
                
                .log-device {
                    font-weight: 500;
                    color: var(--text-primary);
                }
                
                .log-version {
                    display: inline-block;
                    padding: 0.125rem 0.375rem;
                    background: rgba(59, 130, 246, 0.1);
                    border: 1px solid rgba(59, 130, 246, 0.2);
                    border-radius: 0.25rem;
                    color: var(--primary-light);
                    font-size: 0.6875rem;
                    margin-top: 0.25rem;
                }
                
                .log-event {
                    color: var(--accent);
                    font-weight: 600;
                }
                
                .log-params pre {
                    margin: 0;
                    font-family: 'Monaco', 'Consolas', monospace;
                    font-size: 0.75rem;
                    color: var(--text-muted);
                    white-space: pre-wrap;
                    max-height: 120px;
                    overflow-y: auto;
                }
                
                .log-empty {
                    padding: 2.5rem !important;
                    text-align: center;
                    color: var(--text-dim);
                    font-style: italic;
                }
                
                .refresh-spin { animation: spin 1s linear infinite; }
                @keyframes spin { 100% { transform: rotate(360deg); } }
                
                /* Timber Log Styles */
                .timber-console {
                    background: #1a1a2e;
                    border-radius: 12px;
                    padding: 0;
                    font-family: 'Monaco', 'Consolas', 'Courier New', monospace;
                    font-size: 0.8rem;
                    max-height: 70vh;
                    overflow-y: auto;
                    border: 1px solid var(--card-border);
                }
                .timber-line {
                    padding: 6px 12px;
                    border-bottom: 1px solid rgba(255,255,255,0.03);
                    display: flex;
                    gap: 12px;
                    align-items: flex-start;
                }
                .timber-line:hover {
                    background: rgba(255,255,255,0.02);
                }
                .timber-time {
                    color: #6b7280;
                    white-space: nowrap;
                    flex-shrink: 0;
                }
                .timber-priority {
                    font-weight: 700;
                    padding: 1px 6px;
                    border-radius: 3px;
                    font-size: 0.7rem;
                    flex-shrink: 0;
                }
                .timber-priority.V { background: #374151; color: #9ca3af; }
                .timber-priority.D { background: #1e3a5f; color: #60a5fa; }
                .timber-priority.I { background: #14532d; color: #4ade80; }
                .timber-priority.W { background: #713f12; color: #fbbf24; }
                .timber-priority.E { background: #7f1d1d; color: #f87171; }
                .timber-priority.A { background: #581c87; color: #c084fc; }
                .timber-tag {
                    color: #a78bfa;
                    font-weight: 600;
                    flex-shrink: 0;
                    max-width: 150px;
                    overflow: hidden;
                    text-overflow: ellipsis;
                }
                .timber-msg {
                    color: #e5e7eb;
                    flex: 1;
                    white-space: pre-wrap;
                    word-break: break-word;
                }
                .timber-throwable {
                    color: #f87171;
                    font-size: 0.75rem;
                    margin-top: 4px;
                    padding: 8px;
                    background: rgba(239, 68, 68, 0.1);
                    border-radius: 4px;
                    white-space: pre-wrap;
                    word-break: break-word;
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
                            <button class="nav-item" id="navWebmGif" data-section="webm-gif">
                                <span class="nav-icon">🎞️</span>
                                <span>WebM → GIF</span>
                            </button>
                            <button class="nav-item" id="navAndroidLogs" data-section="android-logs">
                                <span class="nav-icon">📱</span>
                                <span>Android Logs</span>
                            </button>
                            <button class="nav-item" id="navTimberLogs" data-section="timber-logs">
                                <span class="nav-icon">🌲</span>
                                <span>Timber Logs</span>
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

                    <!-- WebM to GIF Section -->
                    <div id="webmGifSection" class="section-content hidden">
                        <div class="grid">
                            <div class="controls-panel">
                                <div class="feature-card">
                                    <div class="feature-title">WebM → GIF</div>
                                    <label for="webmFile">Chọn file WebM</label>
                                    <input id="webmFile" type="file" accept="video/webm" />
                                    <div class="row-3" style="margin-top: 10px;">
                                        <div>
                                            <label for="webmFps" style="margin-bottom:6px;">FPS</label>
                                            <input id="webmFps" type="number" min="1" max="60" value="15" />
                                        </div>
                                        <div>
                                            <label for="webmWidth" style="margin-bottom:6px;">Width (px)</label>
                                            <input id="webmWidth" type="number" min="64" max="2048" value="640" />
                                        </div>
                                    </div>
                                    <button id="webmConvertBtn" type="button">🎞️ Convert WebM → GIF</button>
                                    <div class="status" id="webmStatus">Chưa chọn file.</div>
                                </div>
                            </div>
                            <div class="preview-container">
                                <img id="webmPreview" class="preview-img" alt="GIF Preview" style="display:none;" />
                                <div style="text-align: center; color: var(--text-muted);">
                                    <div style="font-size: 4rem; margin-bottom: 16px;">🎞️</div>
                                    <div style="font-size: 1.1rem; font-weight: 600;">WebM → GIF</div>
                                    <div class="small">Preview kết quả tại đây</div>
                                </div>
                            </div>
                        </div>
                    </div>

                   <!-- Android Logs Section -->
                    <div id="androidLogsSection" class="section-content hidden">
                        <div class="controls-panel" style="width: 100%; max-width: 100%; max-height: none;">
                            <div class="feature-card" style="border:none; background:transparent; padding:0;">
                                <div class="feature-title" style="margin-bottom: 20px; display: flex; align-items: center; justify-content: space-between;">
                                    <div style="display:flex; align-items:center; gap:10px;">
                                        <span style="font-size: 1.5rem;">📱</span>
                                        <span style="font-size: 1.25rem;">Android Device Logs</span>
                                    </div>
                                    <div style="display:flex; gap:10px;">
                                        <button id="refreshLogsBtn" style="width:auto; margin:0; padding: 8px 16px; font-size: 0.9rem;">
                                            🔄 Refresh
                                        </button>
                                        <button id="clearLogsBtn" style="width:auto; margin:0; padding: 8px 16px; font-size: 0.9rem; background: rgba(239, 68, 68, 0.15); border: 1px solid rgba(239, 68, 68, 0.3); color: #fca5a5;">
                                            🗑️ Clear
                                        </button>
                                    </div>
                                </div>
                                
                                <!-- Filter Controls -->
                                <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 16px; padding: 16px; background: rgba(255,255,255,0.02); border-radius: 12px; border: 1px solid var(--card-border);">
                                    <div>
                                        <label style="font-size: 0.8rem; color: var(--text-muted); margin-bottom: 4px; display: block;">Device</label>
                                        <input type="text" id="filterDevice" placeholder="Filter by device..." style="width: 100%; padding: 8px 12px; border-radius: 8px; border: 1px solid var(--input-border); background: var(--input-bg); color: var(--text); font-size: 0.85rem;" />
                                    </div>
                                    <div>
                                        <label style="font-size: 0.8rem; color: var(--text-muted); margin-bottom: 4px; display: block;">Event Name</label>
                                        <input type="text" id="filterEvent" placeholder="Filter by event..." style="width: 100%; padding: 8px 12px; border-radius: 8px; border: 1px solid var(--input-border); background: var(--input-bg); color: var(--text); font-size: 0.85rem;" />
                                    </div>
                                    <div>
                                        <label style="font-size: 0.8rem; color: var(--text-muted); margin-bottom: 4px; display: block;">From Date</label>
                                        <input type="date" id="filterFromDate" style="width: 100%; padding: 8px 12px; border-radius: 8px; border: 1px solid var(--input-border); background: var(--input-bg); color: var(--text); font-size: 0.85rem;" />
                                    </div>
                                    <div>
                                        <label style="font-size: 0.8rem; color: var(--text-muted); margin-bottom: 4px; display: block;">To Date</label>
                                        <input type="date" id="filterToDate" style="width: 100%; padding: 8px 12px; border-radius: 8px; border: 1px solid var(--input-border); background: var(--input-bg); color: var(--text); font-size: 0.85rem;" />
                                    </div>
                                </div>
                                <div style="margin-bottom: 16px; display: flex; gap: 10px; align-items: center;">
                                    <button id="applyFiltersBtn" style="width:auto; margin:0; padding: 8px 20px; font-size: 0.9rem;">
                                        🔍 Apply Filters
                                    </button>
                                    <button id="clearFiltersBtn" style="width:auto; margin:0; padding: 8px 16px; font-size: 0.9rem; background: transparent; border: 1px solid var(--input-border); color: var(--text-muted);">
                                        ✕ Clear Filters
                                    </button>
                                    <span id="logsCount" style="margin-left: auto; color: var(--text-dim); font-size: 0.85rem;"></span>
                                </div>
                                
                                <div class="logs-container">
                                    <div style="overflow-x: auto; max-height: 60vh;">
                                        <table class="logs-table">
                                            <thead>
                                                <tr>
                                                    <th style="width: 160px;">Time</th>
                                                    <th style="width: 200px;">Device</th>
                                                    <th style="width: 200px;">Event</th>
                                                    <th>Parameters</th>
                                                </tr>
                                            </thead>
                                            <tbody id="logsTableBody">
                                                <tr>
                                                    <td colspan="4" class="log-empty">No logs received yet.</td>
                                                </tr>
                                            </tbody>
                                        </table>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Timber Logs Section -->
                    <div id="timberLogsSection" class="section-content hidden">
                        <div class="controls-panel" style="width: 100%; max-width: 100%; max-height: none;">
                            <div class="feature-card" style="border:none; background:transparent; padding:0;">
                                <div class="feature-title" style="margin-bottom: 20px; display: flex; align-items: center; justify-content: space-between;">
                                    <div style="display:flex; align-items:center; gap:10px;">
                                        <span style="font-size: 1.5rem;">🌲</span>
                                        <span style="font-size: 1.25rem;">Timber Console</span>
                                    </div>
                                    <div style="display:flex; gap:10px;">
                                        <button id="refreshTimberBtn" style="width:auto; margin:0; padding: 8px 16px; font-size: 0.9rem;">
                                            🔄 Refresh
                                        </button>
                                        <button id="clearTimberBtn" style="width:auto; margin:0; padding: 8px 16px; font-size: 0.9rem; background: rgba(239, 68, 68, 0.15); border: 1px solid rgba(239, 68, 68, 0.3); color: #fca5a5;">
                                            🗑️ Clear
                                        </button>
                                    </div>
                                </div>
                                
                                <!-- Timber Filter Controls -->
                                <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 16px; padding: 16px; background: rgba(255,255,255,0.02); border-radius: 12px; border: 1px solid var(--card-border);">
                                    <div>
                                        <label style="font-size: 0.8rem; color: var(--text-muted); margin-bottom: 4px; display: block;">Priority</label>
                                        <select id="timberFilterPriority" style="width: 100%; padding: 8px 12px; border-radius: 8px; border: 1px solid var(--input-border); background: var(--input-bg); color: var(--text); font-size: 0.85rem;">
                                            <option value="">All</option>
                                            <option value="V">Verbose</option>
                                            <option value="D">Debug</option>
                                            <option value="I">Info</option>
                                            <option value="W">Warning</option>
                                            <option value="E">Error</option>
                                            <option value="A">Assert</option>
                                        </select>
                                    </div>
                                    <div>
                                        <label style="font-size: 0.8rem; color: var(--text-muted); margin-bottom: 4px; display: block;">Tag</label>
                                        <input type="text" id="timberFilterTag" placeholder="Filter by tag..." style="width: 100%; padding: 8px 12px; border-radius: 8px; border: 1px solid var(--input-border); background: var(--input-bg); color: var(--text); font-size: 0.85rem;" />
                                    </div>
                                    <div>
                                        <label style="font-size: 0.8rem; color: var(--text-muted); margin-bottom: 4px; display: block;">Message</label>
                                        <input type="text" id="timberFilterMsg" placeholder="Search message..." style="width: 100%; padding: 8px 12px; border-radius: 8px; border: 1px solid var(--input-border); background: var(--input-bg); color: var(--text); font-size: 0.85rem;" />
                                    </div>
                                    <div style="display: flex; align-items: flex-end; gap: 8px;">
                                        <button id="applyTimberFiltersBtn" style="flex:1; margin:0; padding: 8px 12px; font-size: 0.85rem;">
                                            🔍 Filter
                                        </button>
                                        <button id="clearTimberFiltersBtn" style="width:auto; margin:0; padding: 8px 12px; font-size: 0.85rem; background: transparent; border: 1px solid var(--input-border); color: var(--text-muted);">
                                            ✕
                                        </button>
                                    </div>
                                </div>
                                <div style="margin-bottom: 12px; display: flex; align-items: center;">
                                    <span id="timberCount" style="color: var(--text-dim); font-size: 0.85rem;"></span>
                                    <label style="margin-left: auto; display: flex; align-items: center; gap: 8px; color: var(--text-muted); font-size: 0.85rem;">
                                        <input type="checkbox" id="timberAutoScroll" checked />
                                        Auto-scroll
                                    </label>
                                </div>
                                
                                <div class="timber-console" id="timberConsole">
                                    <div class="timber-line" style="color: var(--text-dim); justify-content: center; padding: 20px;">No Timber logs yet.</div>
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

                const webmFile = document.getElementById('webmFile');
                const webmFps = document.getElementById('webmFps');
                const webmWidth = document.getElementById('webmWidth');
                const webmConvertBtn = document.getElementById('webmConvertBtn');
                const webmStatus = document.getElementById('webmStatus');
                const webmPreview = document.getElementById('webmPreview');

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
                    const webmGifSection = document.getElementById('webmGifSection');
                    const androidLogsSection = document.getElementById('androidLogsSection');
                    const timberLogsSection = document.getElementById('timberLogsSection');

                    const allSections = [
                        videoSection,
                        imageConvertSection,
                        gifWebpSection,
                        videoWebpSection,
                        batchConvertSection,
                        batchResizeSection,
                        tgsGifSection,
                        webmGifSection,
                        androidLogsSection,
                        timberLogsSection
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
                            'tgs-gif': tgsGifSection,
                            'webm-gif': webmGifSection,
                            'android-logs': androidLogsSection,
                            'timber-logs': timberLogsSection
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
                        downloadBlob(blob, file.name.replace(/\.[^/.]+$/, "") + ".webp");
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
                        downloadBlob(blob, file.name.replace(/\.[^/.]+$/, "") + ".webp");
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

                // WebM to GIF conversion
                webmConvertBtn.addEventListener('click', async () => {
                    const file = webmFile.files?.[0];
                    if (!file) { webmStatus.textContent = 'Hãy chọn file WebM.'; return; }

                    const fps = Number(webmFps.value || 15);
                    const width = Number(webmWidth.value || 640);

                    webmStatus.textContent = 'Đang convert WebM → GIF...';
                    const form = new FormData();
                    form.append('file', file);
                    form.append('fps', String(fps));
                    form.append('width', String(width));

                    try {
                        const res = await fetch('/webm-to-gif', { method: 'POST', body: form });
                        if (!res.ok) throw new Error(await res.text());
                        const blob = await res.blob();
                        
                        const url = URL.createObjectURL(blob);
                        webmPreview.src = url;
                        webmPreview.style.display = 'block';
                        // hide placeholder
                        webmPreview.nextElementSibling.style.display = 'none';
                        
                        downloadBlob(blob, file.name.replace(/\.[^/.]+$/, "") + ".gif");
                        webmStatus.textContent = `Xong (${fps} fps, width ${width}px).`;
                    } catch (err) {
                        console.error(err);
                        webmStatus.textContent = 'Lỗi: ' + err.message;
                    }
                });
                // Android Logs Logic
                const logsTableBody = document.getElementById('logsTableBody');
                const refreshLogsBtn = document.getElementById('refreshLogsBtn');
                const clearLogsBtn = document.getElementById('clearLogsBtn');
                const filterDevice = document.getElementById('filterDevice');
                const filterEvent = document.getElementById('filterEvent');
                const filterFromDate = document.getElementById('filterFromDate');
                const filterToDate = document.getElementById('filterToDate');
                const applyFiltersBtn = document.getElementById('applyFiltersBtn');
                const clearFiltersBtn = document.getElementById('clearFiltersBtn');
                const logsCount = document.getElementById('logsCount');
                
                let allLogs = []; // Store all logs for filtering

                async function fetchLogs() {
                    try {
                        refreshLogsBtn.disabled = true;
                        refreshLogsBtn.textContent = 'Refreshing...';
                        const res = await fetch('/api/android-log');
                        if (!res.ok) throw new Error(await res.text());
                        allLogs = await res.json();
                        applyFilters();
                    } catch (err) {
                        console.error(err);
                    } finally {
                        refreshLogsBtn.disabled = false;
                        refreshLogsBtn.textContent = '🔄 Refresh';
                    }
                }
                
                function applyFilters() {
                    const deviceFilter = (filterDevice.value || '').toLowerCase().trim();
                    const eventFilter = (filterEvent.value || '').toLowerCase().trim();
                    const fromDate = filterFromDate.value ? new Date(filterFromDate.value) : null;
                    const toDate = filterToDate.value ? new Date(filterToDate.value + 'T23:59:59') : null;
                    
                    let filtered = allLogs.filter(log => {
                        // Device filter
                        if (deviceFilter && !(log.deviceName || '').toLowerCase().includes(deviceFilter)) {
                            return false;
                        }
                        // Event filter
                        if (eventFilter && !(log.eventName || '').toLowerCase().includes(eventFilter)) {
                            return false;
                        }
                        // Date filter
                        if (fromDate || toDate) {
                            const logDate = new Date(log.timestamp.replace(' ', 'T'));
                            if (fromDate && logDate < fromDate) return false;
                            if (toDate && logDate > toDate) return false;
                        }
                        return true;
                    });
                    
                    renderLogs(filtered);
                    logsCount.textContent = `Showing ${filtered.length} of ${allLogs.length} logs`;
                }

                function renderLogs(logs) {
                    if (!logs || logs.length === 0) {
                        logsTableBody.innerHTML = '<tr><td colspan="4" class="log-empty">No logs match the filters.</td></tr>';
                        return;
                    }
                    // Show newest first
                    logsTableBody.innerHTML = logs.slice().reverse().map(log => {
                        const paramsStr = log.params && Object.keys(log.params).length > 0 
                            ? JSON.stringify(log.params, null, 2) 
                            : '<span style="color:var(--text-dim); font-style:italic;">No params</span>';
                            
                        const deviceName = log.deviceName || 'Unknown Device';
                        const version = log.versionCode ? `v${log.versionCode}` : '';
                        
                        return `
                            <tr>
                                <td class="log-time">${log.timestamp}</td>
                                <td>
                                    <div class="log-device">${deviceName}</div>
                                    ${version ? `<div class="log-version">${version}</div>` : ''}
                                </td>
                                <td class="log-event">${log.eventName}</td>
                                <td class="log-params"><pre>${paramsStr}</pre></td>
                            </tr>
                        `;
                    }).join('');
                }
                
                applyFiltersBtn.addEventListener('click', applyFilters);
                
                clearFiltersBtn.addEventListener('click', () => {
                    filterDevice.value = '';
                    filterEvent.value = '';
                    filterFromDate.value = '';
                    filterToDate.value = '';
                    applyFilters();
                });
                
                // Allow Enter key to apply filters
                [filterDevice, filterEvent].forEach(input => {
                    input.addEventListener('keypress', (e) => {
                        if (e.key === 'Enter') applyFilters();
                    });
                });

                refreshLogsBtn.addEventListener('click', fetchLogs);
                
                clearLogsBtn.addEventListener('click', async () => {
                    if(!confirm('Clear all logs?')) return;
                    try {
                        await fetch('/api/android-log', { method: 'DELETE' });
                        fetchLogs();
                    } catch(e) { console.error(e); }
                });

                // Initial fetch
                fetchLogs();
                
                // Real-time updates using Server-Sent Events
                let eventSource = null;
                
                function startSSE() {
                    if (eventSource) return;
                    
                    eventSource = new EventSource('/api/android-log/stream');
                    
                    eventSource.onmessage = (event) => {
                        try {
                            const log = JSON.parse(event.data);
                            // Add to allLogs and re-render
                            allLogs.push(log);
                            // Keep only last 1000
                            if (allLogs.length > 1000) {
                                allLogs = allLogs.slice(-1000);
                            }
                            applyFilters();
                        } catch(e) {
                            // Ignore parse errors (heartbeats)
                        }
                    };
                    
                    eventSource.onerror = () => {
                        stopSSE();
                        // Reconnect after 3 seconds
                        setTimeout(() => {
                            const section = document.getElementById('androidLogsSection');
                            if (section && !section.classList.contains('hidden')) {
                                startSSE();
                            }
                        }, 3000);
                    };
                }
                
                function stopSSE() {
                    if (eventSource) {
                        eventSource.close();
                        eventSource = null;
                    }
                }
                
                // Start SSE when on Android Logs tab
                document.getElementById('navAndroidLogs').addEventListener('click', () => {
                    fetchLogs();
                    startSSE();
                });
                
                // Stop SSE when switching to other tabs
                document.querySelectorAll('.nav-item').forEach(item => {
                    item.addEventListener('click', () => {
                        if (item.id !== 'navAndroidLogs') {
                            stopSSE();
                        }
                        if (item.id !== 'navTimberLogs') {
                            stopTimberSSE();
                        }
                    });
                });
                
                // ==================== TIMBER LOGS LOGIC ====================
                const timberConsole = document.getElementById('timberConsole');
                const refreshTimberBtn = document.getElementById('refreshTimberBtn');
                const clearTimberBtn = document.getElementById('clearTimberBtn');
                const timberFilterPriority = document.getElementById('timberFilterPriority');
                const timberFilterTag = document.getElementById('timberFilterTag');
                const timberFilterMsg = document.getElementById('timberFilterMsg');
                const applyTimberFiltersBtn = document.getElementById('applyTimberFiltersBtn');
                const clearTimberFiltersBtn = document.getElementById('clearTimberFiltersBtn');
                const timberCount = document.getElementById('timberCount');
                const timberAutoScroll = document.getElementById('timberAutoScroll');
                
                let allTimberLogs = [];
                let timberEventSource = null;
                
                async function fetchTimberLogs() {
                    try {
                        refreshTimberBtn.disabled = true;
                        refreshTimberBtn.textContent = 'Refreshing...';
                        const res = await fetch('/api/android-log');
                        if (!res.ok) throw new Error(await res.text());
                        const logs = await res.json();
                        // Filter only timber_log events
                        allTimberLogs = logs.filter(l => l.eventName === 'timber_log');
                        applyTimberFilters();
                    } catch (err) {
                        console.error(err);
                    } finally {
                        refreshTimberBtn.disabled = false;
                        refreshTimberBtn.textContent = '\ud83d\udd04 Refresh';
                    }
                }
                
                function applyTimberFilters() {
                    const priorityFilter = timberFilterPriority.value;
                    const tagFilter = (timberFilterTag.value || '').toLowerCase().trim();
                    const msgFilter = (timberFilterMsg.value || '').toLowerCase().trim();
                    
                    let filtered = allTimberLogs.filter(log => {
                        const params = log.params || {};
                        if (priorityFilter && params.priority !== priorityFilter) return false;
                        if (tagFilter && !(params.tag || '').toLowerCase().includes(tagFilter)) return false;
                        if (msgFilter && !(params.message || '').toLowerCase().includes(msgFilter)) return false;
                        return true;
                    });
                    
                    renderTimberLogs(filtered);
                    timberCount.textContent = `Showing ${filtered.length} of ${allTimberLogs.length} timber logs`;
                }
                
                function escapeHtml(text) {
                    if (!text) return '';
                    return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
                }
                
                function renderTimberLogs(logs) {
                    if (!logs || logs.length === 0) {
                        timberConsole.innerHTML = '<div class="timber-line" style="color: var(--text-dim); justify-content: center; padding: 20px;">No Timber logs match the filters.</div>';
                        return;
                    }
                    
                    timberConsole.innerHTML = logs.map(log => {
                        const params = log.params || {};
                        const priority = params.priority || 'D';
                        const tag = escapeHtml(params.tag || 'Unknown');
                        const message = escapeHtml(params.message || '');
                        const throwable = params.throwable ? escapeHtml(params.throwable) : null;
                        const time = log.timestamp ? log.timestamp.split(' ')[1] || log.timestamp : '';
                        
                        return `
                            <div class="timber-line">
                                <span class="timber-time">${time}</span>
                                <span class="timber-priority ${priority}">${priority}</span>
                                <span class="timber-tag">${tag}</span>
                                <div class="timber-msg">
                                    ${message}
                                    ${throwable ? `<div class="timber-throwable">${throwable}</div>` : ''}
                                </div>
                            </div>
                        `;
                    }).join('');
                    
                    if (timberAutoScroll.checked) {
                        timberConsole.scrollTop = timberConsole.scrollHeight;
                    }
                }
                
                function startTimberSSE() {
                    if (timberEventSource) return;
                    
                    timberEventSource = new EventSource('/api/android-log/stream');
                    
                    timberEventSource.onmessage = (event) => {
                        try {
                            const log = JSON.parse(event.data);
                            if (log.eventName === 'timber_log') {
                                allTimberLogs.push(log);
                                if (allTimberLogs.length > 1000) {
                                    allTimberLogs = allTimberLogs.slice(-1000);
                                }
                                applyTimberFilters();
                            }
                        } catch(e) {}
                    };
                    
                    timberEventSource.onerror = () => {
                        stopTimberSSE();
                        setTimeout(() => {
                            const section = document.getElementById('timberLogsSection');
                            if (section && !section.classList.contains('hidden')) {
                                startTimberSSE();
                            }
                        }, 3000);
                    };
                }
                
                function stopTimberSSE() {
                    if (timberEventSource) {
                        timberEventSource.close();
                        timberEventSource = null;
                    }
                }
                
                refreshTimberBtn.addEventListener('click', fetchTimberLogs);
                
                clearTimberBtn.addEventListener('click', async () => {
                    if(!confirm('This will clear ALL logs (including Android events). Continue?')) return;
                    try {
                        await fetch('/api/android-log', { method: 'DELETE' });
                        allTimberLogs = [];
                        applyTimberFilters();
                        fetchLogs(); // Also refresh Android logs
                    } catch(e) { console.error(e); }
                });
                
                applyTimberFiltersBtn.addEventListener('click', applyTimberFilters);
                
                clearTimberFiltersBtn.addEventListener('click', () => {
                    timberFilterPriority.value = '';
                    timberFilterTag.value = '';
                    timberFilterMsg.value = '';
                    applyTimberFilters();
                });
                
                [timberFilterTag, timberFilterMsg].forEach(input => {
                    input.addEventListener('keypress', (e) => {
                        if (e.key === 'Enter') applyTimberFilters();
                    });
                });
                
                timberFilterPriority.addEventListener('change', applyTimberFilters);
                
                document.getElementById('navTimberLogs').addEventListener('click', () => {
                    fetchTimberLogs();
                    startTimberSSE();
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


@app.route("/api/android-log", methods=["GET", "POST", "DELETE"])
def android_log():
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        event_name = data.get("eventName", "Unknown")
        device_name = data.get("deviceName", "Unknown Device")
        version_code = str(data.get("versionCode", ""))
        params_json = json.dumps(data.get("params", {}))

        try:
            conn = get_db_connection()
            conn.execute(
                'INSERT INTO logs (timestamp, event_name, device_name, version_code, params) VALUES (?, ?, ?, ?, ?)',
                (timestamp, event_name, device_name, version_code, params_json)
            )
            conn.commit()
            conn.close()
            
            # Return the entry for client confirmation (optional, simplified)
            return jsonify({
                "status": "logged", 
                "entry": {
                    "timestamp": timestamp,
                    "eventName": event_name,
                    "deviceName": device_name,
                    "versionCode": version_code,
                    "params": data.get("params", {})
                }
            })
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

    elif request.method == "DELETE":
        try:
            conn = get_db_connection()
            conn.execute('DELETE FROM logs')
            conn.commit()
            conn.close()
            return jsonify({"status": "cleared"})
        except Exception as e:
             return jsonify({"status": "error", "message": str(e)}), 500

    else:
        # GET
        try:
            conn = get_db_connection()
            # Get last 1000 logs
            logs_db = conn.execute('SELECT * FROM logs ORDER BY id DESC LIMIT 1000').fetchall()
            conn.close()
            
            logs = []
            for row in logs_db:
                logs.append({
                    "timestamp": row["timestamp"],
                    "eventName": row["event_name"],
                    "deviceName": row["device_name"],
                    "versionCode": row["version_code"],
                    "params": json.loads(row["params"]) if row["params"] else {}
                })
            # Reverse to match previous behavior if needed, but UI handles slice().reverse()
            # API returns newest first (DESC) so UI might not need reverse() if we wanted consistent order, 
            # but let's send them and let UI handle display.
            # Current UI does `slice().reverse()`, implying it expects Oldest -> Newest.
            # Our SQL returns Newest -> Oldest. 
            # So if UI reverses, it will show Oldest -> Newest at top? 
            # Wait, UI: `logs.slice().reverse().map(...)`
            # If API sends [New, Old], Reverse -> [Old, New]. Map renders Top=Old, Bottom=New.
            # If we want Newest at Top, UI should NOT reverse, or API should send Oldest -> Newest.
            # Ideally logs are usually appended. 
            # Let's send Oldest -> Newest (ASC) from SQL to keep compatibility with existing UI logic `slice().reverse()` 
            # which likely assumes appending array.
            
            # Re-query for ASC order to maintain compatibility with simple array append logic
            # actually strict limit 1000 implies we want 1000 newest.
            # So: Select * from (Select * form logs order by id DESC limit 1000) order by id ASC
            
            # To keep it simple and consistent with "ANDROID_LOGS.append", we should return list in chronological order.
            logs.reverse() # created from DESC, so reverse makes it ASC (Chronological)
            
            return jsonify(logs)
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/android-log/stream")
def android_log_stream():
    """Server-Sent Events endpoint for real-time log updates."""
    def generate():
        last_id = 0
        while True:
            try:
                conn = get_db_connection()
                # Get logs newer than last_id
                logs_db = conn.execute(
                    'SELECT * FROM logs WHERE id > ? ORDER BY id ASC LIMIT 50',
                    (last_id,)
                ).fetchall()
                conn.close()
                
                if logs_db:
                    for row in logs_db:
                        last_id = row["id"]
                        log_entry = {
                            "timestamp": row["timestamp"],
                            "eventName": row["event_name"],
                            "deviceName": row["device_name"],
                            "versionCode": row["version_code"],
                            "params": json.loads(row["params"]) if row["params"] else {}
                        }
                        yield f"data: {json.dumps(log_entry)}\n\n"
                else:
                    # Send heartbeat to keep connection alive
                    yield f": heartbeat\n\n"
                    
                import time
                time.sleep(1)  # Check for new logs every second
            except GeneratorExit:
                break
            except Exception as e:
                print(f"SSE Error: {e}")
                break
    
    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no'
        }
    )


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
        download_name=Path(file.filename).stem + ".webp",
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
        download_name=Path(file.filename).stem + ".webp",
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


def _convert_tgs_to_webp(
    input_path: Path,
    *,
    width: int | None = None,
    fps: int = 30,
    quality: int = 80,
    output_path: Path | None = None,
) -> Path:
    """Convert TGS (Telegram sticker) to animated WebP.

    TGS files are gzipped Lottie JSON animations.
    We decompress, load as Lottie, export to GIF first, then convert to WebP.
    """
    if not HAS_LOTTIE:
        abort(500, "Lottie library không được cài đặt. Cần cài đặt 'lottie'.")

    if output_path is None:
        output_path = OUTPUT_DIR / f"{uuid.uuid4().hex}.webp"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # TGS files are gzipped Lottie JSON - first convert to GIF, then to WebP
    try:
        with gzip.open(input_path, 'rb') as f:
            lottie_data = json.load(f)

        # Parse Lottie animation
        animation = objects.Animation.load(lottie_data)

        # Map width to renderer DPI (96 is the base scale).
        dpi = 96
        if width:
            scale = width / animation.width if animation.width else 1
            dpi = max(1, int(round(96 * scale)))

        # Map requested fps to skip_frames (renderer uses original frame rate).
        skip_frames = 1
        if fps and animation.frame_rate:
            skip_frames = max(1, int(round(animation.frame_rate / fps)))

        # Export to GIF first (temp file)
        gif_path = output_path.parent / f"{uuid.uuid4().hex}_temp.gif"
        export_gif(
            animation,
            str(gif_path),
            dpi=dpi,
            skip_frames=skip_frames,
        )

        # Convert GIF to animated WebP
        vf = "format=rgba"
        if width:
            vf = f"scale={width}:-1:flags=lanczos,format=rgba"

        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(gif_path),
            "-vf",
            vf,
            "-an",
            "-loop",
            "0",
            "-c:v",
            "libwebp",
            "-preset",
            "default",
            "-q:v",
            str(quality),
            "-compression_level",
            "6",
            str(output_path),
        ]
        _run_ffmpeg(cmd)
        gif_path.unlink(missing_ok=True)

        return output_path

    except Exception as e:
        abort(500, f"Lỗi chuyển đổi TGS sang WebP: {str(e)}")


def _convert_webm_to_webp(
    input_path: Path,
    *,
    fps: int = 15,
    width: int | None = None,
    quality: int = 80,
    output_path: Path | None = None,
) -> Path:
    """Convert WebM video to animated WebP."""
    if output_path is None:
        output_path = OUTPUT_DIR / f"{uuid.uuid4().hex}.webp"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    vf_parts = [f"fps={fps}"]
    if width:
        vf_parts.append(f"scale={width}:-1:flags=lanczos")
    vf_parts.append("format=rgba")
    vf = ",".join(vf_parts)

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(input_path),
        "-vf",
        vf,
        "-an",
        "-loop",
        "0",
        "-c:v",
        "libwebp",
        "-preset",
        "default",
        "-q:v",
        str(quality),
        "-compression_level",
        "6",
        str(output_path),
    ]
    _run_ffmpeg(cmd)
    return output_path


def _convert_gif_to_webp(
    input_path: Path,
    *,
    width: int | None = None,
    quality: int = 80,
    output_path: Path | None = None,
) -> Path:
    """Convert GIF to animated WebP."""
    if output_path is None:
        output_path = OUTPUT_DIR / f"{uuid.uuid4().hex}.webp"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    vf = "format=rgba"
    if width:
        vf = f"scale={width}:-1:flags=lanczos,format=rgba"

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(input_path),
        "-vf",
        vf,
        "-an",
        "-loop",
        "0",
        "-c:v",
        "libwebp",
        "-preset",
        "default",
        "-q:v",
        str(quality),
        "-compression_level",
        "6",
        str(output_path),
    ]
    _run_ffmpeg(cmd)
    return output_path


def _allowed_batch_to_webp_suffix(filename: str) -> str | None:
    """Check if file extension is allowed for batch-to-webp conversion."""
    suffix = (Path(filename).suffix or "").lower()
    if suffix in {".tgs", ".webm", ".png", ".jpg", ".jpeg", ".gif"}:
        return suffix
    return None


@app.post("/batch-to-webp-zip")
def batch_to_webp_zip():
    """Batch convert TGS/WebM/PNG/GIF files to WebP and return as ZIP.
    Also supports uploading ZIP files containing these file types.
    """
    files = request.files.getlist("files")
    if not files:
        abort(400, "Thiếu danh sách file (files)")

    # Optional parameters
    width_raw = request.form.get("width")
    width: int | None = None
    if width_raw not in (None, "", "0"):
        width = _validate_positive_int(width_raw, name="Width", min_value=16, max_value=4096)

    fps_raw = request.form.get("fps")
    fps: int = 15  # default FPS for animated
    if fps_raw not in (None, "", "0"):
        fps = _validate_positive_int(fps_raw, name="FPS", min_value=1, max_value=60)

    quality_raw = request.form.get("quality")
    quality: int = 80  # default quality
    if quality_raw not in (None, "", "0"):
        quality = _validate_positive_int(quality_raw, name="Quality", min_value=1, max_value=100)

    # Create batch directory
    batch_dir = OUTPUT_DIR / f"batch_to_webp_{uuid.uuid4().hex}"
    batch_dir.mkdir(parents=True, exist_ok=True)
    zip_path = batch_dir / "converted_webp.zip"
    extract_dir = batch_dir / "extracted"
    extract_dir.mkdir(parents=True, exist_ok=True)

    # Collect all files to process (including files extracted from ZIPs)
    files_to_process: list[tuple[Path, str]] = []  # (path, original_name)

    output_paths: list[Path] = []
    try:
        for index, f in enumerate(files, start=1):
            if f.filename is None or f.filename == "":
                continue

            # Check if it's a ZIP file
            if f.filename.lower().endswith(".zip"):
                # Save and extract ZIP
                zip_input_path = batch_dir / f"input_zip_{index:04d}.zip"
                f.save(zip_input_path)
                try:
                    with zipfile.ZipFile(zip_input_path, "r") as zf:
                        for zip_member in zf.namelist():
                            # Skip directories and hidden files
                            if zip_member.endswith("/") or zip_member.startswith("__MACOSX"):
                                continue
                            member_filename = Path(zip_member).name
                            suffix = _allowed_batch_to_webp_suffix(member_filename)
                            if suffix:
                                extracted_path = extract_dir / f"z{index}_{uuid.uuid4().hex[:8]}{suffix}"
                                with zf.open(zip_member) as source, open(extracted_path, "wb") as target:
                                    target.write(source.read())
                                files_to_process.append((extracted_path, member_filename))
                except zipfile.BadZipFile:
                    continue  # Skip invalid ZIP files
            else:
                suffix = _allowed_batch_to_webp_suffix(f.filename)
                if suffix is None:
                    continue  # Skip unsupported files instead of aborting

                input_path = batch_dir / f"input_{index:04d}{suffix}"
                f.save(input_path)
                files_to_process.append((input_path, f.filename))

        # Process all collected files
        for idx, (input_path, original_name) in enumerate(files_to_process, start=1):
            suffix = input_path.suffix.lower()
            output_name = _safe_zip_entry_name_with_ext(Path(original_name).stem, index=idx, ext=".webp")
            output_path = batch_dir / output_name

            # Convert based on file type
            if suffix == ".tgs":
                _convert_tgs_to_webp(
                    input_path,
                    width=width,
                    fps=fps,
                    quality=quality,
                    output_path=output_path,
                )
            elif suffix == ".webm":
                _convert_webm_to_webp(
                    input_path,
                    fps=fps,
                    width=width,
                    quality=quality,
                    output_path=output_path,
                )
            elif suffix == ".gif":
                _convert_gif_to_webp(
                    input_path,
                    width=width,
                    quality=quality,
                    output_path=output_path,
                )
            else:  # PNG, JPG, JPEG - static images
                _convert_image_to_webp(
                    input_path,
                    lossless=(suffix == ".png"),
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
        abort(500, f"Lỗi chuyển đổi: {exc}")

    # Cleanup after request
    @after_this_request
    def cleanup(response):  # type: ignore
        shutil.rmtree(batch_dir, ignore_errors=True)
        return response

    return send_file(
        zip_path,
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"batch_to_webp_{len(output_paths)}.zip",
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


@app.post("/webm-to-gif")
def webm_to_gif():
    file = request.files.get("file")
    if file is None or file.filename == "":
        abort(400, "Thiếu file WebM")

    fps = _validate_positive_int(request.form.get("fps"), name="FPS", min_value=1, max_value=60)
    width_raw = request.form.get("width")
    width: int = 640
    if width_raw not in (None, "", "0"):
        width = _validate_positive_int(width_raw, name="Width", min_value=64, max_value=2048)

    input_path = UPLOAD_DIR / f"{uuid.uuid4().hex}.webm"
    file.save(input_path)

    try:
        output_path = _convert_webm_to_gif(input_path, fps=fps, width=width)
    except Exception as exc:
        input_path.unlink(missing_ok=True)
        abort(500, f"Lỗi ffmpeg: {exc}")

    @after_this_request
    def cleanup(response):
        input_path.unlink(missing_ok=True)
        output_path.unlink(missing_ok=True)
        return response

    return send_file(
        output_path,
        mimetype="image/gif",
        as_attachment=True,
        download_name=Path(file.filename).stem + ".gif",
    )


# ---------------------------- Analytics Dashboard -------------------------

@app.get("/analytics")
def analytics_dashboard():
    """Render the analytics dashboard UI."""
    return render_template_string(r"""
<!doctype html>
<html lang="en">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>🌿 Plant Analytics Dashboard</title>
    <link href="https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;500;600;700&family=Fira+Sans:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        
        html { scroll-behavior: smooth; }
        
        @media (prefers-reduced-motion: reduce) {
            *, *::before, *::after {
                animation-duration: 0.01ms !important;
                animation-iteration-count: 1 !important;
                transition-duration: 0.01ms !important;
            }
        }
        
        :root {
            /* New Design System Colors */
            --bg-gradient-1: #0a0e27;
            --bg-gradient-2: #1a1f3a;
            --card-bg: rgba(17, 24, 39, 0.8);
            --card-border: rgba(255, 255, 255, 0.08);
            --primary: #3b82f6;           /* Blue-500 */
            --primary-light: #60a5fa;      /* Blue-400 */
            --secondary: #60a5fa;          /* Blue-400 for secondary actions */
            --accent: #10b981;             /* Emerald-500 for success */
            --cta: #f97316;                /* Orange-500 for CTAs */
            --text: #f1f5f9;               /* Slate-100 */
            --text-muted: #94a3b8;         /* Slate-400 */
            --text-dim: #64748b;           /* Slate-500 */
            --input-bg: rgba(15, 23, 42, 0.6);
            --input-border: rgba(148, 163, 184, 0.2);
            --success: #10b981;
            --warning: #f59e0b;
            --error: #ef4444;
            
            /* Typography */
            --font-heading: 'Fira Code', monospace;
            --font-body: 'Fira Sans', sans-serif;
        }
        
        body {
            font-family: var(--font-body);
            background: linear-gradient(135deg, var(--bg-gradient-1) 0%, var(--bg-gradient-2) 100%);
            background-attachment: fixed;
            color: var(--text);
            min-height: 100vh;
            line-height: 1.6;
            padding: 1.25rem;
        }
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
            --success: #10b981;
            --warning: #f59e0b;
            --error: #ef4444;
        }
        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
            background: linear-gradient(135deg, var(--bg-gradient-1) 0%, var(--bg-gradient-2) 100%);
            background-attachment: fixed;
            color: var(--text);
            min-height: 100vh;
            line-height: 1.6;
            padding: 20px;
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
            max-width: 1600px;
            margin: 0 auto;
            position: relative;
            z-index: 1;
        }
        .header {
            text-align: center;
            margin-bottom: 32px;
            animation: fadeInDown 0.6s ease;
        }
        .header h1 {
            margin: 0 0 8px;
            font-size: 2.5rem;
            font-weight: 800;
            background: linear-gradient(135deg, #3b82f6, #8b5cf6, #ec4899);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        .header p {
            color: var(--text-muted);
            font-size: 1rem;
        }
        .card {
            background: var(--card-bg);
            backdrop-filter: blur(20px);
            border: 1px solid var(--card-border);
            border-radius: 20px;
            padding: 24px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.4);
            margin-bottom: 20px;
            animation: fadeInUp 0.6s ease;
        }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }
        .stat-card {
            background: linear-gradient(135deg, rgba(59, 130, 246, 0.1), rgba(139, 92, 246, 0.1));
            border: 1px solid var(--card-border);
            border-radius: 16px;
            padding: 20px;
            text-align: center;
            transition: transform 0.3s ease;
        }
        .stat-card:hover {
            transform: translateY(-4px);
        }
        .stat-value {
            font-size: 2rem;
            font-weight: 700;
            color: var(--primary-light);
            margin-bottom: 4px;
        }
        .stat-label {
            font-size: 0.875rem;
            color: var(--text-muted);
            font-weight: 500;
        }
        .charts-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 20px;
            margin-bottom: 24px;
        }
        .chart-card {
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 16px;
            padding: 20px;
        }
        .chart-title {
            font-size: 1rem;
            font-weight: 600;
            margin-bottom: 16px;
            color: var(--text);
        }
        .filters {
            display: flex;
            gap: 12px;
            flex-wrap: wrap;
            margin-bottom: 20px;
            padding: 16px;
            background: rgba(15, 23, 42, 0.4);
            border-radius: 12px;
        }
        .filter-group {
            flex: 1;
            min-width: 200px;
        }
        .filter-group label {
            display: block;
            font-size: 0.875rem;
            font-weight: 600;
            margin-bottom: 6px;
            color: var(--text-muted);
        }
        .filter-group select,
        .filter-group input {
            width: 100%;
            padding: 10px 14px;
            background: var(--input-bg);
            border: 1px solid var(--input-border);
            border-radius: 8px;
            color: var(--text);
            font-size: 0.875rem;
            font-family: inherit;
            transition: border-color 0.2s;
        }
        .filter-group select:focus,
        .filter-group input:focus {
            outline: none;
            border-color: var(--primary);
        }
        .btn {
            padding: 10px 20px;
            border: none;
            border-radius: 8px;
            font-weight: 600;
            font-size: 0.875rem;
            cursor: pointer;
            transition: all 0.3s ease;
            font-family: inherit;
        }
        .btn-primary {
            background: linear-gradient(135deg, var(--primary), var(--secondary));
            color: white;
        }
        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 20px rgba(59, 130, 246, 0.4);
        }
        .btn-secondary {
            background: rgba(148, 163, 184, 0.2);
            color: var(--text-muted);
        }
        .btn-secondary:hover {
            background: rgba(148, 163, 184, 0.3);
            color: var(--text);
        }
        .table-wrapper {
            overflow-x: auto;
            margin-bottom: 16px;
        }
        table {
            width: 100%;
            border-collapse: collapse;
        }
        th {
            background: rgba(59, 130, 246, 0.1);
            padding: 12px;
            text-align: left;
            font-weight: 600;
            font-size: 0.875rem;
            color: var(--text);
            cursor: pointer;
            user-select: none;
            white-space: nowrap;
        }
        th:hover {
            background: rgba(59, 130, 246, 0.2);
        }
        td {
            padding: 12px;
            border-bottom: 1px solid var(--card-border);
            font-size: 0.875rem;
        }
        tr:hover {
            background: rgba(59, 130, 246, 0.05);
            cursor: pointer;
        }
        .badge {
            display: inline-block;
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 0.75rem;
            font-weight: 600;
        }
        .badge-healthy {
            background: rgba(16, 185, 129, 0.2);
            color: var(--success);
        }
        .badge-unhealthy {
            background: rgba(239, 68, 68, 0.2);
            color: var(--error);
        }
        .badge-unknown {
            background: rgba(148, 163, 184, 0.2);
            color: var(--text-muted);
        }
        .badge-identify {
            background: rgba(59, 130, 246, 0.2);
            color: var(--primary-light);
        }
        .badge-diagnose {
            background: rgba(236, 72, 153, 0.2);
            color: var(--accent-pink);
        }
        .pagination {
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 8px;
            margin-top: 16px;
        }
        .page-info {
            color: var(--text-muted);
            font-size: 0.875rem;
            margin: 0 12px;
        }
        .img-thumb {
            width: 50px;
            height: 50px;
            object-fit: cover;
            border-radius: 8px;
            cursor: pointer;
            transition: transform 0.2s;
        }
        .img-thumb:hover {
            transform: scale(1.1);
        }
        .modal {
            display: none;
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(0, 0, 0, 0.8);
            z-index: 1000;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        .modal.active {
            display: flex;
        }
        .modal-content {
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 16px;
            padding: 32px;
            max-width: 800px;
            width: 100%;
            max-height: 90vh;
            overflow-y: auto;
            position: relative;
        }
        .modal-close {
            position: absolute;
            top: 16px;
            right: 16px;
            width: 32px;
            height: 32px;
            border-radius: 50%;
            background: rgba(255, 255, 255, 0.1);
            border: none;
            color: var(--text);
            font-size: 1.5rem;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .modal-close:hover {
            background: rgba(255, 255, 255, 0.2);
        }
        .modal-img {
            width: 100%;
            border-radius: 12px;
            margin-bottom: 20px;
        }
        .detail-row {
            display: flex;
            padding: 12px 0;
            border-bottom: 1px solid var(--card-border);
        }
        .detail-label {
            font-weight: 600;
            color: var(--text-muted);
            width: 180px;
            flex-shrink: 0;
        }
        .detail-value {
            color: var(--text);
            word-break: break-all;
        }
        .loading {
            text-align: center;
            padding: 40px;
            color: var(--text-muted);
        }
        .spinner {
            border: 3px solid rgba(255, 255, 255, 0.1);
            border-top: 3px solid var(--primary);
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 0 auto 16px;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        @keyframes fadeInDown {
            from {
                opacity: 0;
                transform: translateY(-20px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
        @keyframes fadeInUp {
            from {
                opacity: 0;
                transform: translateY(20px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
        @media (max-width: 768px) {
            .header h1 { font-size: 2rem; }
            .stats-grid { grid-template-columns: repeat(2, 1fr); }
            .charts-grid { grid-template-columns: 1fr; }
            .filters { flex-direction: column; }
            .filter-group { min-width: 100%; }
            table { font-size: 0.75rem; }
            th, td { padding: 8px; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🌿 Plant Identification Analytics</h1>
            <p>Track and analyze plant identification and diagnosis requests</p>
        </div>

        <!-- Statistics Cards -->
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-value" id="totalRequests">0</div>
                <div class="stat-label">Total Requests</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" id="avgResponseTime">0s</div>
                <div class="stat-label">Avg Response Time</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" id="successRate">0%</div>
                <div class="stat-label">Healthy Plants</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" id="uniqueDevices">0</div>
                <div class="stat-label">Unique Devices</div>
            </div>
        </div>

        <!-- Charts -->
        <div class="charts-grid">
            <div class="chart-card">
                <div class="chart-title">Function Distribution</div>
                <canvas id="functionChart"></canvas>
            </div>
            <div class="chart-card">
                <div class="chart-title">Response Time Trend</div>
                <canvas id="responseTimeChart"></canvas>
            </div>
            <div class="chart-card">
                <div class="chart-title">Health Status Distribution</div>
                <canvas id="healthChart"></canvas>
            </div>
            <div class="chart-card">
                <div class="chart-title">Top Countries</div>
                <canvas id="countryChart"></canvas>
            </div>
        </div>

        <!-- Filters & Data Table -->
        <div class="card">
            <div class="filters">
                <div class="filter-group">
                    <label>Device ID</label>
                    <select id="filterDevice">
                        <option value="">All Devices</option>
                    </select>
                </div>
                <div class="filter-group">
                    <label>Function</label>
                    <select id="filterFunction">
                        <option value="">All Functions</option>
                        <option value="Plant identify">Plant Identify</option>
                        <option value="Diagnose">Diagnose</option>
                    </select>
                </div>
                <div class="filter-group">
                    <label>Health Status</label>
                    <select id="filterHealth">
                        <option value="">All Status</option>
                        <option value="true">Healthy</option>
                        <option value="false">Unhealthy</option>
                        <option value="null">Unknown</option>
                    </select>
                </div>
                <div class="filter-group">
                    <label>Date From</label>
                    <input type="date" id="filterDateFrom">
                </div>
                <div class="filter-group">
                    <label>Date To</label>
                    <input type="date" id="filterDateTo">
                </div>
                <div class="filter-group" style="display: flex; align-items: flex-end; gap: 8px;">
                    <button class="btn btn-primary" onclick="applyFilters()">Apply</button>
                    <button class="btn btn-secondary" onclick="clearFilters()">Clear</button>
                </div>
            </div>

            <div class="table-wrapper">
                <table>
                    <thead>
                        <tr>
                            <th onclick="sortTable('date')">Date ↕</th>
                            <th onclick="sortTable('device_id')">Device ↕</th>
                            <th onclick="sortTable('function')">Function ↕</th>
                            <th onclick="sortTable('result')">Result ↕</th>
                            <th onclick="sortTable('response_time_seconds')">Response Time ↕</th>
                            <th onclick="sortTable('is_plant_healthy')">Health ↕</th>
                            <th>Image</th>
                        </tr>
                    </thead>
                    <tbody id="tableBody">
                        <tr>
                            <td colspan="7" class="loading">
                                <div class="spinner"></div>
                                Loading data...
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>

            <div class="pagination">
                <button class="btn btn-secondary" onclick="prevPage()" id="prevBtn">Previous</button>
                <span class="page-info" id="pageInfo">Page 1</span>
                <button class="btn btn-secondary" onclick="nextPage()" id="nextBtn">Next</button>
            </div>
        </div>
    </div>

    <!-- Detail Modal -->
    <div class="modal" id="detailModal" onclick="closeModal(event)">
        <div class="modal-content" onclick="event.stopPropagation()">
            <button class="modal-close" onclick="closeModal()">×</button>
            <div id="detailContent"></div>
        </div>
    </div>

    <script>
        let allData = [];
        let filteredData = [];
        let currentPage = 1;
        const itemsPerPage = 20;
        let sortColumn = 'date';
        let sortDirection = -1; // -1 for desc, 1 for asc
        let charts = {};

        // Fetch data on load
        fetchData();

        async function fetchData() {
            try {
                const response = await fetch('/api/analytics/proxy');
                const json = await response.json();
                allData = json.data || [];
                filteredData = [...allData];
                updateUI();
            } catch (error) {
                console.error('Error fetching data:', error);
                document.getElementById('tableBody').innerHTML = 
                    '<tr><td colspan="7" style="text-align:center;color:var(--error);">Error loading data. Please try again.</td></tr>';
            }
        }

        function updateUI() {
            updateStats();
            updateCharts();
            updateTable();
            updateFilters();
        }

        function updateStats() {
            const total = filteredData.length;
            const avgTime = filteredData.filter(d => d.response_time_seconds).reduce((sum, d) => 
                sum + d.response_time_seconds, 0) / (filteredData.filter(d => d.response_time_seconds).length || 1);
            const healthyCount = filteredData.filter(d => d.is_plant_healthy === true).length;
            const uniqueDevices = new Set(filteredData.map(d => d.device_id)).size;

            document.getElementById('totalRequests').textContent = total;
            document.getElementById('avgResponseTime').textContent = avgTime.toFixed(2) + 's';
            document.getElementById('successRate').textContent = 
                total > 0 ? ((healthyCount / total) * 100).toFixed(1) + '%' : '0%';
            document.getElementById('uniqueDevices').textContent = uniqueDevices;
        }

        function updateCharts() {
            // Function distribution
            const functionCounts = {};
            filteredData.forEach(d => {
                functionCounts[d.function] = (functionCounts[d.function] || 0) + 1;
            });

            if (charts.functionChart) charts.functionChart.destroy();
            charts.functionChart = new Chart(document.getElementById('functionChart'), {
                type: 'doughnut',
                data: {
                    labels: Object.keys(functionCounts),
                    datasets: [{
                        data: Object.values(functionCounts),
                        backgroundColor: ['rgba(59, 130, 246, 0.8)', 'rgba(236, 72, 153, 0.8)', 'rgba(16, 185, 129, 0.8)']
                    }]
                },
                options: {
                    responsive: true,
                    plugins: {
                        legend: { labels: { color: '#f1f5f9' } }
                    }
                }
            });

            // Response time trend (last 20)
            const recentData = filteredData.filter(d => d.response_time_seconds).slice(0, 20).reverse();
            if (charts.responseTimeChart) charts.responseTimeChart.destroy();
            charts.responseTimeChart = new Chart(document.getElementById('responseTimeChart'), {
                type: 'line',
                data: {
                    labels: recentData.map((_, i) => i + 1),
                    datasets: [{
                        label: 'Response Time (s)',
                        data: recentData.map(d => d.response_time_seconds),
                        borderColor: 'rgba(59, 130, 246, 1)',
                        backgroundColor: 'rgba(59, 130, 246, 0.1)',
                        tension: 0.4
                    }]
                },
                options: {
                    responsive: true,
                    scales: {
                        y: { ticks: { color: '#94a3b8' }, grid: { color: 'rgba(255,255,255,0.1)' } },
                        x: { ticks: { color: '#94a3b8' }, grid: { color: 'rgba(255,255,255,0.1)' } }
                    },
                    plugins: {
                        legend: { labels: { color: '#f1f5f9' } }
                    }
                }
            });

            // Health status
            const healthCounts = {
                'Healthy': filteredData.filter(d => d.is_plant_healthy === true).length,
                'Unhealthy': filteredData.filter(d => d.is_plant_healthy === false).length,
                'Unknown': filteredData.filter(d => d.is_plant_healthy === null).length
            };
            if (charts.healthChart) charts.healthChart.destroy();
            charts.healthChart = new Chart(document.getElementById('healthChart'), {
                type: 'bar',
                data: {
                    labels: Object.keys(healthCounts),
                    datasets: [{
                        label: 'Count',
                        data: Object.values(healthCounts),
                        backgroundColor: ['rgba(16, 185, 129, 0.8)', 'rgba(239, 68, 68, 0.8)', 'rgba(148, 163, 184, 0.8)']
                    }]
                },
                options: {
                    responsive: true,
                    scales: {
                        y: { ticks: { color: '#94a3b8' }, grid: { color: 'rgba(255,255,255,0.1)' } },
                        x: { ticks: { color: '#94a3b8' }, grid: { color: 'rgba(255,255,255,0.1)' } }
                    },
                    plugins: {
                        legend: { display: false }
                    }
                }
            });

            // Country distribution
            const countryCounts = {};
            filteredData.forEach(d => {
                const country = d.country_code || 'unknown';
                countryCounts[country] = (countryCounts[country] || 0) + 1;
            });
            const topCountries = Object.entries(countryCounts)
                .sort((a, b) => b[1] - a[1])
                .slice(0, 10);
            
            if (charts.countryChart) charts.countryChart.destroy();
            charts.countryChart = new Chart(document.getElementById('countryChart'), {
                type: 'bar',
                data: {
                    labels: topCountries.map(c => c[0]),
                    datasets: [{
                        label: 'Requests',
                        data: topCountries.map(c => c[1]),
                        backgroundColor: 'rgba(139, 92, 246, 0.8)'
                    }]
                },
                options: {
                    responsive: true,
                    indexAxis: 'y',
                    scales: {
                        y: { ticks: { color: '#94a3b8' }, grid: { color: 'rgba(255,255,255,0.1)' } },
                        x: { ticks: { color: '#94a3b8' }, grid: { color: 'rgba(255,255,255,0.1)' } }
                    },
                    plugins: {
                        legend: { display: false }
                    }
                }
            });
        }

        function updateTable() {
            // Sort data
            const sorted = [...filteredData].sort((a, b) => {
                let aVal = a[sortColumn];
                let bVal = b[sortColumn];
                if (aVal == null) aVal = '';
                if (bVal == null) bVal = '';
                return sortDirection * (aVal > bVal ? 1 : aVal < bVal ? -1 : 0);
            });

            // Paginate
            const start = (currentPage - 1) * itemsPerPage;
            const end = start + itemsPerPage;
            const pageData = sorted.slice(start, end);

            // Render table
            const tbody = document.getElementById('tableBody');
            if (pageData.length === 0) {
                tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:var(--text-muted);">No data found</td></tr>';
            } else {
                tbody.innerHTML = pageData.map((row, idx) => {
                    const date = new Date(row.date).toLocaleString();
                    const health = row.is_plant_healthy === true ? '<span class="badge badge-healthy">Healthy</span>' :
                                   row.is_plant_healthy === false ? '<span class="badge badge-unhealthy">Unhealthy</span>' :
                                   '<span class="badge badge-unknown">Unknown</span>';
                    const func = row.function === 'Plant identify' ? '<span class="badge badge-identify">Identify</span>' :
                                 '<span class="badge badge-diagnose">Diagnose</span>';
                    const img = row.image_url ? 
                        `<img src="${row.image_url}" class="img-thumb" onclick="showImage('${row.image_url}', event)" />` :
                        '<span style="color:var(--text-dim);">-</span>';
                    const responseTime = row.response_time_seconds ? row.response_time_seconds.toFixed(2) + 's' : '-';
                    const result = row.result || '-';

                    return `<tr onclick="showDetail(${start + idx})">
                        <td>${date}</td>
                        <td>${row.device_id}</td>
                        <td>${func}</td>
                        <td>${result}</td>
                        <td>${responseTime}</td>
                        <td>${health}</td>
                        <td>${img}</td>
                    </tr>`;
                }).join('');
            }

            // Update pagination
            const totalPages = Math.ceil(sorted.length / itemsPerPage) || 1;
            document.getElementById('pageInfo').textContent = `Page ${currentPage} of ${totalPages}`;
            document.getElementById('prevBtn').disabled = currentPage === 1;
            document.getElementById('nextBtn').disabled = currentPage >= totalPages;
        }

        function updateFilters() {
            // Populate device filter
            const devices = [...new Set(allData.map(d => d.device_id))].sort();
            const deviceSelect = document.getElementById('filterDevice');
            const currentDevice = deviceSelect.value;
            deviceSelect.innerHTML = '<option value="">All Devices</option>' +
                devices.map(d => `<option value="${d}" ${d === currentDevice ? 'selected' : ''}>${d}</option>`).join('');
        }

        function applyFilters() {
            const device = document.getElementById('filterDevice').value;
            const func = document.getElementById('filterFunction').value;
            const health = document.getElementById('filterHealth').value;
            const dateFrom = document.getElementById('filterDateFrom').value;
            const dateTo = document.getElementById('filterDateTo').value;

            filteredData = allData.filter(row => {
                if (device && row.device_id !== device) return false;
                if (func && row.function !== func) return false;
                if (health !== '' && String(row.is_plant_healthy) !== health) return false;
                if (dateFrom && new Date(row.date) < new Date(dateFrom)) return false;
                if (dateTo && new Date(row.date) > new Date(dateTo + 'T23:59:59')) return false;
                return true;
            });

            currentPage = 1;
            updateUI();
        }

        function clearFilters() {
            document.getElementById('filterDevice').value = '';
            document.getElementById('filterFunction').value = '';
            document.getElementById('filterHealth').value = '';
            document.getElementById('filterDateFrom').value = '';
            document.getElementById('filterDateTo').value = '';
            filteredData = [...allData];
            currentPage = 1;
            updateUI();
        }

        function sortTable(column) {
            if (sortColumn === column) {
                sortDirection *= -1;
            } else {
                sortColumn = column;
                sortDirection = -1;
            }
            updateTable();
        }

        function prevPage() {
            if (currentPage > 1) {
                currentPage--;
                updateTable();
            }
        }

        function nextPage() {
            const totalPages = Math.ceil(filteredData.length / itemsPerPage);
            if (currentPage < totalPages) {
                currentPage++;
                updateTable();
            }
        }

        function showDetail(index) {
            const row = filteredData.sort((a, b) => {
                let aVal = a[sortColumn] || '';
                let bVal = b[sortColumn] || '';
                return sortDirection * (aVal > bVal ? 1 : aVal < bVal ? -1 : 0);
            })[(currentPage - 1) * itemsPerPage + index];

            const img = row.image_url ? `<img src="${row.image_url}" class="modal-img" />` : '';
            const health = row.is_plant_healthy === true ? 'Healthy' :
                           row.is_plant_healthy === false ? 'Unhealthy' : 'Unknown';

            document.getElementById('detailContent').innerHTML = `
                ${img}
                <div class="detail-row">
                    <div class="detail-label">Date</div>
                    <div class="detail-value">${new Date(row.date).toLocaleString()}</div>
                </div>
                <div class="detail-row">
                    <div class="detail-label">Device ID</div>
                    <div class="detail-value">${row.device_id}</div>
                </div>
                <div class="detail-row">
                    <div class="detail-label">Country</div>
                    <div class="detail-value">${row.country_code || 'Unknown'}</div>
                </div>
                <div class="detail-row">
                    <div class="detail-label">App Version</div>
                    <div class="detail-value">${row.app_version || 'Unknown'}</div>
                </div>
                <div class="detail-row">
                    <div class="detail-label">Function</div>
                    <div class="detail-value">${row.function}</div>
                </div>
                <div class="detail-row">
                    <div class="detail-label">Result</div>
                    <div class="detail-value">${row.result || '-'}</div>
                </div>
                <div class="detail-row">
                    <div class="detail-label">Response Time</div>
                    <div class="detail-value">${row.response_time_seconds ? row.response_time_seconds.toFixed(3) + 's' : 'N/A'}</div>
                </div>
                <div class="detail-row">
                    <div class="detail-label">Health Status</div>
                    <div class="detail-value">${health}</div>
                </div>
                <div class="detail-row">
                    <div class="detail-label">Image URL</div>
                    <div class="detail-value">${row.image_url || 'N/A'}</div>
                </div>
            `;
            document.getElementById('detailModal').classList.add('active');
        }

        function showImage(url, event) {
            event.stopPropagation();
            document.getElementById('detailContent').innerHTML = `<img src="${url}" class="modal-img" />`;
            document.getElementById('detailModal').classList.add('active');
        }

        function closeModal(event) {
            if (!event || event.target.id === 'detailModal' || event.target.classList.contains('modal-close')) {
                document.getElementById('detailModal').classList.remove('active');
            }
        }
    </script>
</body>
</html>
    """)


@app.get("/api/analytics/proxy")
def analytics_proxy():
    """Proxy endpoint to fetch data from external analytics API."""
    import urllib.request
    import urllib.error
    
    try:
        # Fetch from external API
        api_url = "http://localhost:6000/api/analytics/v1/tracking"
        req = urllib.request.Request(api_url)
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
        
        return jsonify(data), 200
    except urllib.error.URLError as e:
        # If external API is not available, return empty data
        return jsonify({
            "data": [],
            "pagination": {
                "page": 1,
                "limit": 100,
                "total": 0,
                "total_pages": 0
            }
        }), 200
    except Exception as e:
        return jsonify({"error": str(e), "data": []}), 500


@app.get("/api/analytics/stats")
def analytics_stats():
    """Get aggregated statistics from the analytics data."""
    import urllib.request
    
    try:
        api_url = "https://plant.cemsoftwareltd.com/api/analytics/v1/tracking"
        req = urllib.request.Request(api_url)
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode('utf-8'))
            data = result.get("data", [])
        
        # Calculate statistics
        total = len(data)
        if total == 0:
            return jsonify({
                "total_requests": 0,
                "avg_response_time": 0,
                "function_distribution": {},
                "health_distribution": {},
                "country_distribution": {},
                "version_distribution": {}
            })
        
        # Aggregate data
        response_times = [d["response_time_seconds"] for d in data if d.get("response_time_seconds")]
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0
        
        function_dist = {}
        health_dist = {"healthy": 0, "unhealthy": 0, "unknown": 0}
        country_dist = {}
        version_dist = {}
        
        for item in data:
            # Function distribution
            func = item.get("function", "unknown")
            function_dist[func] = function_dist.get(func, 0) + 1
            
            # Health distribution
            health = item.get("is_plant_healthy")
            if health is True:
                health_dist["healthy"] += 1
            elif health is False:
                health_dist["unhealthy"] += 1
            else:
                health_dist["unknown"] += 1
            
            # Country distribution
            country = item.get("country_code", "unknown")
            country_dist[country] = country_dist.get(country, 0) + 1
            
            # Version distribution
            version = item.get("app_version", "unknown")
            version_dist[version] = version_dist.get(version, 0) + 1
        
        return jsonify({
            "total_requests": total,
            "avg_response_time": round(avg_response_time, 3),
            "function_distribution": function_dist,
            "health_distribution": health_dist,
            "country_distribution": country_dist,
            "version_distribution": version_dist
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
