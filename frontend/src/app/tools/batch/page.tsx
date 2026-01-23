"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import {
  AlertCircle,
  ArrowLeft,
  CheckCircle2,
  Download,
  Loader2,
  Package,
  Sparkles,
  Wand2,
} from "lucide-react";
import { apiClient } from "@/lib/api-client";
import { downloadBlob, formatBytes } from "@/lib/file-utils";

const StatusNotice = ({ status }: { status: string }) => {
  if (!status) return null;
  const statusParts = status.split(":");
  const statusType = statusParts[0];
  const statusMessage =
    statusParts.length > 1 ? statusParts.slice(1).join(":") : status;

  const toneClasses = {
    error: "bg-rose-500/10 border-rose-500/30 text-rose-400",
    success: "bg-emerald-500/10 border-emerald-500/30 text-emerald-400",
    processing: "bg-sky-500/10 border-sky-500/30 text-sky-400",
    default: "bg-[var(--secondary)] border-[var(--border)] text-[var(--muted)]"
  };

  const tone = toneClasses[statusType as keyof typeof toneClasses] || toneClasses.default;

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

const parseOptionalNumber = (value: string) => {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed <= 0) return undefined;
  return parsed;
};

export default function BatchPage() {
  const [imagesZipFiles, setImagesZipFiles] = useState<File[]>([]);
  const [imagesZipStatus, setImagesZipStatus] = useState("");
  const [imagesZipProcessing, setImagesZipProcessing] = useState(false);

  const [convertZipFiles, setConvertZipFiles] = useState<File[]>([]);
  const [convertFormat, setConvertFormat] = useState<"webp" | "png" | "jpg">(
    "webp"
  );
  const [convertWidth, setConvertWidth] = useState("");
  const [convertQuality, setConvertQuality] = useState("");
  const [convertLossless, setConvertLossless] = useState(false);
  const [convertZipStatus, setConvertZipStatus] = useState("");
  const [convertZipProcessing, setConvertZipProcessing] = useState(false);

  const [tgsFiles, setTgsFiles] = useState<File[]>([]);
  const [tgsWidth, setTgsWidth] = useState("");
  const [tgsQuality, setTgsQuality] = useState("");
  const [tgsFps, setTgsFps] = useState("");
  const [tgsStatus, setTgsStatus] = useState("");
  const [tgsProcessing, setTgsProcessing] = useState(false);

  const [animatedResizeFiles, setAnimatedResizeFiles] = useState<File[]>([]);
  const [animatedWidth, setAnimatedWidth] = useState("");
  const [animatedHeight, setAnimatedHeight] = useState("");
  const [animatedQuality, setAnimatedQuality] = useState("");
  const [animatedTargetSize, setAnimatedTargetSize] = useState("");
  const [animatedStatus, setAnimatedStatus] = useState("");
  const [animatedProcessing, setAnimatedProcessing] = useState(false);

  const [webpResizeFiles, setWebpResizeFiles] = useState<File[]>([]);
  const [webpResizeFormat, setWebpResizeFormat] = useState<
    "webp" | "png" | "jpg"
  >("webp");
  const [webpResizeWidth, setWebpResizeWidth] = useState("");
  const [webpResizeTarget, setWebpResizeTarget] = useState("");
  const [webpResizeQuality, setWebpResizeQuality] = useState("");
  const [webpResizeStatus, setWebpResizeStatus] = useState("");
  const [webpResizeProcessing, setWebpResizeProcessing] = useState(false);

  const [batchToWebpFiles, setBatchToWebpFiles] = useState<File[]>([]);
  const [batchToWebpWidth, setBatchToWebpWidth] = useState("");
  const [batchToWebpFps, setBatchToWebpFps] = useState("");
  const [batchToWebpQuality, setBatchToWebpQuality] = useState("");
  const [batchToWebpStatus, setBatchToWebpStatus] = useState("");
  const [batchToWebpProcessing, setBatchToWebpProcessing] = useState(false);

  const [toTgsFiles, setToTgsFiles] = useState<File[]>([]);
  const [toTgsWidth, setToTgsWidth] = useState("");
  const [toTgsFps, setToTgsFps] = useState("");
  const [toTgsStatus, setToTgsStatus] = useState("");
  const [toTgsProcessing, setToTgsProcessing] = useState(false);

  const imagesZipSummary = useMemo(
    () => summarizeFiles(imagesZipFiles),
    [imagesZipFiles]
  );
  const convertZipSummary = useMemo(
    () => summarizeFiles(convertZipFiles),
    [convertZipFiles]
  );
  const tgsSummary = useMemo(() => summarizeFiles(tgsFiles), [tgsFiles]);
  const animatedSummary = useMemo(
    () => summarizeFiles(animatedResizeFiles),
    [animatedResizeFiles]
  );
  const webpResizeSummary = useMemo(
    () => summarizeFiles(webpResizeFiles),
    [webpResizeFiles]
  );
  const batchToWebpSummary = useMemo(
    () => summarizeFiles(batchToWebpFiles),
    [batchToWebpFiles]
  );
  const toTgsSummary = useMemo(
    () => summarizeFiles(toTgsFiles),
    [toTgsFiles]
  );

  const handleImagesZip = async () => {
    if (!imagesZipFiles.length) {
      setImagesZipStatus("error:Vui lòng chọn ảnh.");
      return;
    }
    try {
      setImagesZipProcessing(true);
      setImagesZipStatus("processing:Đang chuyển ảnh sang WebP...");
      const blob = await apiClient.imagesToWebPZip(imagesZipFiles);
      downloadBlob(
        blob,
        `images_${imagesZipFiles.length}_webp.zip`
      );
      setImagesZipStatus("success:Đã tạo ZIP WebP.");
    } catch (error) {
      setImagesZipStatus(
        `error:${error instanceof Error ? error.message : "Có lỗi xảy ra"}`
      );
    } finally {
      setImagesZipProcessing(false);
    }
  };

  const handleConvertZip = async () => {
    if (!convertZipFiles.length) {
      setConvertZipStatus("error:Vui lòng chọn ảnh.");
      return;
    }
    try {
      setConvertZipProcessing(true);
      setConvertZipStatus("processing:Đang convert hàng loạt...");
      const blob = await apiClient.imagesConvertZip(convertZipFiles, {
        format: convertFormat,
        width: parseOptionalNumber(convertWidth),
        quality: parseOptionalNumber(convertQuality),
        lossless: convertFormat === "webp" ? convertLossless : undefined,
      });
      downloadBlob(
        blob,
        `images_${convertZipFiles.length}_${convertFormat}.zip`
      );
      setConvertZipStatus("success:ZIP đã sẵn sàng tải về.");
    } catch (error) {
      setConvertZipStatus(
        `error:${error instanceof Error ? error.message : "Có lỗi xảy ra"}`
      );
    } finally {
      setConvertZipProcessing(false);
    }
  };

  const handleTgsZip = async () => {
    if (!tgsFiles.length) {
      setTgsStatus("error:Vui lòng chọn file .tgs.");
      return;
    }
    try {
      setTgsProcessing(true);
      setTgsStatus("processing:Đang chuyển TGS → GIF...");
      const blob = await apiClient.tgsToGifZip(tgsFiles, {
        width: parseOptionalNumber(tgsWidth),
        quality: parseOptionalNumber(tgsQuality),
        fps: parseOptionalNumber(tgsFps),
      });
      downloadBlob(blob, `tgs_to_gif_${tgsFiles.length}.zip`);
      setTgsStatus("success:ZIP GIF đã sẵn sàng.");
    } catch (error) {
      setTgsStatus(
        `error:${error instanceof Error ? error.message : "Có lỗi xảy ra"}`
      );
    } finally {
      setTgsProcessing(false);
    }
  };

  const handleAnimatedResize = async () => {
    if (!animatedResizeFiles.length) {
      setAnimatedStatus("error:Vui lòng chọn WebP/GIF.");
      return;
    }
    try {
      setAnimatedProcessing(true);
      setAnimatedStatus("processing:Đang resize animation...");
      const blob = await apiClient.batchAnimatedResizeZip(animatedResizeFiles, {
        width: parseOptionalNumber(animatedWidth),
        height: parseOptionalNumber(animatedHeight),
        targetSizeKb: parseOptionalNumber(animatedTargetSize),
        quality: parseOptionalNumber(animatedQuality),
      });
      downloadBlob(
        blob,
        `resized_${animatedResizeFiles.length}_animated.zip`
      );
      setAnimatedStatus("success:Resize hoàn tất.");
    } catch (error) {
      setAnimatedStatus(
        `error:${error instanceof Error ? error.message : "Có lỗi xảy ra"}`
      );
    } finally {
      setAnimatedProcessing(false);
    }
  };

  const handleWebpResize = async () => {
    if (!webpResizeFiles.length) {
      setWebpResizeStatus("error:Vui lòng chọn ảnh.");
      return;
    }
    try {
      setWebpResizeProcessing(true);
      setWebpResizeStatus("processing:Đang resize & optimize...");
      const blob = await apiClient.webpResizeZip(webpResizeFiles, {
        format: webpResizeFormat,
        width: parseOptionalNumber(webpResizeWidth),
        targetSizeKb: parseOptionalNumber(webpResizeTarget),
        quality: parseOptionalNumber(webpResizeQuality),
      });
      downloadBlob(
        blob,
        `resized_${webpResizeFiles.length}_${webpResizeFormat}.zip`
      );
      setWebpResizeStatus("success:ZIP đã sẵn sàng.");
    } catch (error) {
      setWebpResizeStatus(
        `error:${error instanceof Error ? error.message : "Có lỗi xảy ra"}`
      );
    } finally {
      setWebpResizeProcessing(false);
    }
  };

  const handleBatchToWebp = async () => {
    if (!batchToWebpFiles.length) {
      setBatchToWebpStatus("error:Vui lòng chọn file.");
      return;
    }
    try {
      setBatchToWebpProcessing(true);
      setBatchToWebpStatus("processing:Đang convert sang WebP...");
      const blob = await apiClient.batchToWebpZip(batchToWebpFiles, {
        width: parseOptionalNumber(batchToWebpWidth),
        fps: parseOptionalNumber(batchToWebpFps),
        quality: parseOptionalNumber(batchToWebpQuality),
      });
      downloadBlob(blob, `batch_to_webp_${batchToWebpFiles.length}.zip`);
      setBatchToWebpStatus("success:ZIP WebP đã sẵn sàng.");
    } catch (error) {
      setBatchToWebpStatus(
        `error:${error instanceof Error ? error.message : "Có lỗi xảy ra"}`
      );
    } finally {
      setBatchToWebpProcessing(false);
    }
  };

  const handleFilesToTgs = async () => {
    if (!toTgsFiles.length) {
      setToTgsStatus("error:Vui lòng chọn file.");
      return;
    }
    try {
      setToTgsProcessing(true);
      setToTgsStatus("processing:Đang chuyển sang TGS...");
      const blob = await apiClient.filesToTgsZip(toTgsFiles, {
        width: parseOptionalNumber(toTgsWidth),
        fps: parseOptionalNumber(toTgsFps),
      });
      downloadBlob(blob, `to_tgs_${toTgsFiles.length}.zip`);
      setToTgsStatus("success:ZIP TGS đã sẵn sàng.");
    } catch (error) {
      setToTgsStatus(
        `error:${error instanceof Error ? error.message : "Có lỗi xảy ra"}`
      );
    } finally {
      setToTgsProcessing(false);
    }
  };

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
              Batch Ops
            </p>
            <h1 className="text-3xl font-heading font-semibold text-[var(--foreground)] md:text-4xl">
              Xử lý hàng loạt
            </h1>
            <p className="mt-1 text-sm text-[var(--muted)]">
              Upload nhiều file, trả về ZIP tối ưu theo preset.
            </p>
          </div>
        </div>
        <span className="rounded-full bg-[var(--secondary)] px-4 py-2 text-xs font-semibold text-[var(--muted)] border border-[var(--border)]">
          Endpoints: /images-to-webp-zip · /images-convert-zip · /tgs-to-gif-zip · /files-to-tgs-zip · /batch-to-webp-zip · /batch-animated-resize-zip · /webp-resize-zip
        </span>
      </header>

      <section className="mt-8 grid gap-6 lg:grid-cols-2">
        <div className="space-y-6">
          <div className="glass-card p-6">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.3em] text-[var(--muted)]">
                  WebP ZIP
                </p>
                <h2 className="mt-2 text-xl font-heading font-semibold text-[var(--foreground)]">
                  PNG/JPG → WebP
                </h2>
                <p className="mt-1 text-sm text-[var(--muted)]">
                  Chuyển hàng loạt ảnh sang WebP và đóng gói ZIP.
                </p>
              </div>
              <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-sky-500/20 text-sky-400">
                <Package className="h-5 w-5" />
              </div>
            </div>

            <div className="mt-5 space-y-4">
              <input
                type="file"
                accept="image/png,image/jpeg"
                multiple
                onChange={(event) =>
                  setImagesZipFiles(Array.from(event.target.files || []))
                }
                className="w-full rounded-2xl border border-[var(--border)] bg-[var(--secondary)] px-4 py-3 text-sm text-[var(--foreground)] file:mr-4 file:rounded-full file:border-0 file:bg-sky-500/20 file:px-4 file:py-2 file:text-xs file:font-semibold file:text-sky-400 cursor-pointer"
              />
              <div className="text-xs text-[var(--muted)]">{imagesZipSummary}</div>
            </div>

            <button
              onClick={handleImagesZip}
              disabled={imagesZipProcessing || !imagesZipFiles.length}
              className="mt-6 flex w-full items-center justify-center gap-2 rounded-2xl bg-gradient-to-r from-sky-500 to-blue-600 px-4 py-3 text-sm font-semibold text-white shadow-lg transition hover:-translate-y-0.5 hover:shadow-sky-500/20 disabled:cursor-not-allowed disabled:opacity-50 cursor-pointer"
            >
              {imagesZipProcessing ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Download className="h-4 w-4" />
              )}
              Tạo ZIP WebP
            </button>
            <div className="mt-4">
              <StatusNotice status={imagesZipStatus} />
            </div>
          </div>

          <div className="glass-card p-6">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.3em] text-[var(--muted)]">
                  Batch Convert
                </p>
                <h2 className="mt-2 text-xl font-heading font-semibold text-[var(--foreground)]">
                  Convert đa định dạng
                </h2>
                <p className="mt-1 text-sm text-[var(--muted)]">
                  Chọn format, width, chất lượng và xuất ZIP.
                </p>
              </div>
              <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-indigo-500/20 text-indigo-400">
                <Wand2 className="h-5 w-5" />
              </div>
            </div>

            <div className="mt-5 space-y-4">
              <input
                type="file"
                accept="image/png,image/jpeg,image/webp"
                multiple
                onChange={(event) =>
                  setConvertZipFiles(Array.from(event.target.files || []))
                }
                className="w-full rounded-2xl border border-[var(--border)] bg-[var(--secondary)] px-4 py-3 text-sm text-[var(--foreground)] file:mr-4 file:rounded-full file:border-0 file:bg-indigo-500/20 file:px-4 file:py-2 file:text-xs file:font-semibold file:text-indigo-400 cursor-pointer"
              />
              <div className="text-xs text-[var(--muted)]">{convertZipSummary}</div>
            </div>

            <div className="mt-5 grid gap-4 md:grid-cols-2">
              <div>
                <label className="text-xs font-semibold uppercase tracking-widest text-[var(--muted)]">
                  Format
                </label>
                <select
                  value={convertFormat}
                  onChange={(event) =>
                    setConvertFormat(event.target.value as "webp" | "png" | "jpg")
                  }
                  className="input mt-2 cursor-pointer"
                >
                  <option value="webp">WebP</option>
                  <option value="png">PNG</option>
                  <option value="jpg">JPG</option>
                </select>
              </div>
              <div>
                <label className="text-xs font-semibold uppercase tracking-widest text-[var(--muted)]">
                  Width
                </label>
                <input
                  type="number"
                  min="16"
                  max="4096"
                  placeholder="Auto"
                  value={convertWidth}
                  onChange={(event) => setConvertWidth(event.target.value)}
                  className="input mt-2"
                />
              </div>
              <div>
                <label className="text-xs font-semibold uppercase tracking-widest text-[var(--muted)]">
                  Quality
                </label>
                <input
                  type="number"
                  min="1"
                  max="100"
                  placeholder="Auto"
                  value={convertQuality}
                  onChange={(event) => setConvertQuality(event.target.value)}
                  className="input mt-2"
                />
              </div>
              <div className="flex items-center gap-3 pt-6 text-xs font-semibold text-[var(--muted)]">
                <input
                  id="lossless"
                  type="checkbox"
                  checked={convertLossless}
                  onChange={(event) => setConvertLossless(event.target.checked)}
                  className="h-4 w-4 rounded border-[var(--border)] accent-[var(--primary)] cursor-pointer"
                  disabled={convertFormat !== "webp"}
                />
                <label htmlFor="lossless" className="cursor-pointer">
                  WebP lossless
                </label>
              </div>
            </div>

            <button
              onClick={handleConvertZip}
              disabled={convertZipProcessing || !convertZipFiles.length}
              className="mt-6 flex w-full items-center justify-center gap-2 rounded-2xl bg-gradient-to-r from-indigo-500 to-purple-600 px-4 py-3 text-sm font-semibold text-white shadow-lg transition hover:-translate-y-0.5 hover:shadow-indigo-500/20 disabled:cursor-not-allowed disabled:opacity-50 cursor-pointer"
            >
              {convertZipProcessing ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Download className="h-4 w-4" />
              )}
              Convert & ZIP
            </button>
            <div className="mt-4">
              <StatusNotice status={convertZipStatus} />
            </div>
          </div>
        </div>

        <div className="space-y-6">
          <div className="glass-card p-6">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.3em] text-[var(--muted)]">
                  TGS → GIF
                </p>
                <h2 className="mt-2 text-xl font-heading font-semibold text-[var(--foreground)]">
                  Telegram Sticker
                </h2>
                <p className="mt-1 text-sm text-[var(--muted)]">
                  Chuyển nhiều file .tgs sang GIF và tải ZIP.
                </p>
              </div>
              <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-emerald-500/20 text-emerald-400">
                <Sparkles className="h-5 w-5" />
              </div>
            </div>

            <div className="mt-5 space-y-4">
              <input
                type="file"
                accept=".tgs"
                multiple
                onChange={(event) =>
                  setTgsFiles(Array.from(event.target.files || []))
                }
                className="w-full rounded-2xl border border-[var(--border)] bg-[var(--secondary)] px-4 py-3 text-sm text-[var(--foreground)] file:mr-4 file:rounded-full file:border-0 file:bg-emerald-500/20 file:px-4 file:py-2 file:text-xs file:font-semibold file:text-emerald-400 cursor-pointer"
              />
              <div className="text-xs text-[var(--muted)]">{tgsSummary}</div>
            </div>

            <div className="mt-5 grid gap-4 md:grid-cols-3">
              <div>
                <label className="text-xs font-semibold uppercase tracking-widest text-[var(--muted)]">
                  Width
                </label>
                <input
                  type="number"
                  min="16"
                  max="2048"
                  placeholder="Auto"
                  value={tgsWidth}
                  onChange={(event) => setTgsWidth(event.target.value)}
                  className="input mt-2"
                />
              </div>
              <div>
                <label className="text-xs font-semibold uppercase tracking-widest text-[var(--muted)]">
                  Quality
                </label>
                <input
                  type="number"
                  min="1"
                  max="100"
                  placeholder="Auto"
                  value={tgsQuality}
                  onChange={(event) => setTgsQuality(event.target.value)}
                  className="input mt-2"
                />
              </div>
              <div>
                <label className="text-xs font-semibold uppercase tracking-widest text-[var(--muted)]">
                  FPS
                </label>
                <input
                  type="number"
                  min="1"
                  max="60"
                  placeholder="30"
                  value={tgsFps}
                  onChange={(event) => setTgsFps(event.target.value)}
                  className="input mt-2"
                />
              </div>
            </div>

            <button
              onClick={handleTgsZip}
              disabled={tgsProcessing || !tgsFiles.length}
              className="mt-6 flex w-full items-center justify-center gap-2 rounded-2xl bg-gradient-to-r from-emerald-500 to-teal-600 px-4 py-3 text-sm font-semibold text-white shadow-lg transition hover:-translate-y-0.5 hover:shadow-emerald-500/20 disabled:cursor-not-allowed disabled:opacity-50 cursor-pointer"
            >
              {tgsProcessing ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Download className="h-4 w-4" />
              )}
              Convert TGS → GIF
            </button>
            <div className="mt-4">
              <StatusNotice status={tgsStatus} />
            </div>
          </div>

          <div className="glass-card p-6">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.3em] text-[var(--muted)]">
                  Files → TGS
                </p>
                <h2 className="mt-2 text-xl font-heading font-semibold text-[var(--foreground)]">
                  Chuyển sang TGS
                </h2>
                <p className="mt-1 text-sm text-[var(--muted)]">
                  Chuyển JSON/GIF/WebP/WebM/PNG sang TGS (Telegram Sticker).
                </p>
              </div>
              <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-pink-500/20 text-pink-400">
                <Sparkles className="h-5 w-5" />
              </div>
            </div>

            <div className="mt-5 space-y-4">
              <input
                type="file"
                accept=".json,.gif,.webp,.webm,.png,.jpg,.jpeg"
                multiple
                onChange={(event) =>
                  setToTgsFiles(Array.from(event.target.files || []))
                }
                className="w-full rounded-2xl border border-[var(--border)] bg-[var(--secondary)] px-4 py-3 text-sm text-[var(--foreground)] file:mr-4 file:rounded-full file:border-0 file:bg-pink-500/20 file:px-4 file:py-2 file:text-xs file:font-semibold file:text-pink-400 cursor-pointer"
              />
              <div className="text-xs text-[var(--muted)]">{toTgsSummary}</div>
            </div>

            <div className="mt-5 grid gap-4 md:grid-cols-2">
              <div>
                <label className="text-xs font-semibold uppercase tracking-widest text-[var(--muted)]">
                  Width
                </label>
                <input
                  type="number"
                  min="16"
                  max="2048"
                  placeholder="Auto"
                  value={toTgsWidth}
                  onChange={(event) => setToTgsWidth(event.target.value)}
                  className="input mt-2"
                />
              </div>
              <div>
                <label className="text-xs font-semibold uppercase tracking-widest text-[var(--muted)]">
                  FPS (animated)
                </label>
                <input
                  type="number"
                  min="1"
                  max="60"
                  placeholder="30"
                  value={toTgsFps}
                  onChange={(event) => setToTgsFps(event.target.value)}
                  className="input mt-2"
                />
              </div>
            </div>

            <button
              onClick={handleFilesToTgs}
              disabled={toTgsProcessing || !toTgsFiles.length}
              className="mt-6 flex w-full items-center justify-center gap-2 rounded-2xl bg-gradient-to-r from-pink-500 to-rose-600 px-4 py-3 text-sm font-semibold text-white shadow-lg transition hover:-translate-y-0.5 hover:shadow-pink-500/20 disabled:cursor-not-allowed disabled:opacity-50 cursor-pointer"
            >
              {toTgsProcessing ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Download className="h-4 w-4" />
              )}
              Convert → TGS ZIP
            </button>
            <div className="mt-4">
              <StatusNotice status={toTgsStatus} />
            </div>
          </div>

          <div className="glass-card p-6">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.3em] text-[var(--muted)]">
                  Animated Resize
                </p>
                <h2 className="mt-2 text-xl font-heading font-semibold text-[var(--foreground)]">
                  Resize WebP/GIF động
                </h2>
                <p className="mt-1 text-sm text-[var(--muted)]">
                  Thay đổi kích thước + target size để tối ưu dung lượng.
                </p>
              </div>
              <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-amber-500/20 text-amber-400">
                <Package className="h-5 w-5" />
              </div>
            </div>

            <div className="mt-5 space-y-4">
              <input
                type="file"
                accept="image/webp,image/gif"
                multiple
                onChange={(event) =>
                  setAnimatedResizeFiles(Array.from(event.target.files || []))
                }
                className="w-full rounded-2xl border border-[var(--border)] bg-[var(--secondary)] px-4 py-3 text-sm text-[var(--foreground)] file:mr-4 file:rounded-full file:border-0 file:bg-amber-500/20 file:px-4 file:py-2 file:text-xs file:font-semibold file:text-amber-400 cursor-pointer"
              />
              <div className="text-xs text-[var(--muted)]">{animatedSummary}</div>
            </div>

            <div className="mt-5 grid gap-4 md:grid-cols-2">
              <div>
                <label className="text-xs font-semibold uppercase tracking-widest text-[var(--muted)]">
                  Width
                </label>
                <input
                  type="number"
                  min="16"
                  max="4096"
                  placeholder="Auto"
                  value={animatedWidth}
                  onChange={(event) => setAnimatedWidth(event.target.value)}
                  className="input mt-2"
                />
              </div>
              <div>
                <label className="text-xs font-semibold uppercase tracking-widest text-[var(--muted)]">
                  Height
                </label>
                <input
                  type="number"
                  min="16"
                  max="4096"
                  placeholder="Auto"
                  value={animatedHeight}
                  onChange={(event) => setAnimatedHeight(event.target.value)}
                  className="input mt-2"
                />
              </div>
              <div>
                <label className="text-xs font-semibold uppercase tracking-widest text-[var(--muted)]">
                  Target KB
                </label>
                <input
                  type="number"
                  min="1"
                  max="10240"
                  placeholder="Auto"
                  value={animatedTargetSize}
                  onChange={(event) => setAnimatedTargetSize(event.target.value)}
                  className="input mt-2"
                />
              </div>
              <div>
                <label className="text-xs font-semibold uppercase tracking-widest text-[var(--muted)]">
                  Quality
                </label>
                <input
                  type="number"
                  min="1"
                  max="100"
                  placeholder="Auto"
                  value={animatedQuality}
                  onChange={(event) => setAnimatedQuality(event.target.value)}
                  className="input mt-2"
                />
              </div>
            </div>

            <button
              onClick={handleAnimatedResize}
              disabled={animatedProcessing || !animatedResizeFiles.length}
              className="mt-6 flex w-full items-center justify-center gap-2 rounded-2xl bg-gradient-to-r from-amber-500 to-orange-600 px-4 py-3 text-sm font-semibold text-white shadow-lg transition hover:-translate-y-0.5 hover:shadow-amber-500/20 disabled:cursor-not-allowed disabled:opacity-50 cursor-pointer"
            >
              {animatedProcessing ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Download className="h-4 w-4" />
              )}
              Resize Animated ZIP
            </button>
            <div className="mt-4">
              <StatusNotice status={animatedStatus} />
            </div>
          </div>

          <div className="glass-card p-6">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.3em] text-[var(--muted)]">
                  WebP Resize
                </p>
                <h2 className="mt-2 text-xl font-heading font-semibold text-[var(--foreground)]">
                  Resize + target size
                </h2>
                <p className="mt-1 text-sm text-[var(--muted)]">
                  Dùng cho ảnh tĩnh WebP/JPG/PNG.
                </p>
              </div>
              <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-slate-500/20 text-slate-400">
                <Package className="h-5 w-5" />
              </div>
            </div>

            <div className="mt-5 space-y-4">
              <input
                type="file"
                accept="image/png,image/jpeg,image/webp"
                multiple
                onChange={(event) =>
                  setWebpResizeFiles(Array.from(event.target.files || []))
                }
                className="w-full rounded-2xl border border-[var(--border)] bg-[var(--secondary)] px-4 py-3 text-sm text-[var(--foreground)] file:mr-4 file:rounded-full file:border-0 file:bg-slate-500/20 file:px-4 file:py-2 file:text-xs file:font-semibold file:text-slate-400 cursor-pointer"
              />
              <div className="text-xs text-[var(--muted)]">{webpResizeSummary}</div>
            </div>

            <div className="mt-5 grid gap-4 md:grid-cols-2">
              <div>
                <label className="text-xs font-semibold uppercase tracking-widest text-[var(--muted)]">
                  Format
                </label>
                <select
                  value={webpResizeFormat}
                  onChange={(event) =>
                    setWebpResizeFormat(
                      event.target.value as "webp" | "png" | "jpg"
                    )
                  }
                  className="input mt-2 cursor-pointer"
                >
                  <option value="webp">WebP</option>
                  <option value="png">PNG</option>
                  <option value="jpg">JPG</option>
                </select>
              </div>
              <div>
                <label className="text-xs font-semibold uppercase tracking-widest text-[var(--muted)]">
                  Width
                </label>
                <input
                  type="number"
                  min="16"
                  max="4096"
                  placeholder="Auto"
                  value={webpResizeWidth}
                  onChange={(event) => setWebpResizeWidth(event.target.value)}
                  className="input mt-2"
                />
              </div>
              <div>
                <label className="text-xs font-semibold uppercase tracking-widest text-[var(--muted)]">
                  Target KB
                </label>
                <input
                  type="number"
                  min="1"
                  max="10240"
                  placeholder="Auto"
                  value={webpResizeTarget}
                  onChange={(event) => setWebpResizeTarget(event.target.value)}
                  className="input mt-2"
                />
              </div>
              <div>
                <label className="text-xs font-semibold uppercase tracking-widest text-[var(--muted)]">
                  Quality
                </label>
                <input
                  type="number"
                  min="1"
                  max="100"
                  placeholder="Auto"
                  value={webpResizeQuality}
                  onChange={(event) => setWebpResizeQuality(event.target.value)}
                  className="input mt-2"
                />
              </div>
            </div>

            <button
              onClick={handleWebpResize}
              disabled={webpResizeProcessing || !webpResizeFiles.length}
              className="mt-6 flex w-full items-center justify-center gap-2 rounded-2xl bg-gradient-to-r from-slate-600 to-slate-800 px-4 py-3 text-sm font-semibold text-white shadow-lg transition hover:-translate-y-0.5 hover:shadow-slate-500/20 disabled:cursor-not-allowed disabled:opacity-50 cursor-pointer"
            >
              {webpResizeProcessing ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Download className="h-4 w-4" />
              )}
              Resize & ZIP
            </button>
            <div className="mt-4">
              <StatusNotice status={webpResizeStatus} />
            </div>
          </div>

          <div className="glass-card p-6">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.3em] text-[var(--muted)]">
                  Universal → WebP
                </p>
                <h2 className="mt-2 text-xl font-heading font-semibold text-[var(--foreground)]">
                  TGS/WebM/PNG/GIF → WebP
                </h2>
                <p className="mt-1 text-sm text-[var(--muted)]">
                  Chuyển nhiều file sang WebP và tải ZIP.
                </p>
              </div>
              <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-violet-500/20 text-violet-400">
                <Sparkles className="h-5 w-5" />
              </div>
            </div>

            <div className="mt-5 space-y-4">
              <input
                type="file"
                accept=".tgs,.webm,.png,.jpg,.jpeg,.gif"
                multiple
                onChange={(event) =>
                  setBatchToWebpFiles(Array.from(event.target.files || []))
                }
                className="w-full rounded-2xl border border-[var(--border)] bg-[var(--secondary)] px-4 py-3 text-sm text-[var(--foreground)] file:mr-4 file:rounded-full file:border-0 file:bg-violet-500/20 file:px-4 file:py-2 file:text-xs file:font-semibold file:text-violet-400 cursor-pointer"
              />
              <div className="text-xs text-[var(--muted)]">{batchToWebpSummary}</div>
            </div>

            <div className="mt-5 grid gap-4 md:grid-cols-3">
              <div>
                <label className="text-xs font-semibold uppercase tracking-widest text-[var(--muted)]">
                  Width
                </label>
                <input
                  type="number"
                  min="16"
                  max="4096"
                  placeholder="Auto"
                  value={batchToWebpWidth}
                  onChange={(event) => setBatchToWebpWidth(event.target.value)}
                  className="input mt-2"
                />
              </div>
              <div>
                <label className="text-xs font-semibold uppercase tracking-widest text-[var(--muted)]">
                  FPS (animated)
                </label>
                <input
                  type="number"
                  min="1"
                  max="60"
                  placeholder="15"
                  value={batchToWebpFps}
                  onChange={(event) => setBatchToWebpFps(event.target.value)}
                  className="input mt-2"
                />
              </div>
              <div>
                <label className="text-xs font-semibold uppercase tracking-widest text-[var(--muted)]">
                  Quality
                </label>
                <input
                  type="number"
                  min="1"
                  max="100"
                  placeholder="80"
                  value={batchToWebpQuality}
                  onChange={(event) => setBatchToWebpQuality(event.target.value)}
                  className="input mt-2"
                />
              </div>
            </div>

            <button
              onClick={handleBatchToWebp}
              disabled={batchToWebpProcessing || !batchToWebpFiles.length}
              className="mt-6 flex w-full items-center justify-center gap-2 rounded-2xl bg-gradient-to-r from-violet-500 to-purple-600 px-4 py-3 text-sm font-semibold text-white shadow-lg transition hover:-translate-y-0.5 hover:shadow-violet-500/20 disabled:cursor-not-allowed disabled:opacity-50 cursor-pointer"
            >
              {batchToWebpProcessing ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Download className="h-4 w-4" />
              )}
              Convert → WebP ZIP
            </button>
            <div className="mt-4">
              <StatusNotice status={batchToWebpStatus} />
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}
