# Media Converter Pro

> Công cụ chuyển đổi video, ảnh và sticker chuyên nghiệp với kiến trúc Frontend (Next.js) + Backend (Flask API)

## 🏗️ Architecture

```
video-speed/
├── frontend/          # Next.js 14 App (React + TypeScript + Tailwind)
└── backend/           # Flask API (Python)
```

## 🚀 Quick Start

### Prerequisites
- **Node.js** 18+ (for Frontend  
- **Python** 3.9+ (for Backend)
- **ffmpeg** (for media conversions)
- **pip** (Python package manager)

### Backend Setup

```bash
cd backend

# Create virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run Flask server
python app.py
```

Backend will start on **http://localhost:5000**

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Run Next.js dev server
npm run dev
```

Frontend will start on **http://localhost:3000**

## 📋 Features

### ✅ Implemented
- **Video FPS Converter** - Change video frame rate (1-60 FPS)
- API Client with TypeScript
- Dark theme with glassmorphism
- Responsive design

### 🔨 Coming Soon
- Image format conversions (PNG/JPG ↔ WebP)
- GIF to WebP conversion
- Video to animated WebP
- Batch conversions
- TGS to GIF (Telegram stickers)
- WebM to GIF
- Android Logs viewer (real-time)
- Timber Logs viewer

## 🛠️ Tech Stack

**Frontend:**
- Next.js 14 (App Router)
- TypeScript
- Tailwind CSS
- Poppins + Open Sans fonts

**Backend:**
- Flask 3.0
- Flask-CORS
- FFmpeg
- SQLite (for logs)

## 📝 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/upload` | POST | Upload video file |
| `/convert` | POST | Convert video FPS |
| `/png-to-webp` | POST | Convert image to WebP |
| `/gif-to-webp` | POST | Convert GIF to WebP |
| `/api/android-log` | GET/POST/DELETE | Android logs CRUD |
| `/api/android-log/stream` | GET | Real-time logs (SSE) |

## 🎨 Design System

**Colors:**
- Primary: `#3B82F6` (Blue)
- CTA: `#F97316` (Orange)
- Background: `#0A0E27` (Dark)

**Typography:**
- Headings: Poppins (500-800)
- Body: Open Sans (300-700)

## 📦 Environment Variables

Create `.env.local` in `frontend/`:

```env
NEXT_PUBLIC_API_URL=http://localhost:5000
```

## 🔧 Development

**Backend:**
```bash
cd backend
python app.py  # Runs on port 5000 with debug=True
```

**Frontend:**
```bash
cd frontend
npm run dev    # Runs on port 3000 with hot reload
```

## 📄 License

MIT

---

**Made with ❤️ using Next.js & Flask**
