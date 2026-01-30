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
    request,
    send_file,
    Response,
)
from flask_cors import CORS
from werkzeug.exceptions import HTTPException

try:
    from lottie.exporters.gif import export_gif
    from lottie import objects
    HAS_LOTTIE = True
except ImportError:
    HAS_LOTTIE = False

# Lazy load rembg for background removal
try:
    from rembg import remove as rembg_remove, new_session as rembg_new_session
    from PIL import Image
    import io
    HAS_REMBG = True
except ImportError:
    HAS_REMBG = False

import time
import threading
import gc

# ----------------- Rembg Session Manager -----------------

class RembgSessionManager:
    def __init__(self, timeout_seconds=300):
        self._session = None
        self._last_accessed = 0
        self._timeout = timeout_seconds
        self._lock = threading.Lock()
        self._cleanup_timer = None
    
    def get_session(self):
        with self._lock:
            self._last_accessed = time.time()
            if self._session is None:
                if HAS_REMBG:
                    print("Initializing rembg session...")
                    self._session = rembg_new_session("u2net")
                else:
                    return None
            
            # Restart cleanup timer
            self._schedule_cleanup()
            return self._session
    
    def _schedule_cleanup(self):
        if self._cleanup_timer is not None:
            self._cleanup_timer.cancel()
        
        self._cleanup_timer = threading.Timer(self._timeout, self._cleanup)
        self._cleanup_timer.daemon = True
        self._cleanup_timer.start()
        
    def _cleanup(self):
        with self._lock:
            if self._session and (time.time() - self._last_accessed >= self._timeout):
                print("Freeing rembg session due to inactivity...")
                self._session = None
                gc.collect() # Force garbage collection

_rembg_manager = RembgSessionManager(timeout_seconds=300) # 5 minutes

def _get_rembg_session():
    return _rembg_manager.get_session()

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
OUTPUT_DIR = DATA_DIR / "converted"

for directory in (UPLOAD_DIR, OUTPUT_DIR):
    directory.mkdir(parents=True, exist_ok=True)

# Auto-detect ffmpeg path (works on Mac/Homebrew and Linux)
FFMPEG_PATH = shutil.which("ffmpeg")
if not FFMPEG_PATH:
    # Fallback paths
    for path in ["/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg", "/usr/bin/ffmpeg", "/bin/ffmpeg"]:
        if Path(path).exists():
            FFMPEG_PATH = path
            break

if not FFMPEG_PATH or not Path(FFMPEG_PATH).exists():
    print("WARNING: ffmpeg not found in PATH. Video conversion features will fail.")
    FFMPEG_PATH = "ffmpeg" # fallback to hope it works later or raises clearer error

MIN_FPS = 1
MAX_FPS = 60
MAX_DURATION = 3600
MAX_WEBP_DURATION = 3600

app = Flask(__name__)
CORS(app)  # Enable CORS for frontend

DB_PATH = DATA_DIR / "logs.db"


