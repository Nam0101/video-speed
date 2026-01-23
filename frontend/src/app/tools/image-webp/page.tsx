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
              Image Toolkit
            </p>
            <h1 className="text-3xl font-heading font-semibold text-[var(--foreground)] md:text-4xl">
              PNG/JPG → WebP
            </h1>
            <p className="mt-1 text-sm text-[var(--muted)]">
              Tối ưu dung lượng, giữ chất lượng ảnh sản phẩm.
            </p>
          </div>
        </div>
        <span className="rounded-full bg-[var(--secondary)] px-4 py-2 text-xs font-semibold text-[var(--muted)] border border-[var(--border)]">
          Endpoint: /png-to-webp
        </span>
      </header>

      <section className="mt-8 grid gap-6 lg:grid-cols-[1fr_0.85fr]">
        <div className="glass-card p-6">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.3em] text-[var(--muted)]">
                Input
              </p>
              <h2 className="mt-2 text-xl font-heading font-semibold text-[var(--foreground)]">
                Chọn file ảnh
              </h2>
              <p className="mt-1 text-sm text-[var(--muted)]">
                Chấp nhận PNG, JPG, JPEG. Output WebP tải về ngay.
              </p>
            </div>
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-emerald-500/20 text-emerald-400">
              <ImageIcon className="h-5 w-5" />
            </div>
          </div>

          <div
            className={`group relative mt-6 rounded-2xl border-2 border-dashed p-6 transition-all duration-300 focus-within:ring-2 focus-within:ring-emerald-400/60 ${dragActive
                ? "border-emerald-400 bg-emerald-500/10 glow-sm"
                : file
                  ? "border-[var(--primary)] bg-[var(--primary)]/10"
                  : "border-[var(--border)] bg-[var(--secondary)] hover:border-emerald-400/50 hover:bg-[var(--card)]"
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
                className={`mx-auto flex h-16 w-16 items-center justify-center rounded-2xl transition-transform duration-300 ${file
                    ? "bg-[var(--primary)] text-white"
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
                  <p className="text-sm font-semibold text-[var(--primary)]">
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
                    Kéo thả ảnh vào đây
                  </p>
                  <p className="text-xs text-[var(--muted)]">hoặc click để chọn file</p>
                  <p className="text-xs text-[var(--muted)]">Giữ nguyên màu sắc</p>
                </div>
              )}
            </div>

            {dragActive && (
              <div className="pointer-events-none absolute inset-0 rounded-2xl bg-gradient-to-br from-emerald-500/20 via-transparent to-teal-500/20" />
            )}
          </div>
        </div>

        <aside className="space-y-6">
          <div className="rounded-3xl bg-gradient-to-br from-emerald-500 via-teal-500 to-cyan-500 p-[1px] shadow-2xl shadow-emerald-500/20">
            <div className="glass-card rounded-[23px] p-6">
              <h3 className="text-lg font-heading font-semibold text-[var(--foreground)]">
                Kết quả tối ưu
              </h3>
              <p className="mt-2 text-sm text-[var(--muted)]">
                WebP giảm dung lượng ~25-35% so với JPEG và PNG.
              </p>
              <div className="mt-4 grid gap-3 text-xs text-[var(--muted)]">
                <div className="flex items-center justify-between">
                  <span>Input</span>
                  <span className="font-semibold text-[var(--foreground)]">
                    {file ? formatBytes(file.size) : "--"}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span>Output</span>
                  <span className="font-semibold text-[var(--foreground)]">WebP</span>
                </div>
              </div>
            </div>
          </div>

          <button
            onClick={handleConvert}
            disabled={processing || !file}
            className="group relative w-full overflow-hidden rounded-2xl bg-gradient-to-r from-emerald-500 via-teal-500 to-cyan-500 px-8 py-4 text-sm font-semibold text-white shadow-lg shadow-emerald-500/20 transition-all duration-300 hover:brightness-105 hover:shadow-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400/70 disabled:cursor-not-allowed disabled:opacity-50 cursor-pointer"
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
