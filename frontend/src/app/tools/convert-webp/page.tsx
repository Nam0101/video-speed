"use client";

import { useCallback, useMemo, useState } from "react";
import Link from "next/link";
import {
    AlertCircle,
    ArrowLeft,
    CheckCircle2,
    Download,
    FileArchive,
    Loader2,
    Sparkles,
    Upload,
    X,
} from "lucide-react";
import { apiClient } from "@/lib/api-client";
import { downloadBlob, formatBytes } from "@/lib/file-utils";

const ACCEPTED_EXTENSIONS = [".tgs", ".webm", ".png", ".jpg", ".jpeg", ".gif", ".zip"];
const ACCEPTED_MIME_TYPES = [
    "image/png",
    "image/jpeg",
    "image/gif",
    "image/webp",
    "video/webm",
    "application/zip",
    "application/x-zip-compressed",
    "application/octet-stream", // for .tgs files
];

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

const getFileIcon = (filename: string) => {
    const ext = filename.toLowerCase().split(".").pop();
    if (ext === "zip") return "📦";
    if (ext === "tgs") return "🎭";
    if (ext === "webm") return "🎬";
    if (ext === "gif") return "🎞️";
    return "🖼️";
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
            const blob = await apiClient.batchToWebpZip(files, {
                width: parseOptionalNumber(width),
                fps: parseOptionalNumber(fps),
                quality: parseOptionalNumber(quality),
            });
            downloadBlob(blob, `converted_webp_${files.length}.zip`);
            setStatus("success:Đã tải xong! ZIP chứa các file WebP.");
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
                        className="inline-flex h-11 w-11 items-center justify-center rounded-2xl bg-white/80 text-slate-700 shadow-sm ring-1 ring-slate-200 transition hover:-translate-y-0.5"
                    >
                        <ArrowLeft className="h-5 w-5" />
                    </Link>
                    <div>
                        <p className="text-xs font-semibold uppercase tracking-[0.35em] text-slate-500">
                            Universal Converter
                        </p>
                        <h1 className="text-3xl font-heading font-semibold text-slate-900 md:text-4xl">
                            Tất cả → WebP
                        </h1>
                        <p className="mt-1 text-sm text-slate-600">
                            Kéo thả TGS, WebM, PNG, GIF hoặc ZIP chứa các file này.
                        </p>
                    </div>
                </div>
                <span className="rounded-full bg-white/70 px-4 py-2 text-xs font-semibold text-slate-600 shadow-sm ring-1 ring-slate-200">
                    Hỗ trợ: .tgs · .webm · .png · .jpg · .gif · .zip
                </span>
            </header>

            <section className="mt-8">
                <div className="rounded-3xl bg-white/80 p-8 shadow-sm ring-1 ring-slate-200">
                    {/* Drag & Drop Zone */}
                    <div
                        onDragOver={handleDragOver}
                        onDragLeave={handleDragLeave}
                        onDrop={handleDrop}
                        className={`relative cursor-pointer rounded-2xl border-2 border-dashed p-12 text-center transition-all ${isDragOver
                                ? "border-violet-400 bg-violet-50"
                                : "border-slate-300 bg-slate-50 hover:border-slate-400 hover:bg-slate-100"
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
                                <FileArchive className="h-16 w-16 text-violet-500" />
                            ) : (
                                <Upload className="h-16 w-16 text-slate-400" />
                            )}
                            <div>
                                <p className="text-lg font-semibold text-slate-700">
                                    {isDragOver ? "Thả file vào đây!" : summary}
                                </p>
                                <p className="mt-1 text-sm text-slate-500">
                                    TGS, WebM, PNG, JPG, GIF hoặc ZIP
                                </p>
                            </div>
                        </div>
                    </div>

                    {/* File List */}
                    {files.length > 0 && (
                        <div className="mt-6">
                            <div className="flex items-center justify-between">
                                <p className="text-sm font-semibold text-slate-700">
                                    Danh sách file ({files.length})
                                </p>
                                <button
                                    onClick={clearAll}
                                    className="text-xs font-semibold text-rose-500 hover:text-rose-600"
                                >
                                    Xóa tất cả
                                </button>
                            </div>
                            <div className="mt-3 max-h-60 space-y-2 overflow-y-auto">
                                {files.map((file, index) => (
                                    <div
                                        key={`${file.name}-${index}`}
                                        className="flex items-center justify-between rounded-xl bg-slate-50 px-4 py-2"
                                    >
                                        <div className="flex items-center gap-3">
                                            <span className="text-xl">{getFileIcon(file.name)}</span>
                                            <div>
                                                <p className="text-sm font-medium text-slate-700 truncate max-w-xs">
                                                    {file.name}
                                                </p>
                                                <p className="text-xs text-slate-500">
                                                    {formatBytes(file.size)}
                                                </p>
                                            </div>
                                        </div>
                                        <button
                                            onClick={() => removeFile(index)}
                                            className="rounded-full p-1 text-slate-400 hover:bg-slate-200 hover:text-slate-600"
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
                            <label className="text-xs font-semibold uppercase tracking-widest text-slate-500">
                                Width (px)
                            </label>
                            <input
                                type="number"
                                min="16"
                                max="4096"
                                placeholder="Auto"
                                value={width}
                                onChange={(e) => setWidth(e.target.value)}
                                className="mt-2 w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700"
                            />
                        </div>
                        <div>
                            <label className="text-xs font-semibold uppercase tracking-widest text-slate-500">
                                FPS (animated)
                            </label>
                            <input
                                type="number"
                                min="1"
                                max="60"
                                placeholder="15"
                                value={fps}
                                onChange={(e) => setFps(e.target.value)}
                                className="mt-2 w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700"
                            />
                        </div>
                        <div>
                            <label className="text-xs font-semibold uppercase tracking-widest text-slate-500">
                                Quality
                            </label>
                            <input
                                type="number"
                                min="1"
                                max="100"
                                placeholder="80"
                                value={quality}
                                onChange={(e) => setQuality(e.target.value)}
                                className="mt-2 w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700"
                            />
                        </div>
                    </div>

                    {/* Convert Button */}
                    <button
                        onClick={handleConvert}
                        disabled={isProcessing || !files.length}
                        className="mt-8 flex w-full items-center justify-center gap-3 rounded-2xl bg-gradient-to-r from-violet-500 to-purple-600 px-6 py-4 text-lg font-semibold text-white shadow-lg transition hover:-translate-y-0.5 hover:shadow-xl disabled:cursor-not-allowed disabled:opacity-50"
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