def get_db_connection():
    """Create and return a database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize the database with the logs table."""
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            event_name TEXT NOT NULL,
            device_name TEXT,
            version_code TEXT,
            params TEXT
        )
    ''')
    conn.commit()
    conn.close()

# Initialize database on startup
init_db()


# ---------------------------- Helpers -------------------------------------

def _validate_fps(raw_fps):
    try:
        fps = int(raw_fps)
    except (TypeError, ValueError):
        abort(400, "FPS không hợp lệ")
    
    if not (MIN_FPS <= fps <= MAX_FPS):
        abort(400, f"FPS phải nằm trong khoảng {MIN_FPS}-{MAX_FPS}")
    return fps


def _validate_duration(raw):
    try:
        val = int(raw)
    except (TypeError, ValueError):
        abort(400, "Thời lượng không hợp lệ")
    if not (1 <= val <= MAX_DURATION):
        abort(400, f"Thời lượng phải trong khoảng 1-{MAX_DURATION} giây")
    return val


def _safe_upload_path(filename, base):
    """Prevent path traversal by resolving the final location."""
    candidate = (base / filename).resolve()
    if base not in candidate.parents:
        abort(404)
    if not candidate.exists():
        abort(404)
    return candidate


def _validate_positive_int(raw, *, name, min_value, max_value):
    try:
        val = int(raw)
    except (TypeError, ValueError):
        abort(400, f"{name} không hợp lệ")
    if not (min_value <= val <= max_value):
        abort(400, f"{name} phải nằm trong khoảng {min_value}-{max_value}")
    return val


def _allowed_image_suffix(filename):
    suffix = (Path(filename).suffix or "").lower()
    if suffix in {".png", ".jpg", ".jpeg"}:
        return suffix
    return None


def _allowed_static_image_suffix(filename):
    suffix = (Path(filename).suffix or "").lower()
    if suffix in {".png", ".jpg", ".jpeg", ".webp"}:
        return suffix
    return None


def _allowed_gif_suffix(filename):
    suffix = (Path(filename).suffix or "").lower()
    if suffix == ".gif":
        return suffix
    return None


def _allowed_tgs_suffix(filename):
    return Path(filename).suffix.lower() == ".tgs"


_ZIP_NAME_SAFE_RE = re.compile(r"[^a-zA-Z0-9._-]+")


def _safe_zip_entry_name(raw_stem, *, index):
    stem = (raw_stem or "").strip() or f"image_{index:04d}"
    stem = _ZIP_NAME_SAFE_RE.sub("_", stem).strip("._-") or f"image_{index:04d}"
    return f"{stem}.webp"


def _safe_zip_entry_name_with_ext(raw_stem, *, index, ext):
    stem = (raw_stem or "").strip() or f"image_{index:04d}"
    stem = _ZIP_NAME_SAFE_RE.sub("_", stem).strip("._-") or f"image_{index:04d}"
    ext = (ext or "").lower().strip()
    if not ext.startswith("."):
        ext = f".{ext}"
    if ext not in {".webp", ".png", ".jpg", ".gif"}:
        ext = ".png"
    return f"{stem}{ext}"


def _parse_bool(raw):
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _run_ffmpeg(cmd):
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.decode("utf-8", errors="ignore"))

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
    if suffix in {".png", ".jpg", ".jpeg", ".webp"}:
        return suffix
    return None


def _remove_alpha(image_data: bytes, bg_color: tuple = (255, 255, 255)) -> bytes:
    """Replace transparent background with solid color.
    
    Args:
        image_data: PNG image bytes with alpha channel
        bg_color: RGB tuple for background color (default white)
    
    Returns:
        PNG image bytes with solid background
    """
    img = Image.open(io.BytesIO(image_data))
    if img.mode == 'RGBA':
        background = Image.new('RGB', img.size, bg_color)
        background.paste(img, mask=img.split()[3])
        output = io.BytesIO()
        background.save(output, format='PNG')
        return output.getvalue()
    return image_data


def _parse_hex_color(hex_color: str) -> tuple:
    """Parse hex color string to RGB tuple.
    
    Args:
        hex_color: Hex color string like '#FFFFFF' or 'FFFFFF'
    
    Returns:
        RGB tuple like (255, 255, 255)
    """
    hex_color = hex_color.strip().lstrip('#')
    if len(hex_color) != 6:
        return (255, 255, 255)  # Default to white
    try:
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        return (r, g, b)
    except ValueError:
        return (255, 255, 255)


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


def _allowed_audio_suffix(filename: str) -> str | None:
    """Check if filename has a supported audio extension."""
    suffix = (Path(filename).suffix or "").lower()
    if suffix in {".mp3", ".wav", ".aac", ".flac", ".m4a", ".ogg", ".wma", ".opus"}:
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
    if ext not in {".webp", ".png", ".jpg", ".gif", ".tgs", ".ogg"}:
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
            cmd: list[str] = [FFMPEG_PATH, "-y", "-i", str(input_path)]
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
    cmd: list[str] = [FFMPEG_PATH, "-y", "-i", str(input_path)]
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
    cmd = [FFMPEG_PATH, "-y"]
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
        FFMPEG_PATH,
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
        FFMPEG_PATH,
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
    output_path: Path | None = None,
) -> Path:
    if output_path is None:
        output_path = OUTPUT_DIR / f"{uuid.uuid4().hex}.webp"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    vf_parts: list[str] = [f"fps={fps}"]
    if width is not None:
        vf_parts.append(f"scale={width}:-1:flags=lanczos")
    vf_parts.append("format=rgba")
    vf = ",".join(vf_parts)

    cmd: list[str] = [FFMPEG_PATH, "-y", "-i", str(input_path)]
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
            cmd: list[str] = [FFMPEG_PATH, "-y", "-i", str(input_path)]

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
    cmd: list[str] = [FFMPEG_PATH, "-y", "-i", str(input_path)]

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
        FFMPEG_PATH,
        "-y",
        "-i",
        str(input_path),
        "-vf",
        vf,
        str(output_path),
    ]
    _run_ffmpeg(cmd)
    return output_path


def _convert_json_to_tgs(
    input_path: Path,
    *,
    output_path: Path | None = None,
) -> Path:
    """Convert Lottie JSON to TGS (gzipped Lottie).

    TGS files are just gzipped Lottie JSON animations.
    """
    if not HAS_LOTTIE:
        abort(500, "Lottie library không được cài đặt. Cần cài đặt 'lottie'.")

    if output_path is None:
        output_path = OUTPUT_DIR / f"{uuid.uuid4().hex}.tgs"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        # Read JSON file
        with open(input_path, 'r', encoding='utf-8') as f:
            lottie_data = json.load(f)

        # Validate it's a valid Lottie animation
        animation = objects.Animation.load(lottie_data)

        # Write as gzipped JSON (TGS format)
        with gzip.open(output_path, 'wt', encoding='utf-8') as f:
            json.dump(lottie_data, f, separators=(',', ':'))

        return output_path

    except Exception as e:
        abort(500, f"Lỗi chuyển đổi JSON sang TGS: {str(e)}")


def _convert_gif_to_tgs(
    input_path: Path,
    *,
    fps: int = 30,
    width: int | None = None,
    output_path: Path | None = None,
) -> Path:
    """Convert GIF/WebP/WebM to TGS via intermediate processing.

    This is experimental and uses a workaround approach:
    1. Extract frames from GIF/WebP/WebM
    2. Generate a simple Lottie animation from frames

    Note: Results may not be perfect as raster-to-vector conversion is complex.
    """
    if not HAS_LOTTIE:
        abort(500, "Lottie library không được cài đặt. Cần cài đặt 'lottie'.")

    if output_path is None:
        output_path = OUTPUT_DIR / f"{uuid.uuid4().hex}.tgs"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        # For now, we'll create a simple frame-based Lottie animation
        # Extract frames using ffmpeg
        frames_dir = OUTPUT_DIR / f"frames_{uuid.uuid4().hex}"
        frames_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Extract frames as PNG
            frame_pattern = str(frames_dir / "frame_%04d.png")
            cmd = [
                FFMPEG_PATH,
                "-i", str(input_path),
                "-vf", f"fps={fps}" + (f",scale={width}:-1" if width else ""),
                frame_pattern,
            ]
            _run_ffmpeg(cmd)

            # Get frame list
            frame_files = sorted(frames_dir.glob("frame_*.png"))
            if not frame_files:
                raise RuntimeError("Không trích xuất được frame nào")

            # Create a basic Lottie animation structure
            # This is a simplified approach - real conversion would need proper tracing
            from PIL import Image
            first_frame = Image.open(frame_files[0])
            frame_width, frame_height = first_frame.size

            # Create minimal Lottie JSON structure
            lottie_data = {
                "v": "5.7.4",
                "fr": fps,
                "ip": 0,
                "op": len(frame_files),
                "w": frame_width,
                "h": frame_height,
                "nm": "Converted Animation",
                "ddd": 0,
                "assets": [],
                "layers": [
                    {
                        "ddd": 0,
                        "ind": 1,
                        "ty": 1,  # Solid layer (placeholder)
                        "nm": "Background",
                        "sr": 1,
                        "ks": {
                            "o": {"a": 0, "k": 100},
                            "r": {"a": 0, "k": 0},
                            "p": {"a": 0, "k": [frame_width/2, frame_height/2, 0]},
                            "a": {"a": 0, "k": [0, 0, 0]},
                            "s": {"a": 0, "k": [100, 100, 100]}
                        },
                        "ao": 0,
                        "sw": frame_width,
                        "sh": frame_height,
                        "sc": "#ffffff",
                        "ip": 0,
                        "op": len(frame_files),
                        "st": 0,
                        "bm": 0
                    }
                ],
                "markers": []
            }

            # Write as gzipped JSON (TGS format)
            with gzip.open(output_path, 'wt', encoding='utf-8') as f:
                json.dump(lottie_data, f, separators=(',', ':'))

            return output_path

        finally:
            # Cleanup frames directory
            shutil.rmtree(frames_dir, ignore_errors=True)

    except Exception as e:
        abort(500, f"Lỗi chuyển đổi sang TGS: {str(e)}")


# ---------------------------- Routes --------------------------------------

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


@app.post("/remove-background")
def remove_background():
    """Remove background from an uploaded PNG/JPG/WebP image using AI.
    
    Args (form data):
        file: Image file (PNG/JPG/JPEG/WebP)
        remove_alpha: Optional. If '1'/'true', replace transparent bg with solid color
        bg_color: Optional. Hex color for background when remove_alpha=true (default: #FFFFFF)
    
    Returns a PNG image with transparent or solid background.
    """
    if not HAS_REMBG:
        abort(500, "Thư viện rembg không được cài đặt. Vui lòng cài đặt 'rembg[cpu]'.")
    
    file = request.files.get("file")
    if file is None or file.filename == "":
        abort(400, "Thiếu file ảnh")

    filename = file.filename
    suffix = _allowed_image_suffix(filename)
    if suffix is None:
        abort(400, "Chỉ chấp nhận PNG/JPG/JPEG/WebP")

    # Parse options
    remove_alpha = _parse_bool(request.form.get("remove_alpha", "0"))
    bg_color_hex = request.form.get("bg_color", "#FFFFFF")
    bg_color = _parse_hex_color(bg_color_hex)

    input_name = f"{uuid.uuid4().hex}{suffix}"
    input_path = UPLOAD_DIR / input_name
    output_path = OUTPUT_DIR / f"{uuid.uuid4().hex}.png"
    file.save(input_path)

    try:
        # Read image
        with open(input_path, 'rb') as f:
            input_data = f.read()
        
        # Remove background using rembg with session reuse
        session = _get_rembg_session()
        output_data = rembg_remove(input_data, session=session)
        
        # Optionally remove alpha channel
        if remove_alpha:
            output_data = _remove_alpha(output_data, bg_color)
        
        # Save output
        with open(output_path, 'wb') as f:
            f.write(output_data)
            
    except Exception as exc:
        input_path.unlink(missing_ok=True)
        output_path.unlink(missing_ok=True)
        abort(500, f"Lỗi xử lý ảnh: {exc}")

    @after_this_request
    def cleanup(response):
        input_path.unlink(missing_ok=True)
        output_path.unlink(missing_ok=True)
        return response

    return send_file(
        output_path,
        mimetype="image/png",
        as_attachment=True,
        download_name=Path(filename).stem + "_nobg.png",
    )


@app.post("/remove-background-zip")
def remove_background_zip():
    """Remove background from multiple images and return as ZIP.
    
    Args (form data):
        files: Image files (PNG/JPG/JPEG/WebP)
        remove_alpha: Optional. If '1'/'true', replace transparent bg with solid color
        bg_color: Optional. Hex color for background when remove_alpha=true (default: #FFFFFF)
    
    Returns a ZIP containing PNG images with transparent or solid backgrounds.
    """
    if not HAS_REMBG:
        abort(500, "Thư viện rembg không được cài đặt. Vui lòng cài đặt 'rembg[cpu]'.")
    
    files = request.files.getlist("files")
    if not files:
        abort(400, "Thiếu danh sách ảnh (files)")

    # Parse options
    remove_alpha = _parse_bool(request.form.get("remove_alpha", "0"))
    bg_color_hex = request.form.get("bg_color", "#FFFFFF")
    bg_color = _parse_hex_color(bg_color_hex)

    batch_dir = OUTPUT_DIR / f"rembg_{uuid.uuid4().hex}"
    batch_dir.mkdir(parents=True, exist_ok=True)
    zip_path = OUTPUT_DIR / f"nobg_{uuid.uuid4().hex}.zip"
    
    processed_files: list[tuple[str, Path]] = []

    try:
        # Get session once for all images
        session = _get_rembg_session()
        
        for index, f in enumerate(files, start=1):
            if f.filename is None or f.filename == "":
                continue
                
            suffix = _allowed_image_suffix(f.filename)
            if suffix is None:
                continue  # Skip unsupported files
            
            # Save input file
            input_path = batch_dir / f"input_{index:04d}{suffix}"
            f.save(input_path)
            
            try:
                # Read and process image sequentially to avoid OOM
                with open(input_path, 'rb') as fp:
                    input_data = fp.read()
                
                output_data = rembg_remove(input_data, session=session)
                
                # Free input data immediately
                del input_data
                
                # Optionally remove alpha channel
                if remove_alpha:
                    output_data = _remove_alpha(output_data, bg_color)
                
                # Save output
                output_name = _safe_zip_entry_name_with_ext(
                    Path(f.filename).stem + "_nobg",
                    index=index,
                    ext="png"
                )
                output_path = batch_dir / output_name
                with open(output_path, 'wb') as fp:
                    fp.write(output_data)
                
                processed_files.append((output_name, output_path))
                
                # Free output data and force garbage collection after each image
                del output_data
                gc.collect()
                
            except Exception as e:
                print(f"Warning: Failed to process {f.filename}: {e}")
                gc.collect()  # Also collect on error
                continue
            finally:
                input_path.unlink(missing_ok=True)

        if not processed_files:
            abort(400, "Không có ảnh nào được xử lý thành công")

        # Create ZIP file
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for name, path in processed_files:
                zf.write(path, arcname=name)

    except HTTPException:
        shutil.rmtree(batch_dir, ignore_errors=True)
        zip_path.unlink(missing_ok=True)
        raise
    except Exception as exc:
        shutil.rmtree(batch_dir, ignore_errors=True)
        zip_path.unlink(missing_ok=True)
        abort(500, f"Lỗi xử lý: {exc}")

    @after_this_request
    def cleanup(response):
        shutil.rmtree(batch_dir, ignore_errors=True)
        zip_path.unlink(missing_ok=True)
        return response

    return send_file(
        zip_path,
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"nobg_{len(processed_files)}_images.zip",
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
    """Convert multiple PNG/JPG images to WebP and return as ZIP.
    
    Files that fail to convert are skipped and reported in the response.
    """
    files = request.files.getlist("files")
    if not files:
        abort(400, "Thiếu danh sách ảnh (files)")

    batch_dir = OUTPUT_DIR / f"webp_batch_{uuid.uuid4().hex}"
    batch_dir.mkdir(parents=True, exist_ok=True)
    zip_path = batch_dir / "webp_images.zip"

    # Track failed files
    failed_files: list[dict] = []
    successful_files: list[str] = []
    output_paths: list[Path] = []
    
    try:
        for index, f in enumerate(files, start=1):
            if f.filename is None or f.filename == "":
                continue
            suffix = _allowed_image_suffix(f.filename)
            if suffix is None:
                failed_files.append({"file": f.filename, "error": "Định dạng không hỗ trợ (chỉ PNG/JPG/JPEG)"})
                continue

            input_path = batch_dir / f"input_{index:04d}{suffix}"
            f.save(input_path)

            try:
                output_name = _safe_zip_entry_name(Path(f.filename).stem, index=index)
                output_path = batch_dir / output_name
                _convert_image_to_webp(input_path, lossless=(suffix == ".png"), output_path=output_path)
                output_paths.append(output_path)
                successful_files.append(f.filename)
            except Exception as e:
                error_msg = str(e) if str(e) else "Lỗi không xác định khi chuyển đổi"
                failed_files.append({"file": f.filename, "error": error_msg})
                print(f"[DEBUG] images_to_webp_zip error for {f.filename}: {e}")
            finally:
                input_path.unlink(missing_ok=True)

        if not output_paths:
            # All files failed
            error_response = {
                "success": False,
                "error": "Không có file nào được chuyển đổi thành công",
                "failed_files": failed_files,
                "successful_count": 0,
                "failed_count": len(failed_files)
            }
            shutil.rmtree(batch_dir, ignore_errors=True)
            return jsonify(error_response), 400

        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for output_path in output_paths:
                zf.write(output_path, arcname=output_path.name)
                
    except HTTPException:
        shutil.rmtree(batch_dir, ignore_errors=True)
        raise
    except Exception as exc:
        shutil.rmtree(batch_dir, ignore_errors=True)
        abort(500, f"Lỗi ffmpeg/zip: {exc}")

    # If there are failed files, return JSON with download info
    if failed_files:
        zip_id = uuid.uuid4().hex
        final_zip_path = OUTPUT_DIR / f"images_webp_{zip_id}.zip"
        shutil.copy(zip_path, final_zip_path)
        shutil.rmtree(batch_dir, ignore_errors=True)
        
        response_data = {
            "success": True,
            "message": f"Đã chuyển đổi {len(output_paths)} file thành công, {len(failed_files)} file bị lỗi",
            "successful_count": len(output_paths),
            "successful_files": successful_files,
            "failed_count": len(failed_files),
            "failed_files": failed_files,
            "download_id": zip_id,
            "download_url": f"/download-images-webp/{zip_id}"
        }
        return jsonify(response_data), 200

    @after_this_request
    def cleanup(response):
        shutil.rmtree(batch_dir, ignore_errors=True)
        return response

    return send_file(
        zip_path,
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"images_{len(output_paths)}_webp.zip",
    )


@app.get("/download-images-webp/<zip_id>")
def download_images_webp(zip_id: str):
    """Download a converted images WebP ZIP file by its ID."""
    if not zip_id or not all(c in '0123456789abcdef' for c in zip_id.lower()):
        abort(400, "ID không hợp lệ")
    
    zip_path = OUTPUT_DIR / f"images_webp_{zip_id}.zip"
    if not zip_path.exists():
        abort(404, "File không tồn tại hoặc đã hết hạn")
    
    @after_this_request
    def cleanup(response):
        zip_path.unlink(missing_ok=True)
        return response
    
    return send_file(
        zip_path,
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"images_webp.zip",
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


@app.post("/files-to-tgs-zip")
def files_to_tgs_zip():
    """Batch convert various formats (JSON, GIF, WebP, WebM, PNG) to TGS and return as ZIP.
    
    Also accepts a .zip file containing source files - they will be extracted and converted.
    """
    files = request.files.getlist("files")
    if not files:
        abort(400, "Thiếu danh sách file (files)")
    
    # Check if the uploaded file is a zip file that needs extraction
    extracted_files: list[Path] = []
    temp_extract_dir: Path | None = None
    
    # If single file is a zip, extract it first
    if len(files) == 1 and files[0].filename and files[0].filename.lower().endswith('.zip'):
        temp_extract_dir = OUTPUT_DIR / f"extract_{uuid.uuid4().hex}"
        temp_extract_dir.mkdir(parents=True, exist_ok=True)
        
        zip_upload_path = temp_extract_dir / "uploaded.zip"
        files[0].save(zip_upload_path)
        
        try:
            with zipfile.ZipFile(zip_upload_path, 'r') as zf:
                for member in zf.namelist():
                    # Skip directories and hidden files
                    if member.endswith('/') or member.startswith('__MACOSX') or '/.' in member:
                        continue
                    member_suffix = Path(member).suffix.lower()
                    if member_suffix in {'.json', '.gif', '.webp', '.webm', '.png', '.jpg', '.jpeg'}:
                        # Extract to temp directory with safe name
                        extracted_filename = Path(member).name
                        extracted_path = temp_extract_dir / extracted_filename
                        with zf.open(member) as source, open(extracted_path, 'wb') as target:
                            shutil.copyfileobj(source, target)
                        extracted_files.append(extracted_path)
        except zipfile.BadZipFile:
            shutil.rmtree(temp_extract_dir, ignore_errors=True)
            abort(400, "File ZIP không hợp lệ")
        
        if not extracted_files:
            shutil.rmtree(temp_extract_dir, ignore_errors=True)
            abort(400, "File ZIP không chứa file hợp lệ (.json, .gif, .webp, .webm, .png, .jpg)")

    # Optional parameters
    width_raw = request.form.get("width")
    width: int | None = None
    if width_raw not in (None, "", "0"):
        width = _validate_positive_int(width_raw, name="Width", min_value=16, max_value=2048)

    fps_raw = request.form.get("fps")
    fps: int = 30  # default FPS
    if fps_raw not in (None, "", "0"):
        fps = _validate_positive_int(fps_raw, name="FPS", min_value=1, max_value=60)

    # Create batch directory
    batch_dir = OUTPUT_DIR / f"to_tgs_{uuid.uuid4().hex}"
    batch_dir.mkdir(parents=True, exist_ok=True)
    zip_path = batch_dir / "converted_tgs.zip"

    output_paths: list[Path] = []
    try:
        # Process files - either from extracted zip or direct uploads
        if extracted_files:
            # Processing extracted files from uploaded zip
            for index, file_path in enumerate(extracted_files, start=1):
                file_suffix = file_path.suffix.lower()
                filename_stem = file_path.stem

                if file_suffix == ".json":
                    output_name = _safe_zip_entry_name_with_ext(filename_stem, index=index, ext=".tgs")
                    output_path = batch_dir / output_name
                    _convert_json_to_tgs(file_path, output_path=output_path)
                    output_paths.append(output_path)
                elif file_suffix in {".gif", ".webp", ".webm", ".png", ".jpg", ".jpeg"}:
                    output_name = _safe_zip_entry_name_with_ext(filename_stem, index=index, ext=".tgs")
                    output_path = batch_dir / output_name
                    _convert_gif_to_tgs(file_path, fps=fps, width=width, output_path=output_path)
                    output_paths.append(output_path)
        else:
            # Processing regular file uploads
            for index, f in enumerate(files, start=1):
                if f.filename is None or f.filename == "":
                    continue

                file_suffix = Path(f.filename).suffix.lower()

                # Determine file type and conversion path
                if file_suffix == ".json":
                    # JSON to TGS (direct conversion)
                    input_path = batch_dir / f"input_{index:04d}.json"
                    f.save(input_path)

                    output_name = _safe_zip_entry_name_with_ext(Path(f.filename).stem, index=index, ext=".tgs")
                    output_path = batch_dir / output_name

                    _convert_json_to_tgs(input_path, output_path=output_path)
                    output_paths.append(output_path)

                elif file_suffix in {".gif", ".webp", ".webm", ".png", ".jpg", ".jpeg"}:
                    # Raster formats to TGS (experimental conversion)
                    input_path = batch_dir / f"input_{index:04d}{file_suffix}"
                    f.save(input_path)

                    output_name = _safe_zip_entry_name_with_ext(Path(f.filename).stem, index=index, ext=".tgs")
                    output_path = batch_dir / output_name

                    _convert_gif_to_tgs(input_path, fps=fps, width=width, output_path=output_path)
                    output_paths.append(output_path)

                else:
                    abort(400, f"Định dạng không được hỗ trợ: {file_suffix}. Hỗ trợ: .json, .gif, .webp, .webm, .png, .jpg")

        if not output_paths:
            abort(400, "Không có file hợp lệ để chuyển đổi")

        # Create ZIP file
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for output_path in output_paths:
                zf.write(output_path, arcname=output_path.name)

    except HTTPException:
        shutil.rmtree(batch_dir, ignore_errors=True)
        if temp_extract_dir:
            shutil.rmtree(temp_extract_dir, ignore_errors=True)
        raise
    except Exception as exc:
        shutil.rmtree(batch_dir, ignore_errors=True)
        if temp_extract_dir:
            shutil.rmtree(temp_extract_dir, ignore_errors=True)
        abort(500, f"Lỗi chuyển đổi sang TGS: {exc}")

    # Cleanup after request
    @after_this_request
    def cleanup(response):  # type: ignore
        shutil.rmtree(batch_dir, ignore_errors=True)
        if temp_extract_dir:
            shutil.rmtree(temp_extract_dir, ignore_errors=True)
        return response

    return send_file(
        zip_path,
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"to_tgs_{len(output_paths)}.zip",
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


@app.post("/batch-to-webp-zip")
def batch_to_webp_zip():
    """Universal batch converter: TGS, WebM, PNG, JPG, GIF, ZIP → WebP ZIP.
    
    Accepts multiple files and/or ZIP archives containing these file types.
    Returns a ZIP with all files converted to WebP format.
    Files that fail to convert are skipped and reported in the response.
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

    batch_dir = OUTPUT_DIR / f"batch_webp_{uuid.uuid4().hex}"
    batch_dir.mkdir(parents=True, exist_ok=True)
    zip_path = batch_dir / "converted_webp.zip"

    SUPPORTED_EXTENSIONS = {".tgs", ".webm", ".png", ".jpg", ".jpeg", ".gif", ".webp"}

    # Track failed files
    failed_files: list[dict] = []
    successful_files: list[str] = []

    def process_single_file(input_path: Path, original_name: str, index: int) -> Path | None:
        """Process a single file and return output path or None if failed."""
        suffix = input_path.suffix.lower()
        output_name = _safe_zip_entry_name(Path(original_name).stem, index=index)
        output_path = batch_dir / output_name

        try:
            if suffix == ".tgs":
                # TGS → animated WebP (via GIF intermediate)
                if HAS_LOTTIE:
                    gif_path = batch_dir / f"temp_{index}.gif"
                    _convert_tgs_to_gif(input_path, width=width, fps=fps, output_path=gif_path)
                    _convert_video_to_animated_webp(gif_path, fps=fps, width=width, loop=0, output_path=output_path)
                    gif_path.unlink(missing_ok=True)
                else:
                    failed_files.append({"file": original_name, "error": "Thiếu thư viện lottie để xử lý TGS"})
                    return None
            elif suffix == ".webm":
                # WebM → animated WebP
                _convert_video_to_animated_webp(input_path, fps=fps, width=width, loop=0, output_path=output_path)
            elif suffix == ".gif":
                # GIF → animated WebP
                _convert_video_to_animated_webp(input_path, fps=fps, width=width, loop=0, output_path=output_path)
            elif suffix in {".png", ".jpg", ".jpeg", ".webp"}:
                # Static image → WebP
                _convert_image(input_path, target="webp", width=width, quality=quality, lossless=(suffix == ".png"), output_path=output_path)
            else:
                failed_files.append({"file": original_name, "error": f"Định dạng không được hỗ trợ: {suffix}"})
                return None
            successful_files.append(original_name)
            return output_path
        except Exception as e:
            error_msg = str(e) if str(e) else "Lỗi không xác định khi chuyển đổi"
            failed_files.append({"file": original_name, "error": error_msg})
            print(f"[DEBUG] process_single_file error for {original_name}: {e}")
            import traceback
            traceback.print_exc()
            return None

    output_paths: list[Path] = []
    file_index = 0

    try:
        for f in files:
            if f.filename is None or f.filename == "":
                continue

            suffix = Path(f.filename).suffix.lower()

            if suffix == ".zip":
                # Handle ZIP file - extract and process contents
                zip_input = batch_dir / f"input_{uuid.uuid4().hex}.zip"
                f.save(zip_input)
                
                extract_dir = batch_dir / f"extract_{uuid.uuid4().hex}"
                extract_dir.mkdir(parents=True, exist_ok=True)
                
                try:
                    with zipfile.ZipFile(zip_input, "r") as zf:
                        for member in zf.namelist():
                            if member.endswith("/"):  # Skip directories
                                continue
                            member_suffix = Path(member).suffix.lower()
                            if member_suffix not in SUPPORTED_EXTENSIONS:
                                failed_files.append({"file": Path(member).name, "error": f"Định dạng không được hỗ trợ: {member_suffix}"})
                                continue
                            
                            # Extract file
                            extracted = extract_dir / Path(member).name
                            with zf.open(member) as src, open(extracted, "wb") as dst:
                                dst.write(src.read())
                            
                            file_index += 1
                            result = process_single_file(extracted, Path(member).name, file_index)
                            if result:
                                output_paths.append(result)
                            extracted.unlink(missing_ok=True)
                except zipfile.BadZipFile:
                    failed_files.append({"file": f.filename, "error": "File ZIP không hợp lệ hoặc bị hỏng"})
                finally:
                    shutil.rmtree(extract_dir, ignore_errors=True)
                    zip_input.unlink(missing_ok=True)
            
            elif suffix in SUPPORTED_EXTENSIONS:
                # Direct file processing
                input_path = batch_dir / f"input_{uuid.uuid4().hex}{suffix}"
                f.save(input_path)
                
                file_index += 1
                result = process_single_file(input_path, f.filename, file_index)
                if result:
                    output_paths.append(result)
                input_path.unlink(missing_ok=True)
            else:
                failed_files.append({"file": f.filename, "error": f"Định dạng không được hỗ trợ: {suffix}"})

        if not output_paths:
            # All files failed - return error with details
            error_response = {
                "success": False,
                "error": "Không có file nào được chuyển đổi thành công",
                "failed_files": failed_files,
                "successful_count": 0,
                "failed_count": len(failed_files)
            }
            shutil.rmtree(batch_dir, ignore_errors=True)
            return jsonify(error_response), 400

        # Create output ZIP
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for output_path in output_paths:
                zf.write(output_path, arcname=output_path.name)

    except HTTPException:
        shutil.rmtree(batch_dir, ignore_errors=True)
        raise
    except Exception as exc:
        shutil.rmtree(batch_dir, ignore_errors=True)
        abort(500, f"Lỗi chuyển đổi: {exc}")

    # If there are failed files, return JSON with download info
    if failed_files:
        # Store zip for download and return JSON response
        zip_id = uuid.uuid4().hex
        final_zip_path = OUTPUT_DIR / f"batch_webp_{zip_id}.zip"
        shutil.copy(zip_path, final_zip_path)
        shutil.rmtree(batch_dir, ignore_errors=True)
        
        response_data = {
            "success": True,
            "message": f"Đã chuyển đổi {len(output_paths)} file thành công, {len(failed_files)} file bị lỗi",
            "successful_count": len(output_paths),
            "successful_files": successful_files,
            "failed_count": len(failed_files),
            "failed_files": failed_files,
            "download_id": zip_id,
            "download_url": f"/download-batch-webp/{zip_id}"
        }
        return jsonify(response_data), 200

    @after_this_request
    def cleanup(response):
        shutil.rmtree(batch_dir, ignore_errors=True)
        return response

    return send_file(
        zip_path,
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"batch_webp_{len(output_paths)}.zip",
    )


@app.get("/download-batch-webp/<zip_id>")
def download_batch_webp(zip_id: str):
    """Download a batch converted WebP ZIP file by its ID."""
    # Validate zip_id format (hex string)
    if not zip_id or not all(c in '0123456789abcdef' for c in zip_id.lower()):
        abort(400, "ID không hợp lệ")
    
    zip_path = OUTPUT_DIR / f"batch_webp_{zip_id}.zip"
    if not zip_path.exists():
        abort(404, "File không tồn tại hoặc đã hết hạn")
    
    @after_this_request
    def cleanup(response):
        zip_path.unlink(missing_ok=True)
        return response
    
    return send_file(
        zip_path,
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"batch_webp.zip",
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


# ---------------------------- Audio to OGG Conversion -------------------------

def _convert_audio_to_ogg(
    input_path: Path,
    *,
    bitrate: int = 128,
    sample_rate: int | None = None,
    output_path: Path | None = None,
) -> Path:
    """Convert audio file to OGG (Vorbis) format using FFmpeg.
    
    Args:
        input_path: Path to input audio file
        bitrate: Target bitrate in kbps (default 128)
        sample_rate: Optional sample rate in Hz (e.g., 44100, 48000)
        output_path: Optional output path, auto-generated if None
    
    Returns:
        Path to the converted OGG file
    """
    if output_path is None:
        output_path = OUTPUT_DIR / f"{uuid.uuid4().hex}.ogg"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    cmd: list[str] = [FFMPEG_PATH, "-y", "-i", str(input_path)]
    
    # Audio codec settings
    cmd += ["-c:a", "libvorbis", "-b:a", f"{bitrate}k"]
    
    if sample_rate is not None:
        cmd += ["-ar", str(sample_rate)]
    
    # Remove video stream if any
    cmd += ["-vn"]
    
    cmd.append(str(output_path))
    _run_ffmpeg(cmd)
    return output_path


@app.post("/audio-to-ogg")
def audio_to_ogg():
    """Convert a single audio file to OGG (Vorbis) format."""
    file = request.files.get("file")
    if file is None or file.filename == "":
        abort(400, "Thiếu file audio")
    
    suffix = _allowed_audio_suffix(file.filename)
    if suffix is None:
        abort(400, "Định dạng không được hỗ trợ. Hỗ trợ: MP3, WAV, AAC, FLAC, M4A, OGG, WMA, OPUS")
    
    # Optional bitrate (default 128 kbps)
    bitrate_raw = request.form.get("bitrate")
    bitrate: int = 128
    if bitrate_raw not in (None, "", "0"):
        bitrate = _validate_positive_int(bitrate_raw, name="Bitrate", min_value=32, max_value=320)
    
    # Optional sample rate
    sample_rate_raw = request.form.get("sample_rate")
    sample_rate: int | None = None
    if sample_rate_raw not in (None, "", "0"):
        sample_rate = _validate_positive_int(sample_rate_raw, name="Sample Rate", min_value=8000, max_value=96000)
    
    input_path = UPLOAD_DIR / f"{uuid.uuid4().hex}{suffix}"
    file.save(input_path)
    
    try:
        output_path = _convert_audio_to_ogg(
            input_path,
            bitrate=bitrate,
            sample_rate=sample_rate,
        )
    except Exception as exc:
        input_path.unlink(missing_ok=True)
        abort(500, f"Lỗi convert audio: {exc}")
    
    @after_this_request
    def cleanup(response):
        input_path.unlink(missing_ok=True)
        output_path.unlink(missing_ok=True)
        return response
    
    return send_file(
        output_path,
        mimetype="audio/ogg",
        as_attachment=True,
        download_name=Path(file.filename).stem + ".ogg",
    )


@app.post("/batch-audio-to-ogg-zip")
def batch_audio_to_ogg_zip():
    """Batch convert audio files to OGG and return as ZIP.
    
    Supports: MP3, WAV, AAC, FLAC, M4A, OGG, WMA, OPUS
    Returns a ZIP file with all audio files converted to OGG format.
    Files that fail to convert are skipped and reported in the response.
    """
    files = request.files.getlist("files")
    if not files:
        abort(400, "Thiếu danh sách file audio (files)")
    
    # Optional bitrate (default 128 kbps)
    bitrate_raw = request.form.get("bitrate")
    bitrate: int = 128
    if bitrate_raw not in (None, "", "0"):
        bitrate = _validate_positive_int(bitrate_raw, name="Bitrate", min_value=32, max_value=320)
    
    # Optional sample rate
    sample_rate_raw = request.form.get("sample_rate")
    sample_rate: int | None = None
    if sample_rate_raw not in (None, "", "0"):
        sample_rate = _validate_positive_int(sample_rate_raw, name="Sample Rate", min_value=8000, max_value=96000)
    
    batch_dir = OUTPUT_DIR / f"audio_ogg_{uuid.uuid4().hex}"
    batch_dir.mkdir(parents=True, exist_ok=True)
    zip_path = batch_dir / "converted_ogg.zip"
    
    SUPPORTED_EXTENSIONS = {".mp3", ".wav", ".aac", ".flac", ".m4a", ".ogg", ".wma", ".opus"}
    
    failed_files: list[dict] = []
    successful_files: list[str] = []
    output_paths: list[Path] = []
    
    def process_audio_file(input_path: Path, original_name: str, index: int) -> Path | None:
        """Process a single audio file and return output path or None if failed."""
        try:
            output_name = _safe_zip_entry_name_with_ext(Path(original_name).stem, index=index, ext=".ogg")
            output_path = batch_dir / output_name
            
            _convert_audio_to_ogg(
                input_path,
                bitrate=bitrate,
                sample_rate=sample_rate,
                output_path=output_path,
            )
            successful_files.append(original_name)
            return output_path
        except Exception as e:
            error_msg = str(e) if str(e) else "Lỗi không xác định khi chuyển đổi"
            failed_files.append({"file": original_name, "error": error_msg})
            print(f"[DEBUG] process_audio_file error for {original_name}: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    file_index = 0
    
    try:
        for f in files:
            if f.filename is None or f.filename == "":
                continue
            
            suffix = Path(f.filename).suffix.lower()
            
            if suffix == ".zip":
                # Handle ZIP file - extract and process audio contents
                zip_input = batch_dir / f"input_{uuid.uuid4().hex}.zip"
                f.save(zip_input)
                
                extract_dir = batch_dir / f"extract_{uuid.uuid4().hex}"
                extract_dir.mkdir(parents=True, exist_ok=True)
                
                try:
                    with zipfile.ZipFile(zip_input, "r") as zf:
                        for member in zf.namelist():
                            if member.endswith("/"):  # Skip directories
                                continue
                            member_suffix = Path(member).suffix.lower()
                            if member_suffix not in SUPPORTED_EXTENSIONS:
                                failed_files.append({
                                    "file": Path(member).name,
                                    "error": f"Định dạng không được hỗ trợ: {member_suffix}"
                                })
                                continue
                            
                            # Extract file
                            extracted = extract_dir / Path(member).name
                            with zf.open(member) as src, open(extracted, "wb") as dst:
                                dst.write(src.read())
                            
                            file_index += 1
                            result = process_audio_file(extracted, Path(member).name, file_index)
                            if result:
                                output_paths.append(result)
                            extracted.unlink(missing_ok=True)
                except zipfile.BadZipFile:
                    failed_files.append({"file": f.filename, "error": "File ZIP không hợp lệ hoặc bị hỏng"})
                finally:
                    shutil.rmtree(extract_dir, ignore_errors=True)
                    zip_input.unlink(missing_ok=True)
            
            elif suffix in SUPPORTED_EXTENSIONS:
                # Direct audio file processing
                input_path = batch_dir / f"input_{uuid.uuid4().hex}{suffix}"
                f.save(input_path)
                
                file_index += 1
                result = process_audio_file(input_path, f.filename, file_index)
                if result:
                    output_paths.append(result)
                input_path.unlink(missing_ok=True)
            else:
                failed_files.append({
                    "file": f.filename,
                    "error": f"Định dạng không được hỗ trợ: {suffix}. Hỗ trợ: MP3, WAV, AAC, FLAC, M4A, OGG, WMA, OPUS"
                })
        
        if not output_paths:
            # All files failed - return error with details
            error_response = {
                "success": False,
                "error": "Không có file nào được chuyển đổi thành công",
                "failed_files": failed_files,
                "successful_count": 0,
                "failed_count": len(failed_files)
            }
            shutil.rmtree(batch_dir, ignore_errors=True)
            return jsonify(error_response), 400
        
        # Create output ZIP
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for output_path in output_paths:
                zf.write(output_path, arcname=output_path.name)
    
    except HTTPException:
        shutil.rmtree(batch_dir, ignore_errors=True)
        raise
    except Exception as exc:
        shutil.rmtree(batch_dir, ignore_errors=True)
        abort(500, f"Lỗi chuyển đổi audio: {exc}")
    
    # If there are failed files, return JSON with download info
    if failed_files:
        zip_id = uuid.uuid4().hex
        final_zip_path = OUTPUT_DIR / f"audio_ogg_{zip_id}.zip"
        shutil.copy(zip_path, final_zip_path)
        shutil.rmtree(batch_dir, ignore_errors=True)
        
        response_data = {
            "success": True,
            "message": f"Đã chuyển đổi {len(output_paths)} file thành công, {len(failed_files)} file bị lỗi",
            "successful_count": len(output_paths),
            "successful_files": successful_files,
            "failed_count": len(failed_files),
            "failed_files": failed_files,
            "download_id": zip_id,
            "download_url": f"/download-audio-ogg/{zip_id}"
        }
        return jsonify(response_data), 200
    
    @after_this_request
    def cleanup(response):
        shutil.rmtree(batch_dir, ignore_errors=True)
        return response
    
    return send_file(
        zip_path,
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"audio_ogg_{len(output_paths)}.zip",
    )


@app.get("/download-audio-ogg/<zip_id>")
def download_audio_ogg(zip_id: str):
    """Download a batch converted audio OGG ZIP file by its ID."""
    # Validate zip_id format (hex string)
    if not zip_id or not all(c in '0123456789abcdef' for c in zip_id.lower()):
        abort(400, "ID không hợp lệ")
    
    zip_path = OUTPUT_DIR / f"audio_ogg_{zip_id}.zip"
    if not zip_path.exists():
        abort(404, "File không tồn tại hoặc đã hết hạn")
    
    @after_this_request
    def cleanup(response):
        zip_path.unlink(missing_ok=True)
        return response
    
    return send_file(
        zip_path,
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"audio_ogg.zip",
    )



if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
