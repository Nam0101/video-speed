"use client";

import { useCallback, useMemo, useState } from "react";
import Link from "next/link";
import {
    AlertCircle,
    ArrowLeft,
    CheckCircle2,
    Download,
    Film,
    FileArchive,
    Image,
    Loader2,
    Package2,
    Sparkles,
    Upload,
    Video,
    X,
} from "lucide-react";
import { apiClient } from "@/lib/api-client";
import { downloadBlob, formatBytes } from "@/lib/file-utils";

const ACCEPTED_EXTENSIONS = [".tgs", ".webm", ".png", ".jpg", ".jpeg", ".gif", ".zip"];

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
    const lines = statusMessage.split('\n');

    return (
        <div className={`rounded-2xl border px-4 py-3 text-sm shadow-sm ${tone}`}>
            <div className="flex items-start gap-3">
                <div className="flex-shrink-0 mt-0.5">
                    {statusType === "error" && <AlertCircle className="h-5 w-5" />}
                    {statusType === "success" && <CheckCircle2 className="h-5 w-5" />}
                    {statusType === "processing" && (
                        <Loader2 className="h-5 w-5 animate-spin" />
                    )}
                </div>
                <div className="flex-1 min-w-0">
                    {lines.map((line, index) => (
                        <p key={index} className={`font-medium ${index > 0 ? 'mt-1 text-xs opacity-80' : ''}`}>
                            {line}
                        </p>
                    ))}
                </div>
            </div>
        </div>
    );
};

const getFileIcon = (filename: string) => {
    const ext = filename.toLowerCase().split(".").pop();
    if (ext === "zip") return <Package2 className="h-5 w-5 text-amber-500" />;
    if (ext === "tgs") return <Sparkles className="h-5 w-5 text-pink-500" />;
    if (ext === "webm") return <Video className="h-5 w-5 text-blue-500" />;
    if (ext === "gif") return <Film className="h-5 w-5 text-emerald-500" />;
    return <Image className="h-5 w-5 text-purple-500" />;
};

