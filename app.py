from __future__ import annotations

import subprocess
import uuid
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

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
OUTPUT_DIR = DATA_DIR / "converted"

for directory in (UPLOAD_DIR, OUTPUT_DIR):
    directory.mkdir(parents=True, exist_ok=True)

MIN_FPS = 1
MAX_FPS = 60
MAX_DURATION = 3600  # seconds

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
                .tag { font-size: 12px; text-transform: uppercase; letter-spacing: 0.08em; color: var(--muted); }
                @media (max-width: 900px) { .grid { grid-template-columns: 1fr; } }
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
                    <div class="pill" id="currentFps">Chưa có video</div>
                </div>

                <div class="grid" style="margin-top: 16px;">
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

                let fileId = null;
                let debounceTimer = null;
                let activeController = null;

                function setStatus(text) { statusEl.textContent = text; }

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
            </script>
        </body>
        </html>
        """,
        min_fps=MIN_FPS,
        max_fps=MAX_FPS,
        max_duration=MAX_DURATION,
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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
