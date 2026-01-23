"use client";

import { useRef, useState } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  AlertCircle,
  CheckCircle2,
  Download,
  Film,
  Loader2,
  Upload,
  Wand2,
} from "lucide-react";
import { apiClient } from "@/lib/api-client";
import { downloadBlob, formatBytes } from "@/lib/file-utils";

export default function VideoExportPage() {
  const [file, setFile] = useState<File | null>(null);
  const [fps, setFps] = useState(24);
  const [duration, setDuration] = useState(8);
  const [status, setStatus] = useState("");
  const [processing, setProcessing] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDrag = (event: React.DragEvent) => {
    event.preventDefault();
    event.stopPropagation();
    if (event.type === "dragenter" || event.type === "dragover") {
      setDragActive(true);
    } else if (event.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (event: React.DragEvent) => {
    event.preventDefault();
    event.stopPropagation();
    setDragActive(false);
    if (event.dataTransfer.files && event.dataTransfer.files[0]) {
      setFile(event.dataTransfer.files[0]);
      setStatus("");
    }
  };

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.files && event.target.files[0]) {
      setFile(event.target.files[0]);
      setStatus("");
    }
  };

  const handleExport = async () => {
    if (!file) {
      setStatus("error:Hãy chọn video trước khi export.");
      return;
    }

    try {
      setProcessing(true);
      setStatus("processing:Đang upload video...");
      const uploadResult = await apiClient.uploadVideo(file);

      if (!uploadResult.file_id) {
        setStatus("error:Không nhận được file_id từ server.");
        return;
      }

      setStatus("processing:Đang render video loop...");
      const exportedBlob = await apiClient.exportVideo(
        uploadResult.file_id,
        fps,
        duration
      );
      downloadBlob(exportedBlob, `export_${fps}fps_${duration}s.mp4`);
      setStatus("success:Export thành công, file đã sẵn sàng tải về.");
    } catch (error) {
      setStatus(
        `error:${error instanceof Error ? error.message : "Có lỗi xảy ra"}`
      );
    } finally {
      setProcessing(false);
    }
  };

  const statusParts = status.split(":");
  const statusType = statusParts[0];
  const statusMessage =
    statusParts.length > 1 ? statusParts.slice(1).join(":") : status;

  const statusTone =
    statusType === "error"
      ? "bg-rose-500/10 border-rose-500/30 text-rose-400"
      : statusType === "success"
        ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400"
        : statusType === "processing"
          ? "bg-sky-500/10 border-sky-500/30 text-sky-400"
          : "bg-[var(--secondary)] border-[var(--border)] text-[var(--muted)]";

  return (
    <main className="mt-10 flex-1">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <Link
            href="/tools"
            className="inline-flex h-11 w-11 items-center justify-center rounded-2xl bg-[var(--card)] text-[var(--foreground)] border border-[var(--border)] transition hover:-translate-y-0.5 hover:border-[var(--primary)] cursor-pointer"
          >
            <ArrowLeft className="h-5 w-5" />
          </Link>
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.35em] text-[var(--muted)]">
              Video Lab
            </p>
            <h1 className="text-3xl font-heading font-semibold text-[var(--foreground)] md:text-4xl">
              Export Loop FPS
            </h1>
            <p className="mt-1 text-sm text-[var(--muted)]">
              Render video theo thời lượng cố định, giữ nhịp khung hình ổn định.
            </p>
          </div>
        </div>
        <span className="rounded-full bg-[var(--secondary)] px-4 py-2 text-xs font-semibold text-[var(--muted)] border border-[var(--border)]">
          Endpoint: /export
        </span>
      </header>

      <section className="mt-8 grid gap-6 lg:grid-cols-[1fr_0.9fr]">
        <div className="space-y-6">
          <div className="glass-card p-6">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.3em] text-[var(--muted)]">
                  Input
                </p>
                <h2 className="mt-2 text-xl font-heading font-semibold text-[var(--foreground)]">
                  Chọn video nguồn
                </h2>
                <p className="mt-1 text-sm text-[var(--muted)]">
                  Hỗ trợ MP4, MOV, WebM. File được xoá sau khi xử lý.
                </p>
              </div>
              <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-sky-500/20 text-sky-400">
                <Film className="h-5 w-5" />
              </div>
            </div>

            <div
              className={`group relative mt-6 rounded-2xl border-2 border-dashed p-6 transition-all duration-300 focus-within:ring-2 focus-within:ring-sky-400/60 ${dragActive
                  ? "border-sky-400 bg-sky-500/10 glow-sm"
                  : file
                    ? "border-emerald-400 bg-emerald-500/10"
                    : "border-[var(--border)] bg-[var(--secondary)] hover:border-sky-400/50 hover:bg-[var(--card)]"
                }`}
              onDragEnter={handleDrag}
              onDragLeave={handleDrag}
              onDragOver={handleDrag}
              onDrop={handleDrop}
            >
              <input
                ref={fileInputRef}
                id="video-loop-file"
                type="file"
                accept="video/*"
                onChange={handleFileChange}
                className="hidden"
                disabled={processing}
              />
              <div
                role="button"
                tabIndex={0}
                aria-label="Chọn video để export"
                onClick={() => fileInputRef.current?.click()}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    fileInputRef.current?.click();
                  }
                }}
                className="relative z-10 cursor-pointer text-center focus:outline-none"
              >
                <div
                  className={`mx-auto flex h-16 w-16 items-center justify-center rounded-2xl transition-transform duration-300 ${file
                      ? "bg-emerald-500 text-white"
                      : "bg-gradient-to-br from-sky-500 to-blue-600 text-white group-hover:scale-110"
                    }`}
                >
                  {file ? (
                    <CheckCircle2 className="h-8 w-8" />
                  ) : (
                    <Upload className="h-8 w-8" />
                  )}
                </div>

                {file ? (
                  <div className="mt-4 space-y-1">
                    <p className="text-sm font-semibold text-emerald-400">
                      Đã chọn file
                    </p>
                    <p className="truncate text-sm font-medium text-[var(--foreground)]">
                      {file.name}
                    </p>
                    <p className="text-xs text-[var(--muted)]">
                      {formatBytes(file.size)}
                    </p>
                  </div>
                ) : (
                  <div className="mt-4 space-y-1">
                    <p className="text-sm font-semibold text-[var(--foreground)]">
                      Kéo thả video vào đây
                    </p>
                    <p className="text-xs text-[var(--muted)]">hoặc click để chọn file</p>
                    <p className="text-xs text-[var(--muted)]">Giữ nguyên âm thanh</p>
                  </div>
                )}
              </div>

              {dragActive && (
                <div className="pointer-events-none absolute inset-0 rounded-2xl bg-gradient-to-br from-sky-500/20 via-transparent to-orange-500/20" />
              )}
            </div>
          </div>

          <div className="glass-card p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.3em] text-[var(--muted)]">
                  Settings
                </p>
                <h3 className="mt-2 text-lg font-heading font-semibold text-[var(--foreground)]">
                  Tuỳ chỉnh FPS & thời lượng
                </h3>
                <p className="mt-1 text-sm text-[var(--muted)]">
                  Gợi ý: 24fps · 6-10s cho highlight, 30fps · 15s cho preview.
                </p>
              </div>
              <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-orange-500/20 text-orange-400">
                <Wand2 className="h-5 w-5" />
              </div>
            </div>

            <div className="mt-6 space-y-6">
              <div>
                <label
                  htmlFor="fps-loop"
                  className="flex items-center justify-between text-sm font-semibold text-[var(--muted)]"
                >
                  FPS mục tiêu
                  <span className="rounded-full bg-[var(--primary)] px-3 py-1 text-xs font-semibold text-white">
                    {fps} FPS
                  </span>
                </label>
                <input
                  id="fps-loop"
                  type="range"
                  min="1"
                  max="60"
                  value={fps}
                  onChange={(event) => setFps(Number(event.target.value))}
                  disabled={processing}
                  className="mt-4 h-2 w-full cursor-pointer appearance-none rounded-full bg-[var(--secondary)] accent-[var(--primary)]"
                />
              </div>

              <div>
                <label
                  htmlFor="duration-loop"
                  className="flex items-center justify-between text-sm font-semibold text-[var(--muted)]"
                >
                  Thời lượng export
                  <span className="rounded-full bg-orange-500 px-3 py-1 text-xs font-semibold text-white">
                    {duration}s
                  </span>
                </label>
                <input
                  id="duration-loop"
                  type="range"
                  min="1"
                  max="30"
                  value={duration}
                  onChange={(event) => setDuration(Number(event.target.value))}
                  disabled={processing}
                  className="mt-4 h-2 w-full cursor-pointer appearance-none rounded-full bg-[var(--secondary)] accent-orange-400"
                />
                <div className="mt-3 flex items-center justify-between text-[11px] text-[var(--muted)]">
                  <span>1s</span>
                  <span>10s</span>
                  <span>20s</span>
                  <span>30s</span>
                </div>
                <div className="mt-3 flex items-center gap-3 text-xs text-[var(--muted)]">
                  <span>Tuỳ chọn nhanh:</span>
                  {[6, 8, 12, 15].map((value) => (
                    <button
                      key={value}
                      type="button"
                      onClick={() => setDuration(value)}
                      className={`rounded-full px-3 py-1 text-[11px] font-semibold transition cursor-pointer ${duration === value
                          ? "bg-[var(--primary)] text-white"
                          : "bg-[var(--secondary)] text-[var(--muted)] hover:bg-[var(--card)]"
                        }`}
                    >
                      {value}s
                    </button>
                  ))}
                </div>
                <div className="mt-4 flex items-center gap-3 text-xs text-[var(--muted)]">
                  <label htmlFor="duration-input" className="font-semibold text-[var(--foreground)]">
                    Nhập thủ công (1-3600s):
                  </label>
                  <input
                    id="duration-input"
                    type="number"
                    min="1"
                    max="3600"
                    value={duration}
                    onChange={(event) => {
                      const value = Number(event.target.value);
                      setDuration(Number.isFinite(value) && value > 0 ? value : 1);
                    }}
                    className="input w-24 !py-1 text-xs"
                  />
                </div>
              </div>
            </div>
          </div>
        </div>

        <aside className="space-y-6">
          <div className="rounded-3xl bg-gradient-to-br from-sky-500 via-blue-500 to-indigo-500 p-[1px] shadow-2xl shadow-sky-500/20">
            <div className="glass-card rounded-[23px] p-6">
              <h3 className="text-lg font-heading font-semibold text-[var(--foreground)]">
                Export nhanh, loop mượt
              </h3>
              <p className="mt-2 text-sm text-[var(--muted)]">
                Dành cho demo loop, preview trong app hoặc carousel social.
              </p>
              <div className="mt-4 space-y-2 text-xs text-[var(--muted)]">
                <div className="flex items-center justify-between">
                  <span>Output</span>
                  <span className="font-semibold text-[var(--foreground)]">MP4</span>
                </div>
                <div className="flex items-center justify-between">
                  <span>FPS</span>
                  <span className="font-semibold text-[var(--foreground)]">{fps}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span>Duration</span>
                  <span className="font-semibold text-[var(--foreground)]">{duration}s</span>
                </div>
              </div>
            </div>
          </div>

          <button
            onClick={handleExport}
            disabled={processing || !file}
            className="group relative w-full overflow-hidden rounded-2xl bg-gradient-to-r from-sky-500 via-cyan-500 to-orange-400 px-8 py-4 text-sm font-semibold text-white shadow-lg shadow-sky-500/20 transition-all duration-300 hover:brightness-105 hover:shadow-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400/70 disabled:cursor-not-allowed disabled:opacity-50 cursor-pointer"
          >
            <span className="relative z-10 flex items-center justify-center gap-3">
              {processing ? (
                <>
                  <Loader2 className="h-5 w-5 animate-spin" />
                  Đang export...
                </>
              ) : (
                <>
                  <Download className="h-5 w-5" />
                  Export video
                </>
              )}
            </span>
            <span className="pointer-events-none absolute inset-0 -translate-x-full bg-gradient-to-r from-transparent via-white/60 to-transparent motion-safe:animate-shimmer" />
          </button>

          {status && (
            <div
              className={`rounded-2xl border px-4 py-3 text-sm shadow-sm ${statusTone}`}
              aria-live="polite"
            >
              <div className="flex items-center gap-3">
                {statusType === "error" && <AlertCircle className="h-5 w-5" />}
                {statusType === "success" && <CheckCircle2 className="h-5 w-5" />}
                {statusType === "processing" && (
                  <Loader2 className="h-5 w-5 animate-spin" />
                )}
                <span className="font-medium">{statusMessage}</span>
              </div>
            </div>
          )}
        </aside>
      </section>
    </main>
  );
}
