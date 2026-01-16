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
      ? "bg-rose-50 border-rose-200 text-rose-700"
      : statusType === "success"
        ? "bg-emerald-50 border-emerald-200 text-emerald-700"
        : statusType === "processing"
          ? "bg-sky-50 border-sky-200 text-sky-700"
          : "bg-slate-50 border-slate-200 text-slate-600";

  return (
    <main className="mt-10 flex-1">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <Link
            href="/tools"
            className="inline-flex h-11 w-11 items-center justify-center rounded-2xl bg-white/80 text-slate-700 shadow-sm ring-1 ring-slate-200 transition hover:-translate-y-0.5"
          >
            <ArrowLeft className="h-5 w-5" />
          </Link>
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.35em] text-slate-500">
              Video Lab
            </p>
            <h1 className="text-3xl font-heading font-semibold text-slate-900 md:text-4xl">
              Export Loop FPS
            </h1>
            <p className="mt-1 text-sm text-slate-600">
              Render video theo thời lượng cố định, giữ nhịp khung hình ổn định.
            </p>
          </div>
        </div>
        <span className="rounded-full bg-white/70 px-4 py-2 text-xs font-semibold text-slate-600 shadow-sm ring-1 ring-slate-200">
          Endpoint: /export
        </span>
      </header>

      <section className="mt-8 grid gap-6 lg:grid-cols-[1fr_0.9fr]">
        <div className="space-y-6">
          <div className="rounded-3xl bg-white/80 p-6 shadow-sm ring-1 ring-slate-200">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">
                  Input
                </p>
                <h2 className="mt-2 text-xl font-heading font-semibold text-slate-900">
                  Chọn video nguồn
                </h2>
                <p className="mt-1 text-sm text-slate-500">
                  Hỗ trợ MP4, MOV, WebM. File được xoá sau khi xử lý.
                </p>
              </div>
              <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-sky-100 text-sky-600">
                <Film className="h-5 w-5" />
              </div>
            </div>

            <div
              className={`group relative mt-6 rounded-2xl border-2 border-dashed p-6 transition-all duration-300 focus-within:ring-2 focus-within:ring-sky-400/60 ${
                dragActive
                  ? "border-sky-400 bg-sky-50/80 shadow-lg shadow-sky-200/60"
                  : file
                    ? "border-emerald-300 bg-emerald-50/70"
                    : "border-slate-200/80 bg-white/70 hover:border-sky-300 hover:bg-sky-50/40"
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
                  className={`mx-auto flex h-16 w-16 items-center justify-center rounded-2xl transition-transform duration-300 ${
                    file
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
                    <p className="text-sm font-semibold text-emerald-600">
                      Đã chọn file
                    </p>
                    <p className="truncate text-sm font-medium text-slate-700">
                      {file.name}
                    </p>
                    <p className="text-xs text-slate-500">
                      {formatBytes(file.size)}
                    </p>
                  </div>
                ) : (
                  <div className="mt-4 space-y-1">
                    <p className="text-sm font-semibold text-slate-700">
                      Kéo thả video vào đây
                    </p>
                    <p className="text-xs text-slate-500">hoặc click để chọn file</p>
                    <p className="text-xs text-slate-400">Giữ nguyên âm thanh</p>
                  </div>
                )}
              </div>

              {dragActive && (
                <div className="pointer-events-none absolute inset-0 rounded-2xl bg-gradient-to-br from-sky-200/70 via-white/20 to-orange-200/60" />
              )}
            </div>
          </div>

          <div className="rounded-3xl bg-white/80 p-6 shadow-sm ring-1 ring-slate-200">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">
                  Settings
                </p>
                <h3 className="mt-2 text-lg font-heading font-semibold text-slate-900">
                  Tuỳ chỉnh FPS & thời lượng
                </h3>
                <p className="mt-1 text-sm text-slate-500">
                  Gợi ý: 24fps · 6-10s cho highlight, 30fps · 15s cho preview.
                </p>
              </div>
              <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-orange-100 text-orange-600">
                <Wand2 className="h-5 w-5" />
              </div>
            </div>

            <div className="mt-6 space-y-6">
              <div>
                <label
                  htmlFor="fps-loop"
                  className="flex items-center justify-between text-sm font-semibold text-slate-600"
                >
                  FPS mục tiêu
                  <span className="rounded-full bg-slate-900 px-3 py-1 text-xs font-semibold text-white">
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
                  className="mt-4 h-2 w-full cursor-pointer appearance-none rounded-full bg-slate-200 accent-sky-500"
                />
              </div>

              <div>
                <label
                  htmlFor="duration-loop"
                  className="flex items-center justify-between text-sm font-semibold text-slate-600"
                >
                  Thời lượng export
                  <span className="rounded-full bg-slate-900 px-3 py-1 text-xs font-semibold text-white">
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
                  className="mt-4 h-2 w-full cursor-pointer appearance-none rounded-full bg-slate-200 accent-orange-400"
                />
                <div className="mt-3 flex items-center justify-between text-[11px] text-slate-400">
                  <span>1s</span>
                  <span>10s</span>
                  <span>20s</span>
                  <span>30s</span>
                </div>
                <div className="mt-3 flex items-center gap-3 text-xs text-slate-500">
                  <span>Tuỳ chọn nhanh:</span>
                  {[6, 8, 12, 15].map((value) => (
                    <button
                      key={value}
                      type="button"
                      onClick={() => setDuration(value)}
                      className={`rounded-full px-3 py-1 text-[11px] font-semibold transition ${
                        duration === value
                          ? "bg-slate-900 text-white"
                          : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                      }`}
                    >
                      {value}s
                    </button>
                  ))}
                </div>
                <div className="mt-4 flex items-center gap-3 text-xs text-slate-500">
                  <label htmlFor="duration-input" className="font-semibold text-slate-600">
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
                    className="w-24 rounded-full border border-slate-200 bg-white px-3 py-1 text-xs text-slate-700"
                  />
                </div>
              </div>
            </div>
          </div>
        </div>

        <aside className="space-y-6">
          <div className="rounded-3xl bg-gradient-to-br from-sky-500 via-blue-500 to-indigo-500 p-[1px] shadow-2xl shadow-sky-200/50">
            <div className="rounded-[23px] bg-white/90 p-6">
              <h3 className="text-lg font-heading font-semibold text-slate-900">
                Export nhanh, loop mượt
              </h3>
              <p className="mt-2 text-sm text-slate-600">
                Dành cho demo loop, preview trong app hoặc carousel social.
              </p>
              <div className="mt-4 space-y-2 text-xs text-slate-500">
                <div className="flex items-center justify-between">
                  <span>Output</span>
                  <span className="font-semibold text-slate-700">MP4</span>
                </div>
                <div className="flex items-center justify-between">
                  <span>FPS</span>
                  <span className="font-semibold text-slate-700">{fps}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span>Duration</span>
                  <span className="font-semibold text-slate-700">{duration}s</span>
                </div>
              </div>
            </div>
          </div>

          <button
            onClick={handleExport}
            disabled={processing || !file}
            className="group relative w-full overflow-hidden rounded-2xl bg-gradient-to-r from-sky-500 via-cyan-500 to-orange-400 px-8 py-4 text-sm font-semibold text-white shadow-lg shadow-sky-200/60 transition-all duration-300 hover:brightness-105 hover:shadow-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400/70 disabled:cursor-not-allowed disabled:opacity-50"
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
