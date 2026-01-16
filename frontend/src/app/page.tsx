'use client';

import { useState, useRef } from 'react';
import Link from 'next/link';
import { apiClient } from '@/lib/api-client';
import {
  Upload,
  Zap,
  Download,
  Film,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Sparkles,
  ShieldCheck,
  Wand2,
  Gauge,
} from 'lucide-react';

export default function Home() {
  const [file, setFile] = useState<File | null>(null);
  const [fps, setFps] = useState(30);
  const [status, setStatus] = useState('');
  const [processing, setProcessing] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      setFile(e.dataTransfer.files[0]);
      setStatus('');
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
      setStatus('');
    }
  };

  const handleConvert = async () => {
    if (!file) {
      setStatus('error:Vui lòng chọn file video');
      return;
    }

    try {
      setProcessing(true);
      setStatus('processing:Đang upload video...');

      const uploadResult = await apiClient.uploadVideo(file);

      if (uploadResult.file_id) {
        setStatus('processing:Đang chuyển đổi FPS...');
        const convertedBlob = await apiClient.convertFPS(uploadResult.file_id, fps);

        const url = URL.createObjectURL(convertedBlob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `converted_${fps}fps.mp4`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);

        setStatus(`success:Chuyển đổi thành công! (${fps} FPS)`);
      }
    } catch (error) {
      setStatus(`error:${error instanceof Error ? error.message : 'Lỗi không xác định'}`);
    } finally {
      setProcessing(false);
    }
  };

  const statusParts = status.split(':');
  const statusType = statusParts[0];
  const statusMessage = statusParts.length > 1 ? statusParts.slice(1).join(':') : status;

  const highlightCards = [
    {
      icon: Wand2,
      title: 'AI cân chỉnh FPS',
      description: 'Tự động tối ưu khung hình cho từng cảnh quay.',
      tone: 'bg-sky-50 text-sky-600',
    },
    {
      icon: Zap,
      title: 'Xử lý siêu tốc',
      description: 'Pipeline nhẹ, xử lý ổn định kể cả file lớn.',
      tone: 'bg-orange-50 text-orange-600',
    },
    {
      icon: ShieldCheck,
      title: 'Giữ nguyên chất lượng',
      description: 'Không nén thêm, giữ nguyên bitrate gốc.',
      tone: 'bg-emerald-50 text-emerald-600',
    },
  ];

  const statusTone =
    statusType === 'error'
      ? 'bg-rose-50 border-rose-200 text-rose-700'
      : statusType === 'success'
        ? 'bg-emerald-50 border-emerald-200 text-emerald-700'
        : statusType === 'processing'
          ? 'bg-sky-50 border-sky-200 text-sky-700'
          : 'bg-slate-50 border-slate-200 text-slate-600';

  return (
    <div className="relative min-h-screen overflow-hidden bg-background text-foreground">
      <div className="pointer-events-none absolute inset-0">
        <div
          className="absolute -top-40 right-[-10%] h-[520px] w-[520px] rounded-full bg-[radial-gradient(circle_at_center,rgba(14,165,233,0.45),transparent_65%)] blur-3xl opacity-80 motion-safe:animate-float-slow"
          style={{ animationDelay: '0s' }}
        />
        <div
          className="absolute -bottom-48 left-[-15%] h-[520px] w-[520px] rounded-full bg-[radial-gradient(circle_at_center,rgba(249,115,22,0.35),transparent_60%)] blur-3xl opacity-80 motion-safe:animate-float-medium"
          style={{ animationDelay: '1.5s' }}
        />
        <div
          className="absolute top-1/3 left-[20%] h-[360px] w-[360px] rounded-full bg-[radial-gradient(circle_at_center,rgba(56,189,248,0.35),transparent_65%)] blur-3xl opacity-70 motion-safe:animate-float-slow"
          style={{ animationDelay: '3s' }}
        />
        <div className="absolute inset-0 bg-[linear-gradient(120deg,rgba(255,255,255,0.85),rgba(255,255,255,0))] opacity-60" />
      </div>

      <div className="relative z-10 mx-auto flex min-h-screen max-w-6xl flex-col px-4 pb-16 pt-10 md:pt-16">
        <nav className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-sky-500 via-cyan-400 to-orange-400 shadow-lg shadow-sky-200/70">
              <Film className="h-6 w-6 text-white" />
            </div>
            <div>
              <p className="text-xs font-semibold tracking-[0.3em] text-slate-500">VIDEO SPEED</p>
              <p className="text-xs text-slate-400">AI Media Converter</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className="hidden items-center gap-2 text-xs text-slate-500 sm:flex">
              <span className="rounded-full bg-white/70 px-3 py-1 shadow-sm ring-1 ring-slate-200">
                No watermark
              </span>
              <span className="rounded-full bg-white/70 px-3 py-1 shadow-sm ring-1 ring-slate-200">
                Auto download
              </span>
              <span className="rounded-full bg-white/70 px-3 py-1 shadow-sm ring-1 ring-slate-200">
                1-60 FPS
              </span>
            </div>
            <Link
              href="/tools"
              className="rounded-full bg-white/80 px-4 py-2 text-xs font-semibold text-slate-700 shadow-sm ring-1 ring-slate-200 transition hover:-translate-y-0.5"
            >
              Tools
            </Link>
            <Link
              href="/tracking"
              className="rounded-full bg-slate-900 px-4 py-2 text-xs font-semibold text-white shadow-sm transition hover:-translate-y-0.5"
            >
              Tracking
            </Link>
          </div>
        </nav>

        <main className="mt-10 grid flex-1 gap-10 lg:grid-cols-[1.05fr_0.95fr]">
          <section className="space-y-8">
            <div className="inline-flex w-fit items-center gap-2 rounded-full bg-white/70 px-4 py-1 text-xs font-semibold text-slate-600 shadow-sm ring-1 ring-slate-200">
              <Sparkles className="h-4 w-4 text-sky-500" />
              Tăng tốc FPS mượt, giữ nguyên chất lượng
            </div>

            <div className="space-y-4">
              <h1 className="text-4xl font-heading font-semibold leading-tight text-slate-900 md:text-6xl">
                Chuyển đổi FPS video
                <span className="block bg-gradient-to-r from-sky-500 via-blue-600 to-orange-500 bg-clip-text text-transparent">
                  nhanh gọn như studio.
                </span>
              </h1>
              <p className="text-lg text-slate-600 md:text-xl">
                Kéo thả video, chọn FPS mong muốn và tải về ngay. Giao diện tinh gọn, tốc độ
                tối ưu cho creator & editor.
              </p>
            </div>

            <div className="flex flex-wrap gap-2">
              {['MP4', 'MOV', 'AVI', 'WebM'].map((format) => (
                <span
                  key={format}
                  className="rounded-full bg-white/80 px-3 py-1 text-xs font-semibold text-slate-600 shadow-sm ring-1 ring-slate-200"
                >
                  {format}
                </span>
              ))}
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="rounded-2xl bg-white/80 p-4 shadow-sm ring-1 ring-slate-200">
                <p className="text-xs font-semibold uppercase tracking-widest text-slate-400">
                  Tốc độ xử lý
                </p>
                <p className="mt-2 text-2xl font-semibold text-slate-900">~3x nhanh hơn</p>
                <p className="mt-1 text-xs text-slate-500">Tối ưu pipeline cho file nặng</p>
              </div>
              <div className="rounded-2xl bg-white/80 p-4 shadow-sm ring-1 ring-slate-200">
                <p className="text-xs font-semibold uppercase tracking-widest text-slate-400">
                  Chất lượng giữ nguyên
                </p>
                <p className="mt-2 text-2xl font-semibold text-slate-900">Không nén thêm</p>
                <p className="mt-1 text-xs text-slate-500">Bảo toàn bitrate & metadata</p>
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-3">
              {highlightCards.map((item) => {
                const Icon = item.icon;
                return (
                  <div
                    key={item.title}
                    className="rounded-2xl bg-white/80 p-4 shadow-sm ring-1 ring-slate-200 transition-transform duration-200 hover:-translate-y-1"
                  >
                    <div
                      className={`flex h-10 w-10 items-center justify-center rounded-xl ${item.tone}`}
                    >
                      <Icon className="h-5 w-5" />
                    </div>
                    <p className="mt-3 text-sm font-semibold text-slate-900">{item.title}</p>
                    <p className="mt-1 text-xs text-slate-500">{item.description}</p>
                  </div>
                );
              })}
            </div>

            <div className="flex flex-wrap items-center gap-4 text-sm text-slate-500">
              <span className="inline-flex items-center gap-2">
                <ShieldCheck className="h-4 w-4 text-emerald-500" />
                Không lưu file sau khi xử lý
              </span>
              <span className="inline-flex items-center gap-2">
                <Gauge className="h-4 w-4 text-sky-500" />
                FPS từ 1 đến 60 tuỳ chọn
              </span>
            </div>
          </section>

          <section className="relative">
            <div className="rounded-[32px] bg-gradient-to-br from-sky-400 via-blue-500 to-orange-400 p-[1px] shadow-2xl shadow-sky-200/60">
              <div className="rounded-[31px] bg-white/80 p-6 backdrop-blur-2xl md:p-8">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">
                      Converter
                    </p>
                    <h2 className="mt-2 text-2xl font-heading font-semibold text-slate-900">
                      Video FPS Studio
                    </h2>
                    <p className="mt-2 text-sm text-slate-500">
                      Điều chỉnh FPS chính xác và tải file ngay khi hoàn tất.
                    </p>
                  </div>
                  <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-sky-100 text-sky-600">
                    <Gauge className="h-5 w-5" />
                  </div>
                </div>

                <div
                  className={`group relative mt-8 rounded-2xl border-2 border-dashed p-6 transition-all duration-300 focus-within:ring-2 focus-within:ring-sky-400/60 ${
                    dragActive
                      ? 'border-sky-400 bg-sky-50/80 shadow-lg shadow-sky-200/60'
                      : file
                        ? 'border-emerald-300 bg-emerald-50/70'
                        : 'border-slate-200/80 bg-white/70 hover:border-sky-300 hover:bg-sky-50/40'
                  }`}
                  onDragEnter={handleDrag}
                  onDragLeave={handleDrag}
                  onDragOver={handleDrag}
                  onDrop={handleDrop}
                >
                  <input
                    ref={fileInputRef}
                    id="video-file"
                    type="file"
                    accept="video/*"
                    onChange={handleFileChange}
                    className="hidden"
                    disabled={processing}
                  />

                  <div
                    role="button"
                    tabIndex={0}
                    aria-label="Chọn file video để chuyển đổi"
                    onClick={() => fileInputRef.current?.click()}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter' || event.key === ' ') {
                        event.preventDefault();
                        fileInputRef.current?.click();
                      }
                    }}
                    className="relative z-10 cursor-pointer text-center focus:outline-none"
                  >
                    <div
                      className={`mx-auto flex h-16 w-16 items-center justify-center rounded-2xl transition-transform duration-300 ${
                        file
                          ? 'bg-emerald-500 text-white'
                          : 'bg-gradient-to-br from-sky-500 to-blue-600 text-white group-hover:scale-110'
                      }`}
                    >
                      {file ? <CheckCircle2 className="h-8 w-8" /> : <Upload className="h-8 w-8" />}
                    </div>

                    {file ? (
                      <div className="mt-4 space-y-1">
                        <p className="text-sm font-semibold text-emerald-600">Đã chọn file</p>
                        <p className="truncate text-sm font-medium text-slate-700">{file.name}</p>
                        <p className="text-xs text-slate-500">
                          {(file.size / 1024 / 1024).toFixed(2)} MB
                        </p>
                      </div>
                    ) : (
                      <div className="mt-4 space-y-1">
                        <p className="text-sm font-semibold text-slate-700">
                          Kéo thả video vào đây
                        </p>
                        <p className="text-xs text-slate-500">hoặc click để chọn file</p>
                        <p className="text-xs text-slate-400">Hỗ trợ MP4, AVI, MOV, WebM</p>
                      </div>
                    )}
                  </div>

                  {dragActive && (
                    <div className="pointer-events-none absolute inset-0 rounded-2xl bg-gradient-to-br from-sky-200/70 via-white/20 to-orange-200/60" />
                  )}
                </div>

                <div className="mt-8">
                  <label htmlFor="fps-range" className="flex items-center justify-between">
                    <span className="text-sm font-semibold text-slate-600">Target FPS</span>
                    <span className="rounded-full bg-slate-900 px-4 py-1.5 text-xs font-semibold text-white shadow-sm">
                      {fps} FPS
                    </span>
                  </label>

                  <div className="mt-4">
                    <input
                      id="fps-range"
                      type="range"
                      min="1"
                      max="60"
                      value={fps}
                      onChange={(e) => setFps(Number(e.target.value))}
                      disabled={processing}
                      className="h-2 w-full cursor-pointer appearance-none rounded-full bg-slate-200 accent-sky-500
                        [&::-webkit-slider-thumb]:appearance-none
                        [&::-webkit-slider-thumb]:h-5
                        [&::-webkit-slider-thumb]:w-5
                        [&::-webkit-slider-thumb]:rounded-full
                        [&::-webkit-slider-thumb]:bg-gradient-to-br
                        [&::-webkit-slider-thumb]:from-sky-500
                        [&::-webkit-slider-thumb]:to-blue-600
                        [&::-webkit-slider-thumb]:shadow-md
                        [&::-webkit-slider-thumb]:transition-transform
                        [&::-webkit-slider-thumb]:hover:scale-110
                      "
                    />
                    <div className="mt-2 flex justify-between text-[11px] text-slate-400">
                      <span>1</span>
                      <span>15</span>
                      <span>30</span>
                      <span>45</span>
                      <span>60</span>
                    </div>
                  </div>
                </div>

                <button
                  onClick={handleConvert}
                  disabled={processing || !file}
                  className="group relative mt-8 w-full overflow-hidden rounded-2xl bg-gradient-to-r from-sky-500 via-cyan-500 to-orange-400 px-8 py-4 text-sm font-semibold text-white shadow-lg shadow-sky-200/60 transition-all duration-300 hover:brightness-105 hover:shadow-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400/70 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <span className="relative z-10 flex items-center justify-center gap-3">
                    {processing ? (
                      <>
                        <Loader2 className="h-5 w-5 animate-spin" />
                        Đang xử lý...
                      </>
                    ) : (
                      <>
                        <Download className="h-5 w-5" />
                        Chuyển đổi FPS
                      </>
                    )}
                  </span>
                  <span className="pointer-events-none absolute inset-0 -translate-x-full bg-gradient-to-r from-transparent via-white/60 to-transparent motion-safe:animate-shimmer" />
                </button>

                {status && (
                  <div
                    className={`mt-6 rounded-2xl border px-4 py-3 text-sm shadow-sm ${statusTone}`}
                    aria-live="polite"
                  >
                    <div className="flex items-center gap-3">
                      {statusType === 'error' && <AlertCircle className="h-5 w-5" />}
                      {statusType === 'success' && <CheckCircle2 className="h-5 w-5" />}
                      {statusType === 'processing' && <Loader2 className="h-5 w-5 animate-spin" />}
                      <span className="font-medium">{statusMessage}</span>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </section>
        </main>

        <section className="mt-12 grid gap-6 md:grid-cols-3">
          {[
            {
              title: 'Bảo mật tuyệt đối',
              description: 'File được xử lý cục bộ và tự xoá sau khi tải về.',
            },
            {
              title: 'Tùy chỉnh linh hoạt',
              description: 'Chọn FPS chính xác cho từng nền tảng và mục tiêu xuất bản.',
            },
            {
              title: 'Tương thích đa nền tảng',
              description: 'Hoạt động ổn định trên trình duyệt, desktop và mobile.',
            },
          ].map((item) => (
            <div
              key={item.title}
              className="rounded-2xl bg-white/80 p-5 shadow-sm ring-1 ring-slate-200"
            >
              <p className="text-sm font-semibold text-slate-900">{item.title}</p>
              <p className="mt-2 text-xs text-slate-500">{item.description}</p>
            </div>
          ))}
        </section>

        <section className="mt-10 rounded-3xl bg-white/70 p-6 shadow-sm ring-1 ring-slate-200">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.35em] text-slate-500">
                Tool Deck
              </p>
              <h2 className="mt-2 text-2xl font-heading font-semibold text-slate-900">
                Khám phá thêm bộ công cụ media
              </h2>
              <p className="mt-2 text-sm text-slate-600">
                Chuyển ảnh, GIF, WebP động, batch zip và theo dõi log realtime.
              </p>
            </div>
            <Link
              href="/tools"
              className="rounded-full bg-slate-900 px-5 py-2 text-xs font-semibold text-white shadow-sm transition hover:-translate-y-0.5"
            >
              Xem tất cả tools
            </Link>
          </div>
          <div className="mt-6 grid gap-4 md:grid-cols-3">
            {[
              {
                title: 'Image → WebP',
                description: 'Giảm dung lượng ảnh nhanh chóng.',
                href: '/tools/image-webp',
              },
              {
                title: 'Animated WebP',
                description: 'Tạo preview động nhẹ và mượt.',
                href: '/tools/animated-webp',
              },
              {
                title: 'Batch ZIP',
                description: 'Xử lý hàng loạt trong một lần.',
                href: '/tools/batch',
              },
            ].map((item, index) => (
              <Link
                key={item.title}
                href={item.href}
                style={{ animationDelay: `${index * 0.08}s` }}
                className="rounded-2xl bg-white/80 p-4 text-sm text-slate-600 shadow-sm ring-1 ring-slate-200 transition hover:-translate-y-1 hover:shadow-lg motion-safe:animate-fade-up"
              >
                <p className="text-sm font-semibold text-slate-900">{item.title}</p>
                <p className="mt-2 text-xs text-slate-500">{item.description}</p>
              </Link>
            ))}
          </div>
        </section>

        <footer className="mt-10 text-center text-sm text-slate-500">
          Powered by <span className="font-semibold text-slate-700">Next.js</span> &{' '}
          <span className="font-semibold text-slate-700">Flask</span>
        </footer>
      </div>
    </div>
  );
}
