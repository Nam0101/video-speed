"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  Activity,
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
    timeStyle: "medium",
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
  const [expandedRow, setExpandedRow] = useState<number | null>(null);

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
      // Device filter
      if (selectedDevice && log.deviceName !== selectedDevice) return false;
      // Event filter
      if (selectedEvent && log.eventName !== selectedEvent) return false;
      // Version filter
      if (selectedVersion && log.versionCode !== selectedVersion) return false;
      // Search query
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

    // Sort
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
    if (!confirm("Xóa tất cả logs? Hành động này không thể hoàn tác.")) return;
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
    <main className="mt-6 flex-1 pb-10">
      {/* Header */}
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <Link
            href="/tools"
            className="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-white/80 text-slate-700 shadow-sm ring-1 ring-slate-200 transition hover:bg-white"
          >
            <ArrowLeft className="h-5 w-5" />
          </Link>
          <div>
            <h1 className="text-2xl font-heading font-semibold text-slate-900">
              Live Monitor
            </h1>
            <p className="text-sm text-slate-500">
              Android event logs • Realtime tracking
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setStreaming((p) => !p)}
            className={`inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition ${streaming
                ? "bg-emerald-500 text-white shadow-lg shadow-emerald-500/25"
                : "bg-white text-slate-700 ring-1 ring-slate-200 hover:bg-slate-50"
              }`}
          >
            <span
              className={`h-2 w-2 rounded-full ${streaming ? "bg-white animate-pulse" : "bg-slate-400"
                }`}
            />
            {streaming ? "Live" : "Paused"}
          </button>
        </div>
      </header>

      {/* Stats Bar */}
      <div className="mt-6 flex flex-wrap items-center gap-4">
        <div className="flex items-center gap-6 rounded-xl bg-white/80 px-5 py-3 shadow-sm ring-1 ring-slate-200">
          <div className="text-center">
            <p className="text-2xl font-bold text-slate-900">{stats.total}</p>
            <p className="text-xs text-slate-500">Total</p>
          </div>
          <div className="h-8 w-px bg-slate-200" />
          <div className="text-center">
            <p className="text-2xl font-bold text-indigo-600">{stats.devices}</p>
            <p className="text-xs text-slate-500">Devices</p>
          </div>
          <div className="h-8 w-px bg-slate-200" />
          <div className="text-center">
            <p className="text-2xl font-bold text-amber-600">{stats.events}</p>
            <p className="text-xs text-slate-500">Events</p>
          </div>
          {hasActiveFilters && (
            <>
              <div className="h-8 w-px bg-slate-200" />
              <div className="text-center">
                <p className="text-2xl font-bold text-emerald-600">{stats.filtered}</p>
                <p className="text-xs text-slate-500">Filtered</p>
              </div>
            </>
          )}
        </div>

        <div className="flex-1" />

        <button
          onClick={fetchLogs}
          disabled={loading}
          className="inline-flex items-center gap-2 rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white shadow-sm transition hover:bg-slate-800 disabled:opacity-50"
        >
          <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </button>
        <button
          onClick={handleClear}
          disabled={loading}
          className="inline-flex items-center gap-2 rounded-lg bg-rose-500 px-4 py-2 text-sm font-medium text-white shadow-sm transition hover:bg-rose-600 disabled:opacity-50"
        >
          <Trash2 className="h-4 w-4" />
          Clear
        </button>
      </div>

      {/* Filters */}
      <div className="mt-4 rounded-xl bg-white/80 p-4 shadow-sm ring-1 ring-slate-200">
        <div className="flex flex-wrap items-center gap-3">
          {/* Search */}
          <div className="relative flex-1 min-w-[200px]">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search events, devices, params..."
              className="w-full rounded-lg border border-slate-200 bg-slate-50 py-2 pl-10 pr-4 text-sm text-slate-700 placeholder:text-slate-400 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            />
          </div>

          {/* Device Filter */}
          <div className="relative">
            <select
              value={selectedDevice}
              onChange={(e) => setSelectedDevice(e.target.value)}
              className="appearance-none rounded-lg border border-slate-200 bg-white py-2 pl-3 pr-8 text-sm text-slate-700 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            >
              <option value="">All Devices</option>
              {filterOptions.devices.map((d) => (
                <option key={d} value={d}>
                  {d}
                </option>
              ))}
            </select>
            <ChevronDown className="pointer-events-none absolute right-2 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          </div>

          {/* Event Filter */}
          <div className="relative">
            <select
              value={selectedEvent}
              onChange={(e) => setSelectedEvent(e.target.value)}
              className="appearance-none rounded-lg border border-slate-200 bg-white py-2 pl-3 pr-8 text-sm text-slate-700 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            >
              <option value="">All Events</option>
              {filterOptions.events.map((e) => (
                <option key={e} value={e}>
                  {e}
                </option>
              ))}
            </select>
            <ChevronDown className="pointer-events-none absolute right-2 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          </div>

          {/* Version Filter */}
          <div className="relative">
            <select
              value={selectedVersion}
              onChange={(e) => setSelectedVersion(e.target.value)}
              className="appearance-none rounded-lg border border-slate-200 bg-white py-2 pl-3 pr-8 text-sm text-slate-700 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            >
              <option value="">All Versions</option>
              {filterOptions.versions.map((v) => (
                <option key={v} value={v}>
                  v{v}
                </option>
              ))}
            </select>
            <ChevronDown className="pointer-events-none absolute right-2 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          </div>

          {/* Sort */}
          <div className="relative">
            <select
              value={sortOrder}
              onChange={(e) => setSortOrder(e.target.value as "newest" | "oldest")}
              className="appearance-none rounded-lg border border-slate-200 bg-white py-2 pl-3 pr-8 text-sm text-slate-700 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            >
              <option value="newest">Newest First</option>
              <option value="oldest">Oldest First</option>
            </select>
            <ChevronDown className="pointer-events-none absolute right-2 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          </div>

          {/* Clear Filters */}
          {hasActiveFilters && (
            <button
              onClick={clearFilters}
              className="inline-flex items-center gap-1 rounded-lg bg-slate-100 px-3 py-2 text-sm text-slate-600 transition hover:bg-slate-200"
            >
              <X className="h-4 w-4" />
              Clear
            </button>
          )}
        </div>
      </div>

      {/* Error Messages */}
      {(error || streamError) && (
        <div className="mt-4 rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
          <div className="flex items-center gap-2">
            <AlertCircle className="h-4 w-4" />
            <span>{error || streamError}</span>
          </div>
        </div>
      )}

      {/* Table */}
      <div className="mt-4 overflow-hidden rounded-xl bg-white shadow-sm ring-1 ring-slate-200">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-xs font-medium uppercase tracking-wider text-slate-500">
              <tr>
                <th className="px-4 py-3">Time</th>
                <th className="px-4 py-3">Event</th>
                <th className="px-4 py-3">Device</th>
                <th className="px-4 py-3">Version</th>
                <th className="px-4 py-3">Params</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading && (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-slate-500">
                    <RefreshCw className="mx-auto h-5 w-5 animate-spin" />
                    <p className="mt-2">Loading...</p>
                  </td>
                </tr>
              )}
              {!loading && filteredLogs.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-slate-500">
                    <Filter className="mx-auto h-5 w-5" />
                    <p className="mt-2">No logs found</p>
                  </td>
                </tr>
              )}
              {!loading &&
                filteredLogs.map((log, index) => (
                  <tr
                    key={`${log.timestamp}-${index}`}
                    onClick={() => setExpandedRow(expandedRow === index ? null : index)}
                    className="cursor-pointer transition hover:bg-slate-50"
                  >
                    <td className="whitespace-nowrap px-4 py-3 text-slate-600">
                      {formatTime(log.timestamp)}
                    </td>
                    <td className="px-4 py-3">
                      <span className="inline-flex items-center rounded-md bg-indigo-50 px-2 py-1 text-xs font-medium text-indigo-700 ring-1 ring-inset ring-indigo-600/20">
                        {log.eventName}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-slate-700">{log.deviceName}</td>
                    <td className="px-4 py-3">
                      <span className="inline-flex items-center rounded-md bg-slate-100 px-2 py-1 text-xs font-medium text-slate-600">
                        v{log.versionCode}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      {expandedRow === index ? (
                        <div className="space-y-1">
                          {Object.entries(log.params || {}).map(([key, value]) => (
                            <div key={key} className="flex gap-2 text-xs">
                              <span className="font-medium text-slate-700">{key}:</span>
                              <span className="text-slate-500">{String(value)}</span>
                            </div>
                          ))}
                          {Object.keys(log.params || {}).length === 0 && (
                            <span className="text-xs text-slate-400">No params</span>
                          )}
                        </div>
                      ) : (
                        <span className="text-xs text-slate-400">
                          {Object.keys(log.params || {}).length} params
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      </div>
    </main>
  );
}