export default function UniversalConverterPage() {
    const [files, setFiles] = useState<File[]>([]);
    const [isDragOver, setIsDragOver] = useState(false);
    const [status, setStatus] = useState("");
    const [isProcessing, setIsProcessing] = useState(false);
    const [width, setWidth] = useState("");
    const [fps, setFps] = useState("");
    const [quality, setQuality] = useState("");

    const totalSize = useMemo(
        () => files.reduce((sum, file) => sum + file.size, 0),
        [files]
    );

    const summary = useMemo(() => {
        if (!files.length) return "Kéo thả file vào đây hoặc click để chọn";
        const zipCount = files.filter((f) => f.name.toLowerCase().endsWith(".zip")).length;
        const otherCount = files.length - zipCount;
        const parts = [];
        if (otherCount > 0) parts.push(`${otherCount} file`);
        if (zipCount > 0) parts.push(`${zipCount} ZIP`);
        return `${parts.join(" + ")} · ${formatBytes(totalSize)}`;
    }, [files, totalSize]);

    const isValidFile = useCallback((file: File) => {
        const ext = "." + file.name.toLowerCase().split(".").pop();
        return ACCEPTED_EXTENSIONS.includes(ext);
    }, []);

    const handleDragOver = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDragOver(true);
    }, []);

    const handleDragLeave = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDragOver(false);
    }, []);

    const handleDrop = useCallback(
        (e: React.DragEvent) => {
            e.preventDefault();
            e.stopPropagation();
            setIsDragOver(false);

            const droppedFiles = Array.from(e.dataTransfer.files).filter(isValidFile);
            if (droppedFiles.length > 0) {
                setFiles((prev) => [...prev, ...droppedFiles]);
                setStatus("");
            }
        },
        [isValidFile]
    );

    const handleFileSelect = useCallback(
        (e: React.ChangeEvent<HTMLInputElement>) => {
            const selectedFiles = Array.from(e.target.files || []).filter(isValidFile);
            if (selectedFiles.length > 0) {
                setFiles((prev) => [...prev, ...selectedFiles]);
                setStatus("");
            }
            e.target.value = ""; // Reset input
        },
        [isValidFile]
    );

    const removeFile = useCallback((index: number) => {
        setFiles((prev) => prev.filter((_, i) => i !== index));
    }, []);

    const clearAll = useCallback(() => {
        setFiles([]);
        setStatus("");
    }, []);

    const parseOptionalNumber = (value: string) => {
        const parsed = Number(value);
        if (!Number.isFinite(parsed) || parsed <= 0) return undefined;
        return parsed;
    };

    const handleConvert = async () => {
        if (!files.length) {
            setStatus("error:Vui lòng thêm file để convert.");
            return;
        }
        try {
            setIsProcessing(true);
            setStatus("processing:Đang xử lý và convert sang WebP...");
            const result = await apiClient.batchToWebpZip(files, {
                width: parseOptionalNumber(width),
                fps: parseOptionalNumber(fps),
                quality: parseOptionalNumber(quality),
            });

            if (!result.success) {
                // All files failed
                const failedInfo = result.failedFiles
                    .slice(0, 5)
                    .map(f => `• ${f.file}: ${f.error}`)
                    .join('\n');
                const moreInfo = result.failedCount > 5
                    ? `\n... và ${result.failedCount - 5} file khác`
                    : '';
                setStatus(`error:Không có file nào được convert thành công.\n${failedInfo}${moreInfo}`);
                return;
            }

            if (result.blob) {
                downloadBlob(result.blob, `converted_webp_${result.successfulCount}.zip`);
            }

            if (result.failedCount > 0) {
                // Partial success - some files failed
                const failedInfo = result.failedFiles
                    .slice(0, 3)
                    .map(f => `• ${f.file}: ${f.error}`)
                    .join('\n');
                const moreInfo = result.failedCount > 3
                    ? `\n... và ${result.failedCount - 3} file khác bị lỗi`
                    : '';
                setStatus(`success:Đã convert ${result.successfulCount} file thành công.\n⚠️ ${result.failedCount} file bị lỗi:\n${failedInfo}${moreInfo}`);
            } else {
                setStatus(`success:Đã tải xong! ZIP chứa ${result.successfulCount} file WebP.`);
            }
        } catch (error) {
            setStatus(
                `error:${error instanceof Error ? error.message : "Có lỗi xảy ra"}`
            );
        } finally {
            setIsProcessing(false);
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
                            Universal Converter
                        </p>
                        <h1 className="text-3xl font-heading font-semibold text-[var(--foreground)] md:text-4xl">
                            Tất cả → WebP
                        </h1>
                        <p className="mt-1 text-sm text-[var(--muted)]">
                            Kéo thả TGS, WebM, PNG, GIF hoặc ZIP chứa các file này.
                        </p>
                    </div>
                </div>
                <span className="rounded-full bg-[var(--secondary)] px-4 py-2 text-xs font-semibold text-[var(--muted)] border border-[var(--border)]">
                    Hỗ trợ: .tgs · .webm · .png · .jpg · .gif · .zip
                </span>
            </header>

            <section className="mt-8">
                <div className="glass-card p-8">
                    {/* Drag & Drop Zone */}
                    <div
                        onDragOver={handleDragOver}
                        onDragLeave={handleDragLeave}
                        onDrop={handleDrop}
                        className={`relative cursor-pointer rounded-2xl border-2 border-dashed p-12 text-center transition-all ${isDragOver
                            ? "border-[var(--primary)] bg-[var(--primary)]/10 glow-sm"
                            : "border-[var(--border)] bg-[var(--secondary)] hover:border-[var(--primary)]/50 hover:bg-[var(--card)]"
                            }`}
                    >
                        <input
                            type="file"
                            accept={ACCEPTED_EXTENSIONS.join(",")}
                            multiple
                            onChange={handleFileSelect}
                            className="absolute inset-0 cursor-pointer opacity-0"
                        />
                        <div className="flex flex-col items-center gap-4">
                            {isDragOver ? (
                                <FileArchive className="h-16 w-16 text-[var(--primary)]" />
                            ) : (
                                <Upload className="h-16 w-16 text-[var(--muted)]" />
                            )}
                            <div>
                                <p className="text-lg font-semibold text-[var(--foreground)]">
                                    {isDragOver ? "Thả file vào đây!" : summary}
                                </p>
                                <p className="mt-1 text-sm text-[var(--muted)]">
                                    TGS, WebM, PNG, JPG, GIF hoặc ZIP
                                </p>
                            </div>
                        </div>
                    </div>

                    {/* File List */}
                    {files.length > 0 && (
                        <div className="mt-6 animate-fade-up">
                            <div className="flex items-center justify-between">
                                <p className="text-sm font-semibold text-[var(--foreground)]">
                                    Danh sách file ({files.length})
                                </p>
                                <button
                                    onClick={clearAll}
                                    className="text-xs font-semibold text-rose-400 hover:text-rose-300 cursor-pointer transition-colors"
                                >
                                    Xóa tất cả
                                </button>
                            </div>
                            <div className="mt-3 max-h-60 space-y-2 overflow-y-auto">
                                {files.map((file, index) => (
                                    <div
                                        key={`${file.name}-${index}`}
                                        className="flex items-center justify-between rounded-xl bg-[var(--secondary)] px-4 py-2 border border-[var(--border)] transition-colors hover:border-[var(--primary)]/30"
                                    >
                                        <div className="flex items-center gap-3">
                                            <span className="flex-shrink-0">{getFileIcon(file.name)}</span>
                                            <div>
                                                <p className="text-sm font-medium text-[var(--foreground)] truncate max-w-xs">
                                                    {file.name}
                                                </p>
                                                <p className="text-xs text-[var(--muted)]">
                                                    {formatBytes(file.size)}
                                                </p>
                                            </div>
                                        </div>
                                        <button
                                            onClick={() => removeFile(index)}
                                            className="rounded-full p-1 text-[var(--muted)] hover:bg-[var(--card)] hover:text-rose-400 cursor-pointer transition-colors"
                                        >
                                            <X className="h-4 w-4" />
                                        </button>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Options */}
                    <div className="mt-6 grid gap-4 md:grid-cols-3">
                        <div>
                            <label className="text-xs font-semibold uppercase tracking-widest text-[var(--muted)]">
                                Width (px)
                            </label>
                            <input
                                type="number"
                                min="16"
                                max="4096"
                                placeholder="Auto"
                                value={width}
                                onChange={(e) => setWidth(e.target.value)}
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
                                value={fps}
                                onChange={(e) => setFps(e.target.value)}
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
                                value={quality}
                                onChange={(e) => setQuality(e.target.value)}
                                className="input mt-2"
                            />
                        </div>
                    </div>

                    {/* Convert Button */}
                    <button
                        onClick={handleConvert}
                        disabled={isProcessing || !files.length}
                        className="mt-8 flex w-full items-center justify-center gap-3 rounded-2xl bg-gradient-to-r from-violet-500 to-purple-600 px-6 py-4 text-lg font-semibold text-white shadow-lg transition-all hover:-translate-y-0.5 hover:shadow-xl hover:shadow-purple-500/20 disabled:cursor-not-allowed disabled:opacity-50 cursor-pointer"
                    >
                        {isProcessing ? (
                            <Loader2 className="h-6 w-6 animate-spin" />
                        ) : (
                            <Sparkles className="h-6 w-6" />
                        )}
                        {isProcessing ? "Đang xử lý..." : "Convert → WebP ZIP"}
                    </button>

                    {/* Status */}
                    <div className="mt-6">
                        <StatusNotice status={status} />
                    </div>
                </div>
            </section>
        </main>
    );
}
