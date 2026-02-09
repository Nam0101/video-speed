"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import {
  AlertCircle,
  ArrowLeft,
  ChevronDown,
  Filter,
  Pause,
  Play,
  RefreshCw,
  Search,
  Smartphone,
  Terminal,
  Trash2,
  Wifi,
  X,
  Zap,
} from "lucide-react";
import { apiClient, Log } from "@/lib/api-client";

const formatTime = (value: string) => {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("vi-VN", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(date);
};

// Parse timber log line: "[D/Tag] message" => { priority, tag, message }
const parseTimberLog = (raw: string) => {
  const match = raw.match(/^\[([DIWEA])\/([^\]]+)\]\s*(.*)$/);
  if (!match) return { priority: "", tag: "", message: raw };
  return { priority: match[1], tag: match[2], message: match[3] };
};

const priorityColor = (p: string) => {
  switch (p) {
    case "D": return "text-cyan-400";
    case "I": return "text-green-400";
    case "W": return "text-yellow-400";
    case "E": return "text-red-400";
    case "A": return "text-red-500 font-bold";
    default: return "text-slate-400";
  }
};

const priorityBg = (p: string) => {
  switch (p) {
    case "D": return "bg-cyan-500/15 text-cyan-400";
    case "I": return "bg-green-500/15 text-green-400";
    case "W": return "bg-yellow-500/15 text-yellow-400";
    case "E": return "bg-red-500/15 text-red-400";
    case "A": return "bg-red-500/25 text-red-400";
    default: return "bg-slate-700 text-slate-400";
  }
};

