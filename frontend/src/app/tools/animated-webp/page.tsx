"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import {
  AlertCircle,
  ArrowLeft,
  CheckCircle2,
  Download,
  ImageIcon,
  Loader2,
  Sparkles,
  Sticker,
  Video,
} from "lucide-react";
import { apiClient } from "@/lib/api-client";
import { downloadBlob, formatBytes } from "@/lib/file-utils";

const StatusNotice = ({ status }: { status: string }) => {
  if (!status) return null;
  const statusParts = status.split(":");
  const statusType = statusParts[0];
  const statusMessage =
    statusParts.length > 1 ? statusParts.slice(1).join(":") : status;
  const tone =
    statusType === "error"
      ? "bg-rose-50 border-rose-200 text-rose-700"
      : statusType === "success"
        ? "bg-emerald-50 border-emerald-200 text-emerald-700"
        : statusType === "processing"
          ? "bg-sky-50 border-sky-200 text-sky-700"
          : "bg-slate-50 border-slate-200 text-slate-600";

  return (
    <div className={`rounded-2xl border px-4 py-3 text-sm shadow-sm ${tone}`}>
      <div className="flex items-center gap-3">
        {statusType === "error" && <AlertCircle className="h-5 w-5" />}
        {statusType === "success" && <CheckCircle2 className="h-5 w-5" />}
        {statusType === "processing" && (
          <Loader2 className="h-5 w-5 animate-spin" />
        )}
        <span className="font-medium">{statusMessage}</span>
      </div>
    </div>
  );
};

const summarizeFiles = (files: File[]) => {
  if (!files.length) return "Chưa có file nào";
  const totalBytes = files.reduce((sum, file) => sum + file.size, 0);
  return `${files.length} files · ${formatBytes(totalBytes)}`;
};

