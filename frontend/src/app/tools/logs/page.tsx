"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  AlertCircle,
  ArrowLeft,
  ChevronDown,
  Filter,
  RefreshCw,
  Search,
  Trash2,
  X,
} from "lucide-react";
import { apiClient, Log } from "@/lib/api-client";

const formatDateTime = (value: string) => {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("vi-VN", {
    dateStyle: "short",
    timeStyle: "medium",
  }).format(date);
};

const formatTime = (value: string) => {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("vi-VN", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(date);
};

export default function LogsPage() {
  const [logs, setLogs] = useState<Log[]>([]);
  const [loading, setLoading] = useState(true);
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState("");
  const [streamError, setStreamError] = useState("");

  // Filters
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedDevice, setSelectedDevice] = useState<string>("");
  const [selectedEvent, setSelectedEvent] = useState<string>("");
  const [selectedVersion, setSelectedVersion] = useState<string>("");
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
      } catch {
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

  // Extract unique values for dropdowns
  const filterOptions = useMemo(() => {
    const devices = [...new Set(logs.map((l) => l.deviceName))].filter(Boolean).sort();
    const events = [...new Set(logs.map((l) => l.eventName))].filter(Boolean).sort();
    const versions = [...new Set(logs.map((l) => l.versionCode))].filter(Boolean).sort();
    return { devices, events, versions };
  }, [logs]);

  const filteredLogs = useMemo(() => {
    let filtered = logs.filter((log) => {
      if (selectedDevice && log.deviceName !== selectedDevice) return false;
      if (selectedEvent && log.eventName !== selectedEvent) return false;
      if (selectedVersion && log.versionCode !== selectedVersion) return false;
      if (searchQuery) {
        const query = searchQuery.toLowerCase();
        const searchable = [
          log.eventName,
          log.deviceName,
          log.versionCode,
          JSON.stringify(log.params),
        ]
          .join(" ")
          .toLowerCase();
        if (!searchable.includes(query)) return false;
      }
      return true;
    });

    filtered.sort((a, b) => {
      const aTime = new Date(a.timestamp).getTime();
      const bTime = new Date(b.timestamp).getTime();
      if (Number.isNaN(aTime) || Number.isNaN(bTime)) return 0;
      return sortOrder === "newest" ? bTime - aTime : aTime - bTime;
    });

    return filtered;
  }, [logs, searchQuery, selectedDevice, selectedEvent, selectedVersion, sortOrder]);

  const stats = useMemo(() => {
    return {
      total: logs.length,
      filtered: filteredLogs.length,
      devices: new Set(logs.map((l) => l.deviceName)).size,
      events: new Set(logs.map((l) => l.eventName)).size,
    };
  }, [logs, filteredLogs]);

  const handleClear = async () => {
    if (!confirm("Xóa tất cả logs?")) return;
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

  const clearFilters = () => {
    setSearchQuery("");
    setSelectedDevice("");
    setSelectedEvent("");
    setSelectedVersion("");
  };

  const hasActiveFilters = searchQuery || selectedDevice || selectedEvent || selectedVersion;

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100 p-4 md:p-6">
      {/* Header */}
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <Link
            href="/tools"
            className="inline-flex h-10 w-10 items-center justify-center rounded-lg bg-slate-800 text-slate-300 ring-1 ring-slate-700 transition hover:bg-slate-700"
          >
            <ArrowLeft className="h-5 w-5" />
          </Link>
          <div>
            <h1 className="text-2xl font-bold text-white">Live Monitor</h1>
            <p className="text-sm text-slate-400">Android event logs</p>
          </div>
        </div>
        <button
          onClick={() => setStreaming((p) => !p)}
          className={`inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition ${streaming
              ? "bg-emerald-500 text-white shadow-lg shadow-emerald-500/30"
              : "bg-slate-800 text-slate-300 ring-1 ring-slate-700 hover:bg-slate-700"
            }`}
        >
          <span
            className={`h-2 w-2 rounded-full ${streaming ? "bg-white animate-pulse" : "bg-slate-500"
              }`}
          />
          {streaming ? "Live" : "Paused"}
        </button>
      </header>

      {/* Stats */}
      <div className="mt-6 flex flex-wrap items-center gap-4">
        <div className="flex items-center gap-4 rounded-lg bg-slate-900 px-4 py-3 ring-1 ring-slate-800">
          <div className="text-center px-2">
            <p className="text-2xl font-bold text-cyan-400">{stats.total}</p>
            <p className="text-xs text-slate-500">Total</p>
          </div>
          <div className="h-8 w-px bg-slate-700" />
          <div className="text-center px-2">
            <p className="text-2xl font-bold text-violet-400">{stats.devices}</p>
            <p className="text-xs text-slate-500">Devices</p>
          </div>
          <div className="h-8 w-px bg-slate-700" />
          <div className="text-center px-2">
            <p className="text-2xl font-bold text-amber-400">{stats.events}</p>
            <p className="text-xs text-slate-500">Events</p>
          </div>
          {hasActiveFilters && (
            <>
              <div className="h-8 w-px bg-slate-700" />
              <div className="text-center px-2">
                <p className="text-2xl font-bold text-emerald-400">{stats.filtered}</p>
                <p className="text-xs text-slate-500">Filtered</p>
              </div>
            </>
          )}
        </div>
        <div className="flex-1" />
        <button
          onClick={fetchLogs}
          disabled={loading}
          className="inline-flex items-center gap-2 rounded-lg bg-cyan-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-cyan-500 disabled:opacity-50"
        >
          <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </button>
        <button
          onClick={handleClear}
          disabled={loading}
          className="inline-flex items-center gap-2 rounded-lg bg-rose-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-rose-500 disabled:opacity-50"
        >
          <Trash2 className="h-4 w-4" />
          Clear
        </button>
      </div>

      {/* Filters */}
      <div className="mt-4 rounded-lg bg-slate-900 p-4 ring-1 ring-slate-800">
        <div className="flex flex-wrap items-center gap-3">
          <div className="relative flex-1 min-w-[200px]">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
            <input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search..."
              className="w-full rounded-lg border border-slate-700 bg-slate-800 py-2 pl-10 pr-4 text-sm text-slate-200 placeholder:text-slate-500 focus:border-cyan-500 focus:outline-none focus:ring-1 focus:ring-cyan-500"
            />
          </div>

          <div className="relative">
            <select
              value={selectedDevice}
              onChange={(e) => setSelectedDevice(e.target.value)}
              className="appearance-none rounded-lg border border-slate-700 bg-slate-800 py-2 pl-3 pr-8 text-sm text-slate-200 focus:border-cyan-500 focus:outline-none"
            >
              <option value="">All Devices</option>
              {filterOptions.devices.map((d) => (
                <option key={d} value={d}>{d}</option>
              ))}
            </select>
            <ChevronDown className="pointer-events-none absolute right-2 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
          </div>

          <div className="relative">
            <select
              value={selectedEvent}
              onChange={(e) => setSelectedEvent(e.target.value)}
              className="appearance-none rounded-lg border border-slate-700 bg-slate-800 py-2 pl-3 pr-8 text-sm text-slate-200 focus:border-cyan-500 focus:outline-none"
            >
              <option value="">All Events</option>
              {filterOptions.events.map((e) => (
                <option key={e} value={e}>{e}</option>
              ))}
            </select>
            <ChevronDown className="pointer-events-none absolute right-2 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
          </div>

          <div className="relative">
            <select
              value={selectedVersion}
              onChange={(e) => setSelectedVersion(e.target.value)}
              className="appearance-none rounded-lg border border-slate-700 bg-slate-800 py-2 pl-3 pr-8 text-sm text-slate-200 focus:border-cyan-500 focus:outline-none"
            >
              <option value="">All Versions</option>
              {filterOptions.versions.map((v) => (
                <option key={v} value={v}>v{v}</option>
              ))}
            </select>
            <ChevronDown className="pointer-events-none absolute right-2 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
          </div>

          <div className="relative">
            <select
              value={sortOrder}
              onChange={(e) => setSortOrder(e.target.value as "newest" | "oldest")}
              className="appearance-none rounded-lg border border-slate-700 bg-slate-800 py-2 pl-3 pr-8 text-sm text-slate-200 focus:border-cyan-500 focus:outline-none"
            >
              <option value="newest">Newest</option>
              <option value="oldest">Oldest</option>
            </select>
            <ChevronDown className="pointer-events-none absolute right-2 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
          </div>

          {hasActiveFilters && (
            <button
              onClick={clearFilters}
              className="inline-flex items-center gap-1 rounded-lg bg-slate-700 px-3 py-2 text-sm text-slate-300 transition hover:bg-slate-600"
            >
              <X className="h-4 w-4" />
              Clear
            </button>
          )}
        </div>
      </div>

      {/* Error */}
      {(error || streamError) && (
        <div className="mt-4 rounded-lg border border-rose-800 bg-rose-950 px-4 py-3 text-sm text-rose-300">
          <div className="flex items-center gap-2">
            <AlertCircle className="h-4 w-4" />
            <span>{error || streamError}</span>
          </div>
        </div>
      )}

      {/* Logs List */}
      <div className="mt-4 space-y-2">
        {loading && (
          <div className="rounded-lg bg-slate-900 p-6 text-center text-slate-400 ring-1 ring-slate-800">
            <RefreshCw className="mx-auto h-5 w-5 animate-spin" />
            <p className="mt-2">Loading...</p>
          </div>
        )}

        {!loading && filteredLogs.length === 0 && (
          <div className="rounded-lg bg-slate-900 p-6 text-center text-slate-500 ring-1 ring-slate-800">
            <Filter className="mx-auto h-5 w-5" />
            <p className="mt-2">No logs found</p>
          </div>
        )}

        {!loading &&
          filteredLogs.map((log, index) => (
            <div
              key={`${log.timestamp}-${index}`}
              className="rounded-lg bg-slate-900 p-4 ring-1 ring-slate-800 hover:ring-slate-700 transition"
            >
              {/* Top row: time, event, device, version */}
              <div className="flex flex-wrap items-center gap-3 text-sm">
                <span className="font-mono text-slate-500">{formatTime(log.timestamp)}</span>
                <span className="rounded bg-cyan-900/50 px-2 py-0.5 text-xs font-medium text-cyan-300 ring-1 ring-cyan-800">
                  {log.eventName}
                </span>
                <span className="text-slate-400">{log.deviceName}</span>
                <span className="rounded bg-slate-800 px-2 py-0.5 text-xs text-slate-400">
                  v{log.versionCode}
                </span>
              </div>

              {/* Params as formatted JSON */}
              <div className="mt-3">
                <pre className="overflow-x-auto rounded-md bg-slate-950 p-3 text-xs font-mono text-emerald-400 ring-1 ring-slate-800">
                  {Object.keys(log.params || {}).length > 0
                    ? JSON.stringify(log.params, null, 2)
                    : "{ }"}
                </pre>
              </div>
            </div>
          ))}
      </div>
    </main>
  );
}