// Event color mappings for visual variety
const getEventColor = (eventName: string) => {
  const colors: Record<string, { bg: string; text: string; glow: string }> = {
    splash_view: { bg: "bg-violet-500/20", text: "text-violet-400", glow: "shadow-violet-500/20" },
    home_view: { bg: "bg-blue-500/20", text: "text-blue-400", glow: "shadow-blue-500/20" },
    result_diagnose_solution_view: { bg: "bg-emerald-500/20", text: "text-emerald-400", glow: "shadow-emerald-500/20" },
    result_diagnose_preventions_view: { bg: "bg-amber-500/20", text: "text-amber-400", glow: "shadow-amber-500/20" },
    result_diagnose_reasons_view: { bg: "bg-rose-500/20", text: "text-rose-400", glow: "shadow-rose-500/20" },
    scan_view: { bg: "bg-cyan-500/20", text: "text-cyan-400", glow: "shadow-cyan-500/20" },
    timber: { bg: "bg-orange-500/20", text: "text-orange-400", glow: "shadow-orange-500/20" },
  };
  return colors[eventName] || { bg: "bg-slate-700", text: "text-slate-300", glow: "" };
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
  const [viewMode, setViewMode] = useState<"all" | "timber">("all");
  const [autoScroll, setAutoScroll] = useState(true);
  const terminalRef = useRef<HTMLDivElement>(null);

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
      if (viewMode === "timber" && log.eventName !== "timber") return false;
      if (viewMode === "all" && selectedEvent && log.eventName !== selectedEvent) return false;
      if (selectedDevice && log.deviceName !== selectedDevice) return false;
      if (viewMode === "all" && selectedVersion && log.versionCode !== selectedVersion) return false;
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
  }, [logs, searchQuery, selectedDevice, selectedEvent, selectedVersion, sortOrder, viewMode]);

  // Auto-scroll for timber terminal view
  useEffect(() => {
    if (autoScroll && viewMode === "timber" && terminalRef.current) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight;
    }
  }, [filteredLogs, autoScroll, viewMode]);

  const stats = useMemo(() => {
    return {
      total: logs.length,
      filtered: filteredLogs.length,
      devices: new Set(logs.map((l) => l.deviceName)).size,
      events: new Set(logs.map((l) => l.eventName)).size,
      timber: logs.filter((l) => l.eventName === "timber").length,
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
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950">
      {/* Background decorations */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-0 left-1/4 w-96 h-96 bg-violet-500/10 rounded-full blur-3xl" />
        <div className="absolute bottom-0 right-1/4 w-96 h-96 bg-cyan-500/10 rounded-full blur-3xl" />
      </div>

      <div className="relative z-10 max-w-7xl mx-auto p-4 md:p-6">
        {/* Header */}
        <header className="flex flex-wrap items-center justify-between gap-4 mb-6">
          <div className="flex items-center gap-4">
            <Link
              href="/tools"
              className="flex items-center justify-center w-10 h-10 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 transition-all duration-200 hover:scale-105"
            >
              <ArrowLeft className="w-5 h-5 text-slate-400" />
            </Link>
            <div>
              <h1 className="text-2xl font-bold text-white flex items-center gap-2">
                <Wifi className="w-6 h-6 text-cyan-400" />
                Live Monitor
              </h1>
              <p className="text-sm text-slate-500">Android event logs</p>
            </div>
          </div>

          {/* View mode toggle */}
          <div className="flex items-center gap-1 rounded-xl bg-white/5 border border-white/10 p-1">
            <button
              onClick={() => setViewMode("all")}
              className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium transition-all ${viewMode === "all"
                  ? "bg-white/10 text-white"
                  : "text-slate-500 hover:text-slate-300"
                }`}
            >
              <Wifi className="w-4 h-4" />
              Events
            </button>
            <button
              onClick={() => setViewMode("timber")}
              className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium transition-all ${viewMode === "timber"
                  ? "bg-gradient-to-r from-orange-500/20 to-amber-500/20 text-orange-400 border border-orange-500/20"
                  : "text-slate-500 hover:text-slate-300"
                }`}
            >
              <Terminal className="w-4 h-4" />
              Timber
              {stats.timber > 0 && (
                <span className="ml-1 px-1.5 py-0.5 rounded-full bg-orange-500/20 text-orange-400 text-xs">
                  {stats.timber}
                </span>
              )}
            </button>
          </div>

          {/* Live toggle */}
          <button
            onClick={() => setStreaming((p) => !p)}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl font-medium text-sm transition-all duration-300 ${streaming
              ? "bg-gradient-to-r from-emerald-500 to-cyan-500 text-white shadow-lg shadow-emerald-500/25"
              : "bg-white/5 text-slate-400 border border-white/10 hover:bg-white/10"
              }`}
          >
            {streaming ? (
              <>
                <span className="w-2 h-2 rounded-full bg-white animate-pulse" />
                <Pause className="w-4 h-4" />
                Live
              </>
            ) : (
              <>
                <Play className="w-4 h-4" />
                Paused
              </>
            )}
          </button>
        </header>

        {/* Stats cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
          {[
            { label: "Total", value: stats.total, color: "from-cyan-500 to-blue-500", icon: Zap },
            { label: "Timber", value: stats.timber, color: "from-orange-500 to-amber-500", icon: Terminal },
            { label: "Devices", value: stats.devices, color: "from-violet-500 to-purple-500", icon: Smartphone },
            { label: "Filtered", value: stats.filtered, color: "from-emerald-500 to-teal-500", icon: Search },
          ].map((stat) => (
            <div
              key={stat.label}
              className="relative overflow-hidden rounded-xl bg-white/5 border border-white/10 p-4 group hover:border-white/20 transition-all duration-200"
            >
              <div className={`absolute inset-0 bg-gradient-to-br ${stat.color} opacity-0 group-hover:opacity-5 transition-opacity`} />
              <div className="relative">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-medium text-slate-500 uppercase tracking-wider">{stat.label}</span>
                  <stat.icon className="w-4 h-4 text-slate-600" />
                </div>
                <p className={`text-2xl font-bold bg-gradient-to-r ${stat.color} bg-clip-text text-transparent`}>
                  {stat.value}
                </p>
              </div>
            </div>
          ))}
        </div>

        {/* Filters */}
        <div className="rounded-xl bg-white/5 border border-white/10 p-4 mb-6 backdrop-blur-sm">
          <div className="flex flex-wrap items-center gap-3">
            {/* Search */}
            <div className="relative flex-1 min-w-[200px]">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
              <input
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search events, devices..."
                className="w-full pl-10 pr-4 py-2.5 rounded-lg bg-white/5 border border-white/10 text-white placeholder:text-slate-500 focus:outline-none focus:border-cyan-500/50 focus:ring-1 focus:ring-cyan-500/25 transition-all"
              />
            </div>

            {/* Dropdowns */}
            {[
              { value: selectedDevice, setter: setSelectedDevice, options: filterOptions.devices, label: "All Devices" },
              { value: selectedEvent, setter: setSelectedEvent, options: filterOptions.events, label: "All Events" },
              { value: selectedVersion, setter: setSelectedVersion, options: filterOptions.versions, label: "All Versions", prefix: "v" },
            ].map((dropdown, i) => (
              <div key={i} className="relative">
                <select
                  value={dropdown.value}
                  onChange={(e) => dropdown.setter(e.target.value)}
                  className="appearance-none pl-3 pr-8 py-2.5 rounded-lg bg-white/5 border border-white/10 text-slate-300 text-sm focus:outline-none focus:border-cyan-500/50 cursor-pointer"
                >
                  <option value="">{dropdown.label}</option>
                  {dropdown.options.map((opt) => (
                    <option key={opt} value={opt}>{dropdown.prefix || ""}{opt}</option>
                  ))}
                </select>
                <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500 pointer-events-none" />
              </div>
            ))}

            {/* Sort */}
            <div className="relative">
              <select
                value={sortOrder}
                onChange={(e) => setSortOrder(e.target.value as "newest" | "oldest")}
                className="appearance-none pl-3 pr-8 py-2.5 rounded-lg bg-white/5 border border-white/10 text-slate-300 text-sm focus:outline-none focus:border-cyan-500/50 cursor-pointer"
              >
                <option value="newest">Newest</option>
                <option value="oldest">Oldest</option>
              </select>
              <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500 pointer-events-none" />
            </div>

            {/* Actions */}
            {hasActiveFilters && (
              <button
                onClick={clearFilters}
                className="flex items-center gap-1.5 px-3 py-2.5 rounded-lg bg-white/5 border border-white/10 text-slate-400 text-sm hover:bg-white/10 transition-all"
              >
                <X className="w-4 h-4" />
                Clear
              </button>
            )}

            <button
              onClick={fetchLogs}
              disabled={loading}
              className="flex items-center gap-1.5 px-4 py-2.5 rounded-lg bg-gradient-to-r from-cyan-500 to-blue-500 text-white text-sm font-medium shadow-lg shadow-cyan-500/25 hover:shadow-cyan-500/40 transition-all disabled:opacity-50"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
              Refresh
            </button>

            <button
              onClick={handleClear}
              disabled={loading}
              className="flex items-center gap-1.5 px-4 py-2.5 rounded-lg bg-gradient-to-r from-rose-500 to-pink-500 text-white text-sm font-medium shadow-lg shadow-rose-500/25 hover:shadow-rose-500/40 transition-all disabled:opacity-50"
            >
              <Trash2 className="w-4 h-4" />
              Clear
            </button>
          </div>
        </div>

        {/* Error */}
        {(error || streamError) && (
          <div className="mb-6 p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400 text-sm flex items-center gap-2">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            {error || streamError}
          </div>
        )}

        {/* Logs */}
        <div className="space-y-3">
          {loading && (
            <div className="flex flex-col items-center justify-center py-12 text-slate-500">
              <RefreshCw className="w-8 h-8 animate-spin mb-3" />
              <p>Loading logs...</p>
            </div>
          )}

          {!loading && filteredLogs.length === 0 && (
            <div className="flex flex-col items-center justify-center py-12 text-slate-500">
              <Filter className="w-8 h-8 mb-3 opacity-50" />
              <p>No logs found</p>
            </div>
          )}

          {/* Timber terminal view */}
          {!loading && viewMode === "timber" && filteredLogs.length > 0 && (
            <div className="rounded-xl bg-black/60 border border-white/10 overflow-hidden">
              {/* Terminal header */}
              <div className="flex items-center justify-between px-4 py-2.5 bg-white/5 border-b border-white/10">
                <div className="flex items-center gap-2">
                  <div className="flex gap-1.5">
                    <span className="w-3 h-3 rounded-full bg-red-500/80" />
                    <span className="w-3 h-3 rounded-full bg-yellow-500/80" />
                    <span className="w-3 h-3 rounded-full bg-green-500/80" />
                  </div>
                  <span className="text-xs text-slate-500 font-mono ml-2">Timber Remote Debug</span>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setAutoScroll((p) => !p)}
                    className={`text-xs px-2 py-1 rounded font-mono transition-all ${autoScroll
                        ? "bg-green-500/15 text-green-400"
                        : "bg-white/5 text-slate-500"
                      }`}
                  >
                    auto-scroll {autoScroll ? "on" : "off"}
                  </button>
                  <span className="text-xs text-slate-600 font-mono">{filteredLogs.length} lines</span>
                </div>
              </div>
              {/* Terminal body */}
              <div
                ref={terminalRef}
                className="max-h-[70vh] overflow-y-auto p-4 font-mono text-sm leading-relaxed scroll-smooth"
              >
                {filteredLogs.map((log, index) => {
                  const raw = log.params?.message || JSON.stringify(log.params);
                  const { priority, tag, message } = parseTimberLog(raw);
                  return (
                    <div
                      key={`${log.timestamp}-${index}`}
                      className="flex gap-0 hover:bg-white/[0.03] py-0.5 px-1 rounded group"
                    >
                      <span className="text-slate-600 select-none shrink-0 w-[70px]">
                        {formatTime(log.timestamp)}
                      </span>
                      <span className={`shrink-0 w-5 text-center font-bold ${priorityColor(priority)}`}>
                        {priority || "?"}
                      </span>
                      <span className="text-violet-400 shrink-0 mx-1">
                        {tag ? `${tag}:` : ""}
                      </span>
                      <span className="text-slate-300 break-all whitespace-pre-wrap">{message}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Card view for events */}
          {!loading && viewMode === "all" &&
            filteredLogs.map((log, index) => {
              const eventColor = getEventColor(log.eventName);
              const hasParams = log.params && Object.keys(log.params).length > 0;
              const isTimber = log.eventName === "timber";

              return (
                <div
                  key={`${log.timestamp}-${index}`}
                  className={`group relative overflow-hidden rounded-xl bg-white/[0.02] border border-white/5 hover:border-white/10 hover:bg-white/[0.04] transition-all duration-200 ${eventColor.glow ? `hover:shadow-lg ${eventColor.glow}` : ""}`}
                >
                  {/* Gradient accent line */}
                  <div className={`absolute left-0 top-0 bottom-0 w-1 ${eventColor.bg}`} />

                  <div className="p-4 pl-5">
                    {/* Top row */}
                    <div className="flex flex-wrap items-center gap-3">
                      <span className="font-mono text-sm text-slate-500">{formatTime(log.timestamp)}</span>
                      <span className={`px-2.5 py-1 rounded-md text-xs font-medium ${eventColor.bg} ${eventColor.text}`}>
                        {log.eventName}
                      </span>
                      {isTimber && (() => {
                        const { priority } = parseTimberLog(log.params?.message || "");
                        return priority ? (
                          <span className={`px-2 py-0.5 rounded text-xs font-mono font-bold ${priorityBg(priority)}`}>
                            {priority}
                          </span>
                        ) : null;
                      })()}
                      <span className="flex items-center gap-1.5 text-sm text-slate-400">
                        <Smartphone className="w-3.5 h-3.5" />
                        {log.deviceName}
                      </span>
                      {log.versionCode && (
                        <span className="px-2 py-0.5 rounded bg-white/5 text-xs text-slate-500">
                          v{log.versionCode}
                        </span>
                      )}
                    </div>

                    {/* Timber message inline */}
                    {isTimber && log.params?.message && (() => {
                      const { priority, tag, message } = parseTimberLog(log.params.message);
                      return (
                        <div className="mt-2 p-2.5 rounded-lg bg-black/30 border border-white/5 font-mono text-sm">
                          <span className={`font-bold ${priorityColor(priority)}`}>{priority}</span>
                          <span className="text-violet-400">/{tag}</span>
                          <span className="text-slate-500 mx-1.5">|</span>
                          <span className="text-slate-300 break-all whitespace-pre-wrap">{message}</span>
                        </div>
                      );
                    })()}

                    {/* Params (non-timber) */}
                    {hasParams && !isTimber && (
                      <div className="mt-3">
                        <pre className="p-3 rounded-lg bg-black/20 border border-white/5 text-xs font-mono text-emerald-400 overflow-x-auto">
                          {JSON.stringify(log.params, null, 2)}
                        </pre>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
        </div>
      </div>
    </div>
  );
}
