"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  Activity,
  AlertCircle,
  ArrowLeft,
  RefreshCw,
  Trash2,
} from "lucide-react";
import { apiClient, Log } from "@/lib/api-client";

const formatDateTime = (value: string) => {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("vi-VN", {
    dateStyle: "medium",
    timeStyle: "medium",
  }).format(date);
};

export default function LogsPage() {
  const [logs, setLogs] = useState<Log[]>([]);
  const [loading, setLoading] = useState(true);
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState("");
  const [streamError, setStreamError] = useState("");
  const [query, setQuery] = useState("");
  const [sortOrder, setSortOrder] = useState<"newest" | "oldest">("newest");

  const fetchLogs = async () => {
    setLoading(true);
    setError("");
    try {
      const response = await apiClient.getLogs();
      setLogs(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không thể tải logs");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLogs();
  }, []);

  useEffect(() => {
    if (!streaming) return;
    setStreamError("");
    const source = new EventSource(apiClient.getLogStreamURL());
    source.onmessage = (event) => {
      if (!event.data) return;
      try {
        const data = JSON.parse(event.data) as Log;
        setLogs((prev) => [...prev, data].slice(-500));
      } catch (err) {
        setStreamError("Không thể parse dữ liệu realtime.");
      }
    };
    source.onerror = () => {
      setStreamError("Kết nối realtime bị gián đoạn.");
      source.close();
      setStreaming(false);
    };
    return () => {
      source.close();
    };
  }, [streaming]);

  const filteredLogs = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    const filtered = logs.filter((log) => {
      if (!normalized) return true;
      const payload = [log.eventName, log.deviceName, log.versionCode]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      const params = JSON.stringify(log.params || {}).toLowerCase();
      return payload.includes(normalized) || params.includes(normalized);
    });
    const sorted = [...filtered].sort((a, b) => {
      const aTime = new Date(a.timestamp).getTime();
      const bTime = new Date(b.timestamp).getTime();
      if (Number.isNaN(aTime) || Number.isNaN(bTime)) return 0;
      return sortOrder === "newest" ? bTime - aTime : aTime - bTime;
    });
    return sorted;
  }, [logs, query, sortOrder]);

  const stats = useMemo(() => {
    const total = logs.length;
    const devices = new Set(logs.map((item) => item.deviceName)).size;
    const versions = new Set(logs.map((item) => item.versionCode)).size;
    return { total, devices, versions };
  }, [logs]);

  const handleClear = async () => {
    try {
      setLoading(true);
      await apiClient.clearLogs();
      setLogs([]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không thể xoá logs");
    } finally {
      setLoading(false);
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
              Live Monitor
            </p>
            <h1 className="text-3xl font-heading font-semibold text-slate-900 md:text-4xl">
              Android Logs
            </h1>
            <p className="mt-1 text-sm text-slate-600">
              Theo dõi event realtime, lọc nhanh theo device và phiên bản.
            </p>
          </div>
        </div>
        <span className="rounded-full bg-white/70 px-4 py-2 text-xs font-semibold text-slate-600 shadow-sm ring-1 ring-slate-200">
          Endpoint: /api/android-log
        </span>
      </header>

      <section className="mt-8 grid gap-4 md:grid-cols-3">
        {[
          { label: "Tổng logs", value: stats.total },
          { label: "Thiết bị", value: stats.devices },
          { label: "Phiên bản", value: stats.versions },
        ].map((item) => (
          <div
            key={item.label}
            className="rounded-2xl bg-white/80 p-4 shadow-sm ring-1 ring-slate-200"
          >
            <p className="text-xs font-semibold uppercase tracking-widest text-slate-500">
              {item.label}
            </p>
            <p className="mt-2 text-3xl font-semibold text-slate-900">
              {item.value}
            </p>
          </div>
        ))}
      </section>

      <section className="mt-6 rounded-3xl bg-white/80 p-4 shadow-sm ring-1 ring-slate-200">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex flex-1 items-center gap-2 rounded-2xl bg-slate-100/80 px-3 py-2">
            <Activity className="h-4 w-4 text-slate-500" />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Tìm event, device, params..."
              className="w-full bg-transparent text-sm text-slate-700 placeholder:text-slate-500 focus:outline-none"
            />
          </div>
          <select
            value={sortOrder}
            onChange={(event) =>
              setSortOrder(event.target.value as "newest" | "oldest")
            }
            className="rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700"
          >
            <option value="newest">Mới nhất</option>
            <option value="oldest">Cũ nhất</option>
          </select>
          <button
            onClick={fetchLogs}
            disabled={loading}
            className="inline-flex items-center gap-2 rounded-full bg-slate-900 px-4 py-2 text-xs font-semibold text-white shadow-sm transition hover:-translate-y-0.5 disabled:opacity-60"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
            Làm mới
          </button>
          <button
            onClick={() => setStreaming((prev) => !prev)}
            className={`inline-flex items-center gap-2 rounded-full px-4 py-2 text-xs font-semibold shadow-sm transition hover:-translate-y-0.5 ${
              streaming
                ? "bg-emerald-500 text-white"
                : "bg-white text-slate-700 ring-1 ring-slate-200"
            }`}
          >
            <span className="h-2 w-2 rounded-full bg-white/70 motion-safe:animate-pulse-soft" />
            {streaming ? "Đang realtime" : "Bật realtime"}
          </button>
          <button
            onClick={handleClear}
            disabled={loading}
            className="inline-flex items-center gap-2 rounded-full bg-rose-500 px-4 py-2 text-xs font-semibold text-white shadow-sm transition hover:-translate-y-0.5 disabled:opacity-60"
          >
            <Trash2 className="h-4 w-4" />
            Xoá logs
          </button>
        </div>
      </section>

      {(error || streamError) && (
        <div className="mt-4 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
          <div className="flex items-center gap-3">
            <AlertCircle className="h-4 w-4" />
            <span>{error || streamError}</span>
          </div>
        </div>
      )}

      <section className="mt-6 space-y-4">
        {loading && (
          <div className="rounded-2xl bg-white/80 p-6 text-sm text-slate-600 shadow-sm ring-1 ring-slate-200">
            Đang tải logs...
          </div>
        )}
        {!loading && filteredLogs.length === 0 && (
          <div className="rounded-2xl bg-white/80 p-6 text-sm text-slate-600 shadow-sm ring-1 ring-slate-200">
            Không có logs phù hợp.
          </div>
        )}
        {!loading &&
          filteredLogs.map((log, index) => (
            <div
              key={`${log.timestamp}-${log.deviceName}-${index}`}
              style={{ animationDelay: `${Math.min(index, 10) * 0.05}s` }}
              className="rounded-3xl bg-white/80 p-5 shadow-sm ring-1 ring-slate-200 motion-safe:animate-fade-up"
            >
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-widest text-slate-400">
                    {formatDateTime(log.timestamp)}
                  </p>
                  <h3 className="mt-1 text-lg font-semibold text-slate-900">
                    {log.eventName}
                  </h3>
                  <p className="mt-1 text-xs text-slate-500">
                    Device: {log.deviceName} · Version: {log.versionCode || "n/a"}
                  </p>
                </div>
                <span className="rounded-full bg-slate-900 px-3 py-1 text-xs font-semibold text-white">
                  {log.params?.action || "event"}
                </span>
              </div>

              <div className="mt-4 grid gap-3 md:grid-cols-2">
                {Object.entries(log.params || {}).length === 0 ? (
                  <div className="rounded-2xl bg-slate-50 px-4 py-3 text-xs text-slate-500">
                    Không có params bổ sung.
                  </div>
                ) : (
                  Object.entries(log.params || {}).map(([key, value]) => (
                    <div
                      key={key}
                      className="rounded-2xl bg-slate-50 px-4 py-3 text-xs text-slate-600"
                    >
                      <span className="font-semibold text-slate-700">{key}:</span>{" "}
                      {String(value)}
                    </div>
                  ))
                )}
              </div>
            </div>
          ))}
      </section>
    </main>
  );
}
