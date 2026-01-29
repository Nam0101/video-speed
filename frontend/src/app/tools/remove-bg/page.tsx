"use client";

import { useRef, useState, useCallback } from "react";
import Link from "next/link";
import {
    AlertCircle,
    ArrowLeft,
    CheckCircle2,
    Download,
    Eraser,
    Loader2,
    Upload,
    Image as ImageIcon,
    Sparkles,
    Files,
} from "lucide-react";
import { apiClient } from "@/lib/api-client";
import { downloadBlob, formatBytes } from "@/lib/file-utils";

type Mode = "single" | "batch";

export default function RemoveBackgroundPage() {
    const [mode, setMode] = useState<Mode>("single");
    const [file, setFile] = useState<File | null>(null);
    const [files, setFiles] = useState<File[]>([]);
    const [status, setStatus] = useState("");
    const [processing, setProcessing] = useState(false);
    const [dragActive, setDragActive] = useState(false);
    const [previewUrl, setPreviewUrl] = useState<string | null>(null);
    const [resultUrl, setResultUrl] = useState<string | null>(null);
    const [removeAlpha, setRemoveAlpha] = useState(false);
    const fileInputRef = useRef<HTMLInputElement>(null);

    const handleDrag = useCallback((event: React.DragEvent) => {
        event.preventDefault();
        event.stopPropagation();
        if (event.type === "dragenter" || event.type === "dragover") {
            setDragActive(true);
        } else if (event.type === "dragleave") {
            setDragActive(false);
        }
    }, []);

    const handleDrop = useCallback(
        (event: React.DragEvent) => {
            event.preventDefault();
            event.stopPropagation();
            setDragActive(false);

            const droppedFiles = Array.from(event.dataTransfer.files).filter((f) =>
                /\.(png|jpe?g|webp)$/i.test(f.name)
            );

            if (mode === "single" && droppedFiles[0]) {
                setFile(droppedFiles[0]);
                setPreviewUrl(URL.createObjectURL(droppedFiles[0]));
                setResultUrl(null);
                setStatus("");
            } else if (mode === "batch" && droppedFiles.length > 0) {
                setFiles(droppedFiles);
                setStatus("");
            }
        },
        [mode]
    );

    const handleFileChange = useCallback(
        (event: React.ChangeEvent<HTMLInputElement>) => {
            const selectedFiles = Array.from(event.target.files || []).filter((f) =>
                /\.(png|jpe?g|webp)$/i.test(f.name)
            );

            if (mode === "single" && selectedFiles[0]) {
                setFile(selectedFiles[0]);
                setPreviewUrl(URL.createObjectURL(selectedFiles[0]));
                setResultUrl(null);
                setStatus("");
            } else if (mode === "batch" && selectedFiles.length > 0) {
                setFiles(selectedFiles);
                setStatus("");
            }
        },
        [mode]
    );

    const handleProcess = async () => {
        if (mode === "single") {
            if (!file) {
                setStatus("error:Hãy chọn ảnh trước khi xử lý.");
                return;
            }

            try {
                setProcessing(true);
                setStatus("processing:Đang xóa nền bằng AI...");
                const blob = await apiClient.removeBackground(file, {
                    removeAlpha,
                    bgColor: "#FFFFFF",
                });

                // Create preview URL for result
                const url = URL.createObjectURL(blob);
                setResultUrl(url);

                // Auto download
                const filename = `${file.name.replace(/\.[^/.]+$/, "")}_nobg.png`;
                downloadBlob(blob, filename);
                setStatus("success:Xóa nền thành công!");
            } catch (error) {
                setStatus(
                    `error:${error instanceof Error ? error.message : "Có lỗi xảy ra"}`
                );
            } finally {
                setProcessing(false);
            }
        } else {
            if (files.length === 0) {
                setStatus("error:Hãy chọn ít nhất 1 ảnh.");
                return;
            }

            try {
                setProcessing(true);
                setStatus(`processing:Đang xóa nền ${files.length} ảnh...`);
                const blob = await apiClient.removeBackgroundZip(files, {
                    removeAlpha,
                    bgColor: "#FFFFFF",
                });
                downloadBlob(blob, `nobg_${files.length}_images.zip`);
                setStatus(`success:Đã xóa nền ${files.length} ảnh thành công!`);
            } catch (error) {
                setStatus(
                    `error:${error instanceof Error ? error.message : "Có lỗi xảy ra"}`
                );
            } finally {
                setProcessing(false);
            }
        }
    };

    const switchMode = (newMode: Mode) => {
        setMode(newMode);
        setFile(null);
        setFiles([]);
        setPreviewUrl(null);
        setResultUrl(null);
        setStatus("");
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
                    ? "bg-violet-500/10 border-violet-500/30 text-violet-400"
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
                            AI Image Processing
                        </p>
                        <h1 className="text-3xl font-heading font-semibold text-[var(--foreground)] md:text-4xl">
                            Remove Background
                        </h1>
                        <p className="mt-1 text-sm text-[var(--muted)]">
                            Xóa nền ảnh tự động bằng AI, output PNG trong suốt.
                        </p>
                    </div>
                </div>
                <div className="flex items-center gap-2">
                    <span className="rounded-full bg-gradient-to-r from-violet-500 to-fuchsia-500 px-4 py-2 text-xs font-semibold text-white shadow-lg shadow-violet-500/30">
                        <Sparkles className="inline h-3 w-3 mr-1" />
                        AI Powered
                    </span>
                </div>
            </header>

            {/* Mode Tabs */}
            <div className="mt-8 flex gap-2">
                <button
                    onClick={() => switchMode("single")}
                    className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-all cursor-pointer ${mode === "single"
                        ? "bg-violet-500 text-white shadow-lg shadow-violet-500/30"
                        : "bg-[var(--secondary)] text-[var(--muted)] hover:bg-[var(--card)] border border-[var(--border)]"
                        }`}
                >
                    <ImageIcon className="h-4 w-4" />
                    Single Image
                </button>
                <button
                    onClick={() => switchMode("batch")}
                    className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-all cursor-pointer ${mode === "batch"
                        ? "bg-violet-500 text-white shadow-lg shadow-violet-500/30"
                        : "bg-[var(--secondary)] text-[var(--muted)] hover:bg-[var(--card)] border border-[var(--border)]"
                        }`}
                >
                    <Files className="h-4 w-4" />
                    Batch Mode
                </button>
            </div>

            <section className="mt-6 grid gap-6 lg:grid-cols-[1fr_0.85fr]">
                <div className="glass-card p-6">
                    <div className="flex items-start justify-between gap-4">
                        <div>
                            <p className="text-xs font-semibold uppercase tracking-[0.3em] text-[var(--muted)]">
                                Input
                            </p>
                            <h2 className="mt-2 text-xl font-heading font-semibold text-[var(--foreground)]">
                                {mode === "single" ? "Chọn ảnh" : "Chọn nhiều ảnh"}
                            </h2>
                            <p className="mt-1 text-sm text-[var(--muted)]">
                                Chấp nhận PNG, JPG, WebP. Output PNG.
                            </p>
                        </div>
                        <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-violet-500/20 text-violet-400">
                            <Eraser className="h-5 w-5" />
                        </div>
                    </div>

                    <div
                        className={`group relative mt-6 rounded-2xl border-2 border-dashed p-6 transition-all duration-300 focus-within:ring-2 focus-within:ring-violet-400/60 ${dragActive
                            ? "border-violet-400 bg-violet-500/10 glow-sm"
                            : (mode === "single" && file) || (mode === "batch" && files.length > 0)
                                ? "border-[var(--primary)] bg-[var(--primary)]/10"
                                : "border-[var(--border)] bg-[var(--secondary)] hover:border-violet-400/50 hover:bg-[var(--card)]"
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
                            accept="image/png,image/jpeg,image/webp"
                            multiple={mode === "batch"}
                            onChange={handleFileChange}
                            className="hidden"
                            disabled={processing}
                        />

                        <div
                            role="button"
                            tabIndex={0}
                            aria-label="Chọn file ảnh để xóa nền"
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
                                className={`mx-auto flex h-16 w-16 items-center justify-center rounded-2xl transition-transform duration-300 ${(mode === "single" && file) || (mode === "batch" && files.length > 0)
                                    ? "bg-violet-500 text-white"
                                    : "bg-gradient-to-br from-violet-500 to-fuchsia-500 text-white group-hover:scale-110"
                                    }`}
                            >
                                {(mode === "single" && file) || (mode === "batch" && files.length > 0) ? (
                                    <CheckCircle2 className="h-8 w-8" />
                                ) : (
                                    <Upload className="h-8 w-8" />
                                )}
                            </div>

                            {mode === "single" && file ? (
                                <div className="mt-4 space-y-1">
                                    <p className="text-sm font-semibold text-violet-400">Đã chọn file</p>
                                    <p className="truncate text-sm font-medium text-[var(--foreground)]">
                                        {file.name}
                                    </p>
                                    <p className="text-xs text-[var(--muted)]">{formatBytes(file.size)}</p>
                                </div>
                            ) : mode === "batch" && files.length > 0 ? (
                                <div className="mt-4 space-y-1">
                                    <p className="text-sm font-semibold text-violet-400">
                                        Đã chọn {files.length} ảnh
                                    </p>
                                    <p className="text-xs text-[var(--muted)]">
                                        Tổng: {formatBytes(files.reduce((acc, f) => acc + f.size, 0))}
                                    </p>
                                </div>
                            ) : (
                                <div className="mt-4 space-y-1">
                                    <p className="text-sm font-semibold text-[var(--foreground)]">
                                        Kéo thả ảnh vào đây
                                    </p>
                                    <p className="text-xs text-[var(--muted)]">hoặc click để chọn file</p>
                                    <p className="text-xs text-[var(--muted)]">
                                        {mode === "single" ? "Hỗ trợ PNG/JPG/WebP" : "Có thể chọn nhiều ảnh"}
                                    </p>
                                </div>
                            )}
                        </div>

                        {dragActive && (
                            <div className="pointer-events-none absolute inset-0 rounded-2xl bg-gradient-to-br from-violet-500/20 via-transparent to-fuchsia-500/20" />
                        )}
                    </div>

                    {/* Preview area for single mode */}
                    {mode === "single" && (previewUrl || resultUrl) && (
                        <div className="mt-6 grid grid-cols-2 gap-4">
                            {previewUrl && (
                                <div className="space-y-2">
                                    <p className="text-xs font-semibold text-[var(--muted)]">Ảnh gốc</p>
                                    <div className="relative aspect-square rounded-xl overflow-hidden bg-[var(--secondary)] border border-[var(--border)]">
                                        <img
                                            src={previewUrl}
                                            alt="Original"
                                            className="w-full h-full object-contain"
                                        />
                                    </div>
                                </div>
                            )}
                            {resultUrl && (
                                <div className="space-y-2">
                                    <p className="text-xs font-semibold text-emerald-400">Đã xóa nền</p>
                                    <div
                                        className="relative aspect-square rounded-xl overflow-hidden border border-[var(--border)]"
                                        style={{
                                            backgroundImage:
                                                "linear-gradient(45deg, #1a1a2e 25%, transparent 25%), linear-gradient(-45deg, #1a1a2e 25%, transparent 25%), linear-gradient(45deg, transparent 75%, #1a1a2e 75%), linear-gradient(-45deg, transparent 75%, #1a1a2e 75%)",
                                            backgroundSize: "20px 20px",
                                            backgroundPosition: "0 0, 0 10px, 10px -10px, -10px 0px",
                                            backgroundColor: "#0f0f1a",
                                        }}
                                    >
                                        <img
                                            src={resultUrl}
                                            alt="Result"
                                            className="w-full h-full object-contain"
                                        />
                                    </div>
                                </div>
                            )}
                        </div>
                    )}
                </div>

                <aside className="space-y-6">
                    <div className="rounded-3xl bg-gradient-to-br from-violet-500 via-purple-500 to-fuchsia-500 p-[1px] shadow-2xl shadow-violet-500/20">
                        <div className="glass-card rounded-[23px] p-6">
                            <h3 className="text-lg font-heading font-semibold text-[var(--foreground)]">
                                AI Background Removal
                            </h3>
                            <p className="mt-2 text-sm text-[var(--muted)]">
                                Sử dụng deep learning để tự động phát hiện và xóa nền ảnh.
                            </p>
                            <div className="mt-4 grid gap-3 text-xs text-[var(--muted)]">
                                <div className="flex items-center justify-between">
                                    <span>Model</span>
                                    <span className="font-semibold text-violet-400">U2NET</span>
                                </div>
                                <div className="flex items-center justify-between">
                                    <span>Output</span>
                                    <span className="font-semibold text-[var(--foreground)]">
                                        {removeAlpha ? "PNG (nền trắng)" : "PNG (transparent)"}
                                    </span>
                                </div>
                                <div className="flex items-center justify-between">
                                    <span>Files</span>
                                    <span className="font-semibold text-[var(--foreground)]">
                                        {mode === "single"
                                            ? file
                                                ? "1 ảnh"
                                                : "--"
                                            : files.length > 0
                                                ? `${files.length} ảnh`
                                                : "--"}
                                    </span>
                                </div>
                            </div>

                            {/* Remove Alpha Toggle */}
                            <div className="mt-4 pt-4 border-t border-[var(--border)]">
                                <label className="flex items-center justify-between cursor-pointer">
                                    <div>
                                        <p className="text-sm font-medium text-[var(--foreground)]">Bỏ Alpha</p>
                                        <p className="text-xs text-[var(--muted)]">Thay nền trong suốt bằng màu trắng</p>
                                    </div>
                                    <button
                                        type="button"
                                        role="switch"
                                        aria-checked={removeAlpha}
                                        onClick={() => setRemoveAlpha(!removeAlpha)}
                                        className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors cursor-pointer ${removeAlpha ? "bg-violet-500" : "bg-[var(--secondary)]"}`}
                                    >
                                        <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${removeAlpha ? "translate-x-6" : "translate-x-1"}`} />
                                    </button>
                                </label>
                            </div>
                        </div>
                    </div>

                    <button
                        onClick={handleProcess}
                        disabled={
                            processing ||
                            (mode === "single" && !file) ||
                            (mode === "batch" && files.length === 0)
                        }
                        className="group relative w-full overflow-hidden rounded-2xl bg-gradient-to-r from-violet-500 via-purple-500 to-fuchsia-500 px-8 py-4 text-sm font-semibold text-white shadow-lg shadow-violet-500/20 transition-all duration-300 hover:brightness-105 hover:shadow-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-400/70 disabled:cursor-not-allowed disabled:opacity-50 cursor-pointer"
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
                                    {mode === "single" ? "Xóa nền & Tải về" : "Xóa nền & Tải ZIP"}
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
                                {statusType === "processing" && <Loader2 className="h-5 w-5 animate-spin" />}
                                <span className="font-medium">{statusMessage}</span>
                            </div>
                        </div>
                    )}

                    {/* Tips */}
                    <div className="glass-card p-4">
                        <p className="text-xs font-semibold text-[var(--muted)] uppercase tracking-wider">
                            Tips
                        </p>
                        <ul className="mt-2 space-y-2 text-xs text-[var(--muted)]">
                            <li className="flex items-start gap-2">
                                <span className="text-violet-400">•</span>
                                Ảnh có chủ thể rõ ràng sẽ cho kết quả tốt nhất
                            </li>
                            <li className="flex items-start gap-2">
                                <span className="text-violet-400">•</span>
                                Hỗ trợ người, động vật, sản phẩm, v.v.
                            </li>
                            <li className="flex items-start gap-2">
                                <span className="text-violet-400">•</span>
                                Batch mode tiết kiệm thời gian xử lý nhiều ảnh
                            </li>
                        </ul>
                    </div>
                </aside>
            </section>
        </main>
    );
}
