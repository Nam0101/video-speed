"use client";

import { useRef, useState } from "react";
import Link from "next/link";
import {
  AlertCircle,
  ArrowLeft,
  CheckCircle2,
  Download,
  ImageIcon,
  Loader2,
  Upload,
} from "lucide-react";
import { apiClient } from "@/lib/api-client";
import { downloadBlob, formatBytes } from "@/lib/file-utils";

export default function ImageWebPPage() {
  const [file, setFile] = useState<File | null>(null);
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

  const handleConvert = async () => {
    if (!file) {
      setStatus("error:Hãy chọn ảnh trước khi chuyển đổi.");
      return;
    }

    try {
      setProcessing(true);
      setStatus("processing:Đang xử lý ảnh...");
      const blob = await apiClient.convertImageToWebP(file);
      const filename = `${file.name.replace(/\.[^/.]+$/, "")}.webp`;
      downloadBlob(blob, filename);
      setStatus("success:Chuyển đổi thành công!");
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
              Image Toolkit
            </p>
            <h1 className="text-3xl font-heading font-semibold text-slate-900 md:text-4xl">
              PNG/JPG → WebP
            </h1>
            <p className="mt-1 text-sm text-slate-600">
              Tối ưu dung lượng, giữ chất lượng ảnh sản phẩm.
            </p>
          </div>
        </div>
        <span className="rounded-full bg-white/70 px-4 py-2 text-xs font-semibold text-slate-600 shadow-sm ring-1 ring-slate-200">
          Endpoint: /png-to-webp
        </span>
      </header>

      <section className="mt-8 grid gap-6 lg:grid-cols-[1fr_0.85fr]">
        <div className="rounded-3xl bg-white/80 p-6 shadow-sm ring-1 ring-slate-200">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">
                Input
              </p>
              <h2 className="mt-2 text-xl font-heading font-semibold text-slate-900">
                Chọn file ảnh
              </h2>
              <p className="mt-1 text-sm text-slate-500">
                Chấp nhận PNG, JPG, JPEG. Output WebP tải về ngay.
              </p>
            </div>
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-emerald-100 text-emerald-600">
              <ImageIcon className="h-5 w-5" />
            </div>
          </div>

          <div
            className={`group relative mt-6 rounded-2xl border-2 border-dashed p-6 transition-all duration-300 focus-within:ring-2 focus-within:ring-emerald-400/60 ${
              dragActive
                ? "border-emerald-400 bg-emerald-50/80 shadow-lg shadow-emerald-200/60"
                : file
                  ? "border-sky-300 bg-sky-50/70"
                  : "border-slate-200/80 bg-white/70 hover:border-emerald-300 hover:bg-emerald-50/40"
            }`}
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
          >
            <input
              ref={fileInputRef}
              id="image-file"
              type="file"
              accept="image/png,image/jpeg"
              onChange={handleFileChange}
              className="hidden"
              disabled={processing}
            />

            <div
              role="button"
              tabIndex={0}
              aria-label="Chọn file ảnh để chuyển đổi"
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
                    ? "bg-sky-500 text-white"
                    : "bg-gradient-to-br from-emerald-500 to-teal-500 text-white group-hover:scale-110"
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
                  <p className="text-sm font-semibold text-sky-600">
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
                    Kéo thả ảnh vào đây
                  </p>
                  <p className="text-xs text-slate-500">hoặc click để chọn file</p>
                  <p className="text-xs text-slate-400">Giữ nguyên màu sắc</p>
                </div>
              )}
            </div>

            {dragActive && (
              <div className="pointer-events-none absolute inset-0 rounded-2xl bg-gradient-to-br from-emerald-200/70 via-white/20 to-sky-200/60" />
            )}
          </div>
        </div>

        <aside className="space-y-6">
          <div className="rounded-3xl bg-gradient-to-br from-emerald-400 via-teal-400 to-sky-500 p-[1px] shadow-2xl shadow-emerald-200/50">
            <div className="rounded-[23px] bg-white/90 p-6">
              <h3 className="text-lg font-heading font-semibold text-slate-900">
                Kết quả tối ưu
              </h3>
              <p className="mt-2 text-sm text-slate-600">
                WebP giảm dung lượng ~25-35% so với JPEG và PNG.
              </p>
              <div className="mt-4 grid gap-3 text-xs text-slate-500">
                <div className="flex items-center justify-between">
                  <span>Input</span>
                  <span className="font-semibold text-slate-700">
                    {file ? formatBytes(file.size) : "--"}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span>Output</span>
                  <span className="font-semibold text-slate-700">WebP</span>
                </div>
              </div>
            </div>
          </div>

          <button
            onClick={handleConvert}
            disabled={processing || !file}
            className="group relative w-full overflow-hidden rounded-2xl bg-gradient-to-r from-emerald-500 via-teal-500 to-sky-500 px-8 py-4 text-sm font-semibold text-white shadow-lg shadow-emerald-200/60 transition-all duration-300 hover:brightness-105 hover:shadow-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400/70 disabled:cursor-not-allowed disabled:opacity-50"
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
                  Chuyển sang WebP
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