export default function AnimatedWebPPage() {
  const [imagesFiles, setImagesFiles] = useState<File[]>([]);
  const [imagesFps, setImagesFps] = useState(12);
  const [imagesWidth, setImagesWidth] = useState("");
  const [imagesStatus, setImagesStatus] = useState("");
  const [imagesProcessing, setImagesProcessing] = useState(false);

  const [mp4File, setMp4File] = useState<File | null>(null);
  const [mp4Fps, setMp4Fps] = useState(15);
  const [mp4Width, setMp4Width] = useState("");
  const [mp4Duration, setMp4Duration] = useState("");
  const [mp4Status, setMp4Status] = useState("");
  const [mp4Processing, setMp4Processing] = useState(false);

  const [gifFile, setGifFile] = useState<File | null>(null);
  const [gifFps, setGifFps] = useState(12);
  const [gifWidth, setGifWidth] = useState("");
  const [gifDuration, setGifDuration] = useState("");
  const [gifStatus, setGifStatus] = useState("");
  const [gifProcessing, setGifProcessing] = useState(false);

  const [webmFile, setWebmFile] = useState<File | null>(null);
  const [webmFps, setWebmFps] = useState(15);
  const [webmWidth, setWebmWidth] = useState("");
  const [webmStatus, setWebmStatus] = useState("");
  const [webmProcessing, setWebmProcessing] = useState(false);

  const imagesSummary = useMemo(
    () => summarizeFiles(imagesFiles),
    [imagesFiles]
  );

  const handleImagesConvert = async () => {
    if (!imagesFiles.length) {
      setImagesStatus("error:Vui lòng chọn ít nhất 1 ảnh.");
      return;
    }
    try {
      setImagesProcessing(true);
      setImagesStatus("processing:Đang render WebP động...");
      const blob = await apiClient.imagesToAnimatedWebP(
        imagesFiles,
        imagesFps,
        imagesWidth ? Number(imagesWidth) : undefined
      );
      downloadBlob(
        blob,
        `animated_${imagesFiles.length}frames_${imagesFps}fps.webp`
      );
      setImagesStatus("success:Hoàn tất! WebP đã sẵn sàng tải về.");
    } catch (error) {
      setImagesStatus(
        `error:${error instanceof Error ? error.message : "Có lỗi xảy ra"}`
      );
    } finally {
      setImagesProcessing(false);
    }
  };

  const handleMp4Convert = async () => {
    if (!mp4File) {
      setMp4Status("error:Hãy chọn file MP4.");
      return;
    }
    try {
      setMp4Processing(true);
      setMp4Status("processing:Đang chuyển MP4 → WebP...");
      const blob = await apiClient.convertMp4ToAnimatedWebP(
        mp4File,
        mp4Fps,
        mp4Width ? Number(mp4Width) : undefined,
        mp4Duration ? Number(mp4Duration) : undefined
      );
      downloadBlob(blob, `${mp4File.name.replace(/\.[^/.]+$/, "")}.webp`);
      setMp4Status("success:Chuyển đổi thành công!");
    } catch (error) {
      setMp4Status(
        `error:${error instanceof Error ? error.message : "Có lỗi xảy ra"}`
      );
    } finally {
      setMp4Processing(false);
    }
  };

  const handleGifConvert = async () => {
    if (!gifFile) {
      setGifStatus("error:Hãy chọn file GIF.");
      return;
    }
    try {
      setGifProcessing(true);
      setGifStatus("processing:Đang chuyển GIF → WebP...");
      const blob = await apiClient.convertGifToWebP(
        gifFile,
        gifFps,
        gifWidth ? Number(gifWidth) : undefined,
        gifDuration ? Number(gifDuration) : undefined
      );
      downloadBlob(blob, `${gifFile.name.replace(/\.[^/.]+$/, "")}.webp`);
      setGifStatus("success:Hoàn tất! WebP đã tải về.");
    } catch (error) {
      setGifStatus(
        `error:${error instanceof Error ? error.message : "Có lỗi xảy ra"}`
      );
    } finally {
      setGifProcessing(false);
    }
  };

  const handleWebmConvert = async () => {
    if (!webmFile) {
      setWebmStatus("error:Hãy chọn file WebM.");
      return;
    }
    try {
      setWebmProcessing(true);
      setWebmStatus("processing:Đang chuyển WebM → GIF...");
      const blob = await apiClient.convertWebmToGif(
        webmFile,
        webmFps,
        webmWidth ? Number(webmWidth) : undefined
      );
      downloadBlob(blob, `${webmFile.name.replace(/\.[^/.]+$/, "")}.gif`);
      setWebmStatus("success:GIF đã sẵn sàng tải về!");
    } catch (error) {
      setWebmStatus(
        `error:${error instanceof Error ? error.message : "Có lỗi xảy ra"}`
      );
    } finally {
      setWebmProcessing(false);
    }
  };

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
              Motion Studio
            </p>
            <h1 className="text-3xl font-heading font-semibold text-slate-900 md:text-4xl">
              Animated WebP & GIF
            </h1>
            <p className="mt-1 text-sm text-slate-600">
              Từ video, GIF hoặc chuỗi ảnh sang WebP động nhẹ và mượt.
            </p>
          </div>
        </div>
        <span className="rounded-full bg-white/70 px-4 py-2 text-xs font-semibold text-slate-600 shadow-sm ring-1 ring-slate-200">
          Endpoints: /images-to-animated-webp · /mp4-to-animated-webp · /gif-to-webp · /webm-to-gif
        </span>
      </header>

      <section className="mt-8 grid gap-6 lg:grid-cols-2">
        <div className="space-y-6">
          <div className="rounded-3xl bg-white/80 p-6 shadow-sm ring-1 ring-slate-200">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">
                  Ảnh → WebP
                </p>
                <h2 className="mt-2 text-xl font-heading font-semibold text-slate-900">
                  Ghép chuỗi ảnh
                </h2>
                <p className="mt-1 text-sm text-slate-500">
                  Upload nhiều ảnh theo thứ tự để tạo WebP động.
                </p>
              </div>
              <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-sky-100 text-sky-600">
                <ImageIcon className="h-5 w-5" />
              </div>
            </div>

            <div className="mt-5 space-y-4">
              <input
                type="file"
                accept="image/png,image/jpeg"
                multiple
                onChange={(event) =>
                  setImagesFiles(Array.from(event.target.files || []))
                }
                className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-600 file:mr-4 file:rounded-full file:border-0 file:bg-sky-50 file:px-4 file:py-2 file:text-xs file:font-semibold file:text-sky-600"
              />
              <div className="text-xs text-slate-500">{imagesSummary}</div>
            </div>

            <div className="mt-5 grid gap-4 md:grid-cols-2">
              <div>
                <label className="text-xs font-semibold uppercase tracking-widest text-slate-500">
                  FPS
                </label>
                <input
                  type="number"
                  min="1"
                  max="60"
                  value={imagesFps}
                  onChange={(event) => setImagesFps(Number(event.target.value))}
                  className="mt-2 w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700"
                />
              </div>
              <div>
                <label className="text-xs font-semibold uppercase tracking-widest text-slate-500">
                  Width (px)
                </label>
                <input
                  type="number"
                  min="64"
                  max="2048"
                  placeholder="Auto"
                  value={imagesWidth}
                  onChange={(event) => setImagesWidth(event.target.value)}
                  className="mt-2 w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700"
                />
              </div>
            </div>

            <button
              onClick={handleImagesConvert}
              disabled={imagesProcessing || imagesFiles.length === 0}
              className="mt-6 flex w-full items-center justify-center gap-2 rounded-2xl bg-slate-900 px-4 py-3 text-sm font-semibold text-white shadow-sm transition hover:-translate-y-0.5 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {imagesProcessing ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Download className="h-4 w-4" />
              )}
              Render WebP động
            </button>
            <div className="mt-4">
              <StatusNotice status={imagesStatus} />
            </div>
          </div>

          <div className="rounded-3xl bg-white/80 p-6 shadow-sm ring-1 ring-slate-200">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">
                  GIF → WebP
                </p>
                <h2 className="mt-2 text-xl font-heading font-semibold text-slate-900">
                  Nén GIF nhẹ hơn
                </h2>
                <p className="mt-1 text-sm text-slate-500">
                  Chuyển GIF sang WebP để giảm dung lượng và giữ animation.
                </p>
              </div>
              <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-rose-100 text-rose-600">
                <Sticker className="h-5 w-5" />
              </div>
            </div>

            <div className="mt-5 space-y-4">
              <input
                type="file"
                accept="image/gif"
                onChange={(event) => setGifFile(event.target.files?.[0] || null)}
                className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-600 file:mr-4 file:rounded-full file:border-0 file:bg-rose-50 file:px-4 file:py-2 file:text-xs file:font-semibold file:text-rose-600"
              />
              <div className="text-xs text-slate-500">
                {gifFile ? `${gifFile.name} · ${formatBytes(gifFile.size)}` : "Chưa có file"}
              </div>
            </div>

            <div className="mt-5 grid gap-4 md:grid-cols-3">
              <div>
                <label className="text-xs font-semibold uppercase tracking-widest text-slate-500">
                  FPS
                </label>
                <input
                  type="number"
                  min="1"
                  max="60"
                  value={gifFps}
                  onChange={(event) => setGifFps(Number(event.target.value))}
                  className="mt-2 w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700"
                />
              </div>
              <div>
                <label className="text-xs font-semibold uppercase tracking-widest text-slate-500">
                  Width
                </label>
                <input
                  type="number"
                  min="64"
                  max="2048"
                  placeholder="Auto"
                  value={gifWidth}
                  onChange={(event) => setGifWidth(event.target.value)}
                  className="mt-2 w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700"
                />
              </div>
              <div>
                <label className="text-xs font-semibold uppercase tracking-widest text-slate-500">
                  Duration
                </label>
                <input
                  type="number"
                  min="1"
                  max="3600"
                  placeholder="Auto"
                  value={gifDuration}
                  onChange={(event) => setGifDuration(event.target.value)}
                  className="mt-2 w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700"
                />
              </div>
            </div>

            <button
              onClick={handleGifConvert}
              disabled={gifProcessing || !gifFile}
              className="mt-6 flex w-full items-center justify-center gap-2 rounded-2xl bg-rose-500 px-4 py-3 text-sm font-semibold text-white shadow-sm transition hover:-translate-y-0.5 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {gifProcessing ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Download className="h-4 w-4" />
              )}
              Convert GIF → WebP
            </button>
            <div className="mt-4">
              <StatusNotice status={gifStatus} />
            </div>
          </div>
        </div>

        <div className="space-y-6">
          <div className="rounded-3xl bg-white/80 p-6 shadow-sm ring-1 ring-slate-200">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">
                  MP4 → WebP
                </p>
                <h2 className="mt-2 text-xl font-heading font-semibold text-slate-900">
                  Trích video thành WebP
                </h2>
                <p className="mt-1 text-sm text-slate-500">
                  Dành cho preview animation ngắn, nhẹ.
                </p>
              </div>
              <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-indigo-100 text-indigo-600">
                <Video className="h-5 w-5" />
              </div>
            </div>

            <div className="mt-5 space-y-4">
              <input
                type="file"
                accept="video/mp4"
                onChange={(event) => setMp4File(event.target.files?.[0] || null)}
                className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-600 file:mr-4 file:rounded-full file:border-0 file:bg-indigo-50 file:px-4 file:py-2 file:text-xs file:font-semibold file:text-indigo-600"
              />
              <div className="text-xs text-slate-500">
                {mp4File ? `${mp4File.name} · ${formatBytes(mp4File.size)}` : "Chưa có file"}
              </div>
            </div>

            <div className="mt-5 grid gap-4 md:grid-cols-3">
              <div>
                <label className="text-xs font-semibold uppercase tracking-widest text-slate-500">
                  FPS
                </label>
                <input
                  type="number"
                  min="1"
                  max="60"
                  value={mp4Fps}
                  onChange={(event) => setMp4Fps(Number(event.target.value))}
                  className="mt-2 w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700"
                />
              </div>
              <div>
                <label className="text-xs font-semibold uppercase tracking-widest text-slate-500">
                  Width
                </label>
                <input
                  type="number"
                  min="64"
                  max="2048"
                  placeholder="Auto"
                  value={mp4Width}
                  onChange={(event) => setMp4Width(event.target.value)}
                  className="mt-2 w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700"
                />
              </div>
              <div>
                <label className="text-xs font-semibold uppercase tracking-widest text-slate-500">
                  Duration
                </label>
                <input
                  type="number"
                  min="1"
                  max="3600"
                  placeholder="Auto"
                  value={mp4Duration}
                  onChange={(event) => setMp4Duration(event.target.value)}
                  className="mt-2 w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700"
                />
              </div>
            </div>

            <button
              onClick={handleMp4Convert}
              disabled={mp4Processing || !mp4File}
              className="mt-6 flex w-full items-center justify-center gap-2 rounded-2xl bg-indigo-500 px-4 py-3 text-sm font-semibold text-white shadow-sm transition hover:-translate-y-0.5 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {mp4Processing ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Download className="h-4 w-4" />
              )}
              Convert MP4 → WebP
            </button>
            <div className="mt-4">
              <StatusNotice status={mp4Status} />
            </div>
          </div>

          <div className="rounded-3xl bg-white/80 p-6 shadow-sm ring-1 ring-slate-200">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">
                  WebM → GIF
                </p>
                <h2 className="mt-2 text-xl font-heading font-semibold text-slate-900">
                  Chuyển WebM thành GIF
                </h2>
                <p className="mt-1 text-sm text-slate-500">
                  Tạo GIF tương thích mọi nền tảng.
                </p>
              </div>
              <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-amber-100 text-amber-600">
                <Sparkles className="h-5 w-5" />
              </div>
            </div>

            <div className="mt-5 space-y-4">
              <input
                type="file"
                accept="video/webm"
                onChange={(event) => setWebmFile(event.target.files?.[0] || null)}
                className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-600 file:mr-4 file:rounded-full file:border-0 file:bg-amber-50 file:px-4 file:py-2 file:text-xs file:font-semibold file:text-amber-600"
              />
              <div className="text-xs text-slate-500">
                {webmFile ? `${webmFile.name} · ${formatBytes(webmFile.size)}` : "Chưa có file"}
              </div>
            </div>

            <div className="mt-5 grid gap-4 md:grid-cols-2">
              <div>
                <label className="text-xs font-semibold uppercase tracking-widest text-slate-500">
                  FPS
                </label>
                <input
                  type="number"
                  min="1"
                  max="60"
                  value={webmFps}
                  onChange={(event) => setWebmFps(Number(event.target.value))}
                  className="mt-2 w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700"
                />
              </div>
              <div>
                <label className="text-xs font-semibold uppercase tracking-widest text-slate-500">
                  Width
                </label>
                <input
                  type="number"
                  min="64"
                  max="2048"
                  placeholder="Auto"
                  value={webmWidth}
                  onChange={(event) => setWebmWidth(event.target.value)}
                  className="mt-2 w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700"
                />
              </div>
            </div>

            <button
              onClick={handleWebmConvert}
              disabled={webmProcessing || !webmFile}
              className="mt-6 flex w-full items-center justify-center gap-2 rounded-2xl bg-amber-500 px-4 py-3 text-sm font-semibold text-white shadow-sm transition hover:-translate-y-0.5 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {webmProcessing ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Download className="h-4 w-4" />
              )}
              Convert WebM → GIF
            </button>
            <div className="mt-4">
              <StatusNotice status={webmStatus} />
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}
