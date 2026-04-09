'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import {
    ArrowLeft,
    RefreshCw,
    ChevronLeft,
    ChevronRight,
    ChevronsLeft,
    ChevronsRight,
    Search,
    Image as ImageIcon,
    AlertCircle,
    CheckCircle2
} from 'lucide-react';
import { apiClient, AiGenerationTrackingItem, PaginatedResponse } from '@/lib/api-client';

export function parseJsonString<T>(value: string | null): T | null {
    if (!value) return null;
    try {
        return JSON.parse(value) as T;
    } catch {
        return null;
    }
}

export default function AiTrackingPage() {
    const [data, setData] = useState<PaginatedResponse<AiGenerationTrackingItem> | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const [page, setPage] = useState(1);
    const [pageSize, setPageSize] = useState(20);

    useEffect(() => {
        let cancelled = false;

        async function load() {
            setLoading(true);
            setError(null);

            try {
                const response = await apiClient.getAiGenerationTracking(page, pageSize);
                if (!cancelled) {
                    setData(response);
                }
            } catch (e) {
                if (!cancelled) {
                    setError(e instanceof Error ? e.message : 'Unknown error');
                }
            } finally {
                if (!cancelled) {
                    setLoading(false);
                }
            }
        }

        load();
        return () => {
            cancelled = true;
        };
    }, [page, pageSize]);

    const handleRefresh = () => {
        setPage(1);
        // Force a re-fetch by triggering a state update that doesn't change value, but we can just use a trick
        // Actually, we'll just re-fetch in place.
        setLoading(true);
        apiClient.getAiGenerationTracking(page, pageSize)
            .then(res => setData(res))
            .catch(err => setError(err instanceof Error ? err.message : 'Unknown error'))
            .finally(() => setLoading(false));
    };

    return (
        <div className="min-h-screen bg-slate-950 text-slate-100 bg-[url('/grid.svg')] bg-center bg-fixed">
            <header className="sticky top-0 z-40 w-full border-b border-slate-800/60 bg-slate-950/80 backdrop-blur-xl supports-[backdrop-filter]:bg-slate-950/60">
                <div className="container mx-auto px-4 py-3 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
                    <div className="flex items-center gap-4">
                        <Link href="/" className="p-2 rounded-full hover:bg-slate-800 text-slate-400 hover:text-white transition-colors">
                            <ArrowLeft size={20} />
                        </Link>
                        <div>
                            <div className="flex items-center gap-2 mb-1">
                                <span className="px-2 py-0.5 rounded-md bg-blue-500/20 text-blue-400 text-[10px] font-bold uppercase tracking-wider">Analytics</span>
                            </div>
                            <h1 className="text-2xl font-bold text-white md:text-3xl tracking-tight">AI Generation Tracking</h1>
                        </div>
                    </div>
                    <div className="flex flex-wrap items-center gap-3 w-full sm:w-auto">
                        {data && data.data && data.data.length > 0 && (
                            <div className="px-4 py-2 bg-slate-800/50 rounded-lg text-sm flex items-center gap-2 border border-slate-700 whitespace-nowrap">
                                <span className="text-slate-400">Avg Gen Time (Page):</span>
                                <span className="font-bold text-emerald-400">
                                    {(data.data.reduce((acc, item) => acc + (item.durationSeconds || 0), 0) / data.data.length).toFixed(2)}s
                                </span>
                            </div>
                        )}
                        <button onClick={handleRefresh} disabled={loading} className="btn-primary cursor-pointer inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-500 transition-colors disabled:opacity-50 ml-auto sm:ml-0">
                            <RefreshCw size={16} className={`${loading ? 'animate-spin' : ''}`} />
                            Refresh
                        </button>
                    </div>
                </div>
            </header>

            <main className="container mx-auto px-4 py-8">
                {error && (
                    <div className="mb-8 p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 flex items-start text-rose-400">
                        <div className="mr-3 mt-0.5"><AlertCircle size={18} /></div>
                        <div>
                            <h3 className="text-sm font-bold">Error Loading Data</h3>
                            <p className="text-sm opacity-80 mt-1">{error}</p>
                        </div>
                    </div>
                )}

                <div className="space-y-4 animate-in fade-in slide-in-from-bottom-4 duration-500">
                    <div className="flex flex-col md:flex-row gap-4 items-center justify-end glass-panel p-3 bg-slate-900/50 rounded-xl border border-slate-800/50">
                        <div className="flex items-center gap-2">
                            <span className="text-sm text-slate-400">Rows per page:</span>
                            <select
                                value={pageSize}
                                onChange={(e) => {
                                    setPageSize(Number(e.target.value));
                                    setPage(1);
                                }}
                                className="bg-slate-900/50 border border-slate-700/50 rounded-lg text-sm text-slate-200 py-1.5 px-3 focus:outline-none focus:ring-2 focus:ring-blue-500/50 appearance-none cursor-pointer"
                            >
                                <option value="10">10</option>
                                <option value="20">20</option>
                                <option value="50">50</option>
                                <option value="100">100</option>
                            </select>
                        </div>
                    </div>

                    <div className="glass-panel overflow-hidden bg-slate-900/50 rounded-xl border border-slate-800/50 shadow-xl">
                        <div className="overflow-x-auto">
                            <table className="w-full text-left border-collapse">
                                <thead className="bg-slate-900/80 text-xs uppercase tracking-wider text-slate-500 sticky top-0 z-10">
                                    <tr>
                                        <th className="px-4 py-4 font-semibold border-b border-slate-800 whitespace-nowrap">No (ID)</th>
                                        <th className="px-4 py-4 font-semibold border-b border-slate-800 whitespace-nowrap">Date</th>
                                        <th className="px-4 py-4 font-semibold border-b border-slate-800 whitespace-nowrap">User / App Info</th>
                                        <th className="px-4 py-4 font-semibold border-b border-slate-800 whitespace-nowrap">Prompt / Style</th>
                                        <th className="px-4 py-4 font-semibold border-b border-slate-800 whitespace-nowrap">Reference Image</th>
                                        <th className="px-4 py-4 font-semibold border-b border-slate-800 whitespace-nowrap">Output Details</th>
                                        <th className="px-4 py-4 font-semibold border-b border-slate-800 whitespace-nowrap">Duration / Status</th>
                                    </tr>
                                </thead>
                                <tbody className="text-sm divide-y divide-slate-800/50">
                                    {loading && !data ? (
                                        <tr>
                                            <td colSpan={7} className="px-4 py-12 text-center text-slate-400">
                                                <div className="flex flex-col items-center justify-center">
                                                    <RefreshCw size={24} className="animate-spin text-blue-500 mb-3" />
                                                    <p>Loading tracking data...</p>
                                                </div>
                                            </td>
                                        </tr>
                                    ) : data?.data.length === 0 ? (
                                        <tr>
                                            <td colSpan={7} className="px-4 py-12 text-center text-slate-400">
                                                <div className="flex flex-col items-center justify-center">
                                                    <Search size={32} className="text-slate-600 mb-3" />
                                                    <p className="text-lg font-medium text-slate-300">No records found</p>
                                                </div>
                                            </td>
                                        </tr>
                                    ) : (
                                        data?.data.map((item, idx) => {
                                            const imageRef = parseJsonString<any>(item.imageReference);
                                            const outputParsed = parseJsonString<any>(item.output);

                                            return (
                                                <tr key={`${item.id}-${idx}`} className="hover:bg-slate-800/20 transition-colors group">
                                                    <td className="px-4 py-3 align-top whitespace-nowrap">
                                                        <div className="font-mono text-xs text-slate-400">#{item.id}</div>
                                                    </td>
                                                    <td className="px-4 py-3 align-top whitespace-nowrap">
                                                        <div className="font-medium text-slate-200">
                                                            {new Intl.DateTimeFormat('vi-VN', { dateStyle: 'short', timeStyle: 'short' }).format(new Date(item.createdAt))}
                                                        </div>
                                                    </td>
                                                    <td className="px-4 py-3 align-top">
                                                        <div className="flex flex-col gap-1 text-xs">
                                                            <div className="text-slate-300"><span className="text-slate-500">User:</span> {item.userId || 'N/A'}</div>
                                                            <div className="text-slate-300"><span className="text-slate-500">Country:</span> {item.countryId || 'N/A'}</div>
                                                            <div className="text-slate-300"><span className="text-slate-500">Version:</span> {item.appVersion || 'N/A'}</div>
                                                        </div>
                                                    </td>
                                                    <td className="px-4 py-3 align-top min-w-[300px] max-w-[400px]">
                                                        <div className="flex flex-col gap-2 w-full">
                                                            <div>
                                                                <span className="text-[10px] font-semibold text-slate-500 uppercase">Prompt</span>
                                                                <div className="text-sm text-slate-200 bg-slate-800/50 p-2 rounded-md max-h-32 overflow-y-auto custom-scrollbar break-words whitespace-pre-wrap">{item.prompt}</div>
                                                            </div>
                                                            {item.forYouPrompt && (
                                                                <div>
                                                                    <span className="text-[10px] font-semibold text-blue-400/80 uppercase">For You Prompt</span>
                                                                    <div className="text-sm text-blue-100 bg-blue-900/20 p-2 rounded-md max-h-32 overflow-y-auto custom-scrollbar break-words whitespace-pre-wrap">{item.forYouPrompt}</div>
                                                                </div>
                                                            )}
                                                            <div className="mt-1 inline-flex items-center px-2 py-0.5 rounded text-[10px] font-medium bg-slate-800 text-slate-300 border border-slate-700 w-fit">
                                                                Style: {item.style || 'N/A'}
                                                            </div>
                                                        </div>
                                                    </td>
                                                    <td className="px-4 py-3 align-top">
                                                        {imageRef ? (
                                                            <div className="text-xs flex flex-col gap-1">
                                                                <div className="flex items-center text-emerald-400 gap-1"><ImageIcon size={12} /> <span className="font-medium">Has Reference</span></div>
                                                                <div className="text-slate-400 truncate max-w-[150px]" title={imageRef.fileName}>{imageRef.fileName || 'N/A'}</div>
                                                                <div className="text-slate-500">{imageRef.contentType || 'N/A'}</div>
                                                            </div>
                                                        ) : (
                                                            <span className="text-xs text-slate-600 italic">None</span>
                                                        )}
                                                    </td>
                                                    <td className="px-4 py-3 align-top max-w-[300px]">
                                                        {item.status === 'SUCCESS' && outputParsed ? (
                                                            <div className="flex flex-col gap-2">
                                                                {outputParsed.images && outputParsed.images.length > 0 && (
                                                                    <div className="flex gap-2 flex-wrap">
                                                                        {outputParsed.images.map((img: any, i: number) => (
                                                                            <a key={i} href={img.imageUrl} target="_blank" rel="noopener noreferrer" className="block relative w-12 h-12 rounded-md overflow-hidden border border-slate-700 hover:border-blue-500 transition-colors">
                                                                                <img src={img.imageUrl} alt="Result" className="w-full h-full object-cover" />
                                                                            </a>
                                                                        ))}
                                                                    </div>
                                                                )}
                                                                <div className="text-xs text-slate-400 flex items-center gap-2">
                                                                    <span>Provider: <span className="text-slate-300">{outputParsed.provider || 'N/A'}</span></span>
                                                                    {outputParsed.fallbackUsed && <span className="px-1.5 py-0.5 bg-amber-500/20 text-amber-400 rounded text-[10px]">Fallback</span>}
                                                                </div>
                                                            </div>
                                                        ) : item.status === 'FAIL' && outputParsed ? (
                                                            <div className="text-xs flex flex-col gap-1 text-rose-300 bg-rose-500/10 p-2 rounded-lg border border-rose-500/20">
                                                                <div className="font-semibold">{outputParsed.code || `Error ${outputParsed.status}`}</div>
                                                                <div className="break-words">{outputParsed.message || 'No error message'}</div>
                                                            </div>
                                                        ) : (
                                                            <span className="text-xs text-slate-500">No structured output</span>
                                                        )}
                                                    </td>
                                                    <td className="px-4 py-3 align-top">
                                                        <div className="flex flex-col gap-2">
                                                            <span className={`inline-flex items-center px-2 py-1 rounded-md text-xs font-medium ring-1 w-fit ${item.status === 'SUCCESS' ? 'bg-emerald-500/20 text-emerald-400 ring-emerald-500/30' : 'bg-rose-500/20 text-rose-400 ring-rose-500/30'}`}>
                                                                {item.status === 'SUCCESS' && <CheckCircle2 size={12} className="mr-1" />}
                                                                {item.status === 'FAIL' && <AlertCircle size={12} className="mr-1" />}
                                                                {item.status}
                                                            </span>
                                                            <div className="text-xs font-medium text-slate-300">
                                                                {item.durationSeconds ? `${item.durationSeconds.toFixed(2)}s` : '--'}
                                                            </div>
                                                        </div>
                                                    </td>
                                                </tr>
                                            );
                                        })
                                    )}
                                </tbody>
                            </table>
                        </div>

                        {/* Pagination Footer */}
                        {data && data.totalPages > 1 && (
                            <div className="px-4 py-3 border-t border-slate-800/50 flex flex-col sm:flex-row items-center justify-between gap-4 bg-slate-900/30">
                                <div className="text-sm text-slate-400">
                                    Showing <span className="font-medium text-white">{(data.page - 1) * data.pageSize + 1}</span> to{' '}
                                    <span className="font-medium text-white">{Math.min(data.page * data.pageSize, data.totalItems)}</span> of{' '}
                                    <span className="font-medium text-white">{data.totalItems}</span> results
                                </div>

                                <div className="flex items-center gap-1">
                                    <button
                                        onClick={() => setPage(1)} disabled={page === 1}
                                        className="flex items-center justify-center w-8 h-8 rounded-lg text-sm font-medium transition-all text-slate-400 hover:text-white hover:bg-slate-800 disabled:opacity-30 disabled:hover:bg-transparent disabled:cursor-not-allowed"
                                    >
                                        <ChevronsLeft size={16} />
                                    </button>
                                    <button
                                        onClick={() => setPage(p => p - 1)} disabled={page === 1}
                                        className="flex items-center justify-center w-8 h-8 rounded-lg text-sm font-medium transition-all text-slate-400 hover:text-white hover:bg-slate-800 disabled:opacity-30 disabled:hover:bg-transparent disabled:cursor-not-allowed"
                                    >
                                        <ChevronLeft size={16} />
                                    </button>

                                    <div className="flex items-center px-2">
                                        <span className="text-sm font-medium text-slate-300">
                                            Page {page} <span className="text-slate-500 font-normal">of {data.totalPages}</span>
                                        </span>
                                    </div>

                                    <button
                                        onClick={() => setPage(p => p + 1)} disabled={page >= data.totalPages}
                                        className="flex items-center justify-center w-8 h-8 rounded-lg text-sm font-medium transition-all text-slate-400 hover:text-white hover:bg-slate-800 disabled:opacity-30 disabled:hover:bg-transparent disabled:cursor-not-allowed"
                                    >
                                        <ChevronRight size={16} />
                                    </button>
                                    <button
                                        onClick={() => setPage(data.totalPages)} disabled={page >= data.totalPages}
                                        className="flex items-center justify-center w-8 h-8 rounded-lg text-sm font-medium transition-all text-slate-400 hover:text-white hover:bg-slate-800 disabled:opacity-30 disabled:hover:bg-transparent disabled:cursor-not-allowed"
                                    >
                                        <ChevronsRight size={16} />
                                    </button>
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            </main>
        </div>
    );
}
