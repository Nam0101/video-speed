"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import {
    AlertCircle,
    ArrowLeft,
    CheckCircle2,
    Download,
    Loader2,
    Music,
    FileAudio,
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

export default function AudioOggPage() {
    // Single file conversion
    const [singleFile, setSingleFile] = useState<File | null>(null);
    const [singleBitrate, setSingleBitrate] = useState("");
    const [singleSampleRate, setSingleSampleRate] = useState("");
    const [singleStatus, setSingleStatus] = useState("");
    const [singleProcessing, setSingleProcessing] = useState(false);

    // Batch conversion
    const [batchFiles, setBatchFiles] = useState<File[]>([]);
    const [batchBitrate, setBatchBitrate] = useState("");
    const [batchSampleRate, setBatchSampleRate] = useState("");
    const [batchStatus, setBatchStatus] = useState("");
    const [batchProcessing, setBatchProcessing] = useState(false);

    const batchSummary = useMemo(() => summarizeFiles(batchFiles), [batchFiles]);

    const handleSingleConvert = async () => {
        if (!singleFile) {
            setSingleStatus("error:Vui lòng chọn file audio.");
            return;
        }
        try {
            setSingleProcessing(true);
            setSingleStatus("processing:Đang convert sang OGG...");
            const blob = await apiClient.audioToOgg(singleFile, {
                bitrate: parseOptionalNumber(singleBitrate),
                sampleRate: parseOptionalNumber(singleSampleRate),
            });
            downloadBlob(blob, singleFile.name.replace(/\.[^/.]+$/, "") + ".ogg");
            setSingleStatus("success:Đã convert thành công!");
        } catch (error) {
            setSingleStatus(
                `error:${error instanceof Error ? error.message : "Có lỗi xảy ra"}`
            );
        } finally {
            setSingleProcessing(false);
        }
    };

    const handleBatchConvert = async () => {
        if (!batchFiles.length) {
            setBatchStatus("error:Vui lòng chọn file audio.");
            return;
        }
        try {
            setBatchProcessing(true);
            setBatchStatus("processing:Đang convert hàng loạt sang OGG...");
            const result = await apiClient.batchAudioToOggZip(batchFiles, {
                bitrate: parseOptionalNumber(batchBitrate),
                sampleRate: parseOptionalNumber(batchSampleRate),
            });

            if (!result.success) {
                const failedInfo = result.failedFiles
                    .slice(0, 5)
                    .map(f => `• ${f.file}: ${f.error}`)
                    .join('\n');
                const moreInfo = result.failedCount > 5
                    ? `\n... và ${result.failedCount - 5} file khác`
                    : '';
                setBatchStatus(`error:Không có file nào được convert.\n${failedInfo}${moreInfo}`);
                return;
            }

            if (result.blob) {
                downloadBlob(result.blob, `audio_ogg_${result.successfulCount}.zip`);
            }

            if (result.failedCount > 0) {
                const failedInfo = result.failedFiles
                    .slice(0, 3)
                    .map(f => `• ${f.file}: ${f.error}`)
                    .join('\n');
                const moreInfo = result.failedCount > 3
                    ? `\n... và ${result.failedCount - 3} file khác bị lỗi`
                    : '';
                setBatchStatus(`success:Đã convert ${result.successfulCount} file.\n⚠️ ${result.failedCount} file lỗi:\n${failedInfo}${moreInfo}`);
            } else {
                setBatchStatus("success:Đã tạo ZIP OGG thành công!");
            }
        } catch (error) {
            setBatchStatus(
                `error:${error instanceof Error ? error.message : "Có lỗi xảy ra"}`
            );
        } finally {
            setBatchProcessing(false);
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
                            Audio Converter
                        </p>
                        <h1 className="text-3xl font-heading font-semibold text-[var(--foreground)] md:text-4xl">
                            Audio → OGG
                        </h1>
                        <p className="mt-1 text-sm text-[var(--muted)]">
                            Convert MP3, WAV, FLAC, AAC, M4A sang OGG (Vorbis) với batch processing.
                        </p>
                    </div>
                </div>
                <span className="rounded-full bg-[var(--secondary)] px-4 py-2 text-xs font-semibold text-[var(--muted)] border border-[var(--border)]">
                    Endpoints: /audio-to-ogg · /batch-audio-to-ogg-zip
                </span>
            </header>

            <section className="mt-8 grid gap-6 lg:grid-cols-2">
                {/* Single File Conversion */}
                <div className="glass-card p-6">
                    <div className="flex items-start justify-between gap-4">
                        <div>
                            <p className="text-xs font-semibold uppercase tracking-[0.3em] text-[var(--muted)]">
                                Single Convert
                            </p>
                            <h2 className="mt-2 text-xl font-heading font-semibold text-[var(--foreground)]">
                                Convert 1 File
                            </h2>
                            <p className="mt-1 text-sm text-[var(--muted)]">
                                Chọn 1 file audio, convert và tải về trực tiếp.
                            </p>
                        </div>
                        <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-rose-500/20 text-rose-400">
                            <FileAudio className="h-5 w-5" />
                        </div>
                    </div>

                    <div className="mt-5 space-y-4">
                        <input
                            type="file"
                            accept=".mp3,.wav,.aac,.flac,.m4a,.ogg,.wma,.opus,audio/*"
                            onChange={(event) =>
                                setSingleFile(event.target.files?.[0] || null)
                            }
                            className="w-full rounded-2xl border border-[var(--border)] bg-[var(--secondary)] px-4 py-3 text-sm text-[var(--foreground)] file:mr-4 file:rounded-full file:border-0 file:bg-rose-500/20 file:px-4 file:py-2 file:text-xs file:font-semibold file:text-rose-400 cursor-pointer"
                        />
                        {singleFile && (
                            <div className="text-xs text-[var(--muted)]">
                                {singleFile.name} · {formatBytes(singleFile.size)}
                            </div>
                        )}
                    </div>

                    <div className="mt-5 grid gap-4 md:grid-cols-2">
                        <div>
                            <label className="text-xs font-semibold uppercase tracking-widest text-[var(--muted)]">
                                Bitrate (kbps)
                            </label>
                            <input
                                type="number"
                                min="32"
                                max="320"
                                placeholder="128"
                                value={singleBitrate}
                                onChange={(event) => setSingleBitrate(event.target.value)}
                                className="input mt-2"
                            />
                        </div>
                        <div>
                            <label className="text-xs font-semibold uppercase tracking-widest text-[var(--muted)]">
                                Sample Rate (Hz)
                            </label>
                            <input
                                type="number"
                                min="8000"
                                max="96000"
                                placeholder="Auto"
                                value={singleSampleRate}
                                onChange={(event) => setSingleSampleRate(event.target.value)}
                                className="input mt-2"
                            />
                        </div>
                    </div>

                    <button
                        onClick={handleSingleConvert}
                        disabled={singleProcessing || !singleFile}
                        className="mt-6 flex w-full items-center justify-center gap-2 rounded-2xl bg-gradient-to-r from-rose-500 to-pink-600 px-4 py-3 text-sm font-semibold text-white shadow-lg transition hover:-translate-y-0.5 hover:shadow-rose-500/20 disabled:cursor-not-allowed disabled:opacity-50 cursor-pointer"
                    >
                        {singleProcessing ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                            <Download className="h-4 w-4" />
                        )}
                        Convert → OGG
                    </button>
                    <div className="mt-4">
                        <StatusNotice status={singleStatus} />
                    </div>
                </div>

                {/* Batch Conversion */}
                <div className="glass-card p-6">
                    <div className="flex items-start justify-between gap-4">
                        <div>
                            <p className="text-xs font-semibold uppercase tracking-[0.3em] text-[var(--muted)]">
                                Batch Convert
                            </p>
                            <h2 className="mt-2 text-xl font-heading font-semibold text-[var(--foreground)]">
                                Convert hàng loạt
                            </h2>
                            <p className="mt-1 text-sm text-[var(--muted)]">
                                Chọn nhiều file audio, convert và tải ZIP.
                            </p>
                        </div>
                        <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-fuchsia-500/20 text-fuchsia-400">
                            <Music className="h-5 w-5" />
                        </div>
                    </div>

                    <div className="mt-5 space-y-4">
                        <input
                            type="file"
                            accept=".mp3,.wav,.aac,.flac,.m4a,.ogg,.wma,.opus,.zip,audio/*"
                            multiple
                            onChange={(event) =>
                                setBatchFiles(Array.from(event.target.files || []))
                            }
                            className="w-full rounded-2xl border border-[var(--border)] bg-[var(--secondary)] px-4 py-3 text-sm text-[var(--foreground)] file:mr-4 file:rounded-full file:border-0 file:bg-fuchsia-500/20 file:px-4 file:py-2 file:text-xs file:font-semibold file:text-fuchsia-400 cursor-pointer"
                        />
                        <div className="text-xs text-[var(--muted)]">{batchSummary}</div>
                    </div>

                    <div className="mt-5 grid gap-4 md:grid-cols-2">
                        <div>
                            <label className="text-xs font-semibold uppercase tracking-widest text-[var(--muted)]">
                                Bitrate (kbps)
                            </label>
                            <input
                                type="number"
                                min="32"
                                max="320"
                                placeholder="128"
                                value={batchBitrate}
                                onChange={(event) => setBatchBitrate(event.target.value)}
                                className="input mt-2"
                            />
                        </div>
                        <div>
                            <label className="text-xs font-semibold uppercase tracking-widest text-[var(--muted)]">
                                Sample Rate (Hz)
                            </label>
                            <input
                                type="number"
                                min="8000"
                                max="96000"
                                placeholder="Auto"
                                value={batchSampleRate}
                                onChange={(event) => setBatchSampleRate(event.target.value)}
                                className="input mt-2"
                            />
                        </div>
                    </div>

                    <button
                        onClick={handleBatchConvert}
                        disabled={batchProcessing || !batchFiles.length}
                        className="mt-6 flex w-full items-center justify-center gap-2 rounded-2xl bg-gradient-to-r from-fuchsia-500 to-purple-600 px-4 py-3 text-sm font-semibold text-white shadow-lg transition hover:-translate-y-0.5 hover:shadow-fuchsia-500/20 disabled:cursor-not-allowed disabled:opacity-50 cursor-pointer"
                    >
                        {batchProcessing ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                            <Download className="h-4 w-4" />
                        )}
                        Convert & Tải ZIP
                    </button>
                    <div className="mt-4">
                        <StatusNotice status={batchStatus} />
                    </div>
                </div>
            </section>

            {/* Supported Formats */}
            <section className="mt-8 glass-card p-6">
                <h3 className="text-lg font-heading font-semibold text-[var(--foreground)]">
                    Định dạng hỗ trợ
                </h3>
                <div className="mt-4 grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-3">
                    {["MP3", "WAV", "FLAC", "AAC", "M4A", "OGG", "WMA", "OPUS"].map((format) => (
                        <div
                            key={format}
                            className="flex items-center justify-center px-3 py-2 rounded-xl bg-[var(--secondary)] border border-[var(--border)] text-sm font-medium text-[var(--muted)]"
                        >
                            {format}
                        </div>
                    ))}
                </div>
                <p className="mt-4 text-sm text-[var(--muted)]">
                    <strong>Output:</strong> OGG (Vorbis codec) - Định dạng audio mở, nén lossy với chất lượng cao.
                    Phù hợp cho web, game và streaming.
                </p>
            </section>
        </main>
    );
}
