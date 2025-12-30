# Video FPS Web Server

Python Flask app that lets users upload a video, adjust target FPS with a slider, and preview the converted output immediately.

## Quick start
```
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```
App listens on http://localhost:8080. Upload a video, drag the FPS slider (1–60), preview updates each time.

## Notes
- Uses ffmpeg for conversion (must be installed and in PATH).
- Converted previews are stored temporarily and cleaned up after each response; originals stay under `data/uploads/`.
- Default encoder is H.264 with ultrafast preset for quick previews.
- Export: nhập số giây, bấm “Export & tải về” để tải clip (FPS theo slider, thời lượng theo ô nhập). Nếu thời lượng lớn hơn video gốc, clip sẽ tự lặp để đủ thời gian.
