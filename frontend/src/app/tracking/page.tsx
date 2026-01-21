'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import {
  ArrowLeft,
  BarChart3,
  Clock3,
  Download,
  Globe2,
  HeartPulse,
  RefreshCw,
  Search,
  Smartphone,
  ChevronDown,
} from 'lucide-react';
import { apiClient, TrackingItem, TrackingResponse } from '@/lib/api-client';

const formatDateTime = (value: string) => {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat('vi-VN', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date);
};

const getDateParts = (value: string) => {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return { time: value, date: '' };
  }
  return {
    time: new Intl.DateTimeFormat('vi-VN', {
      hour: '2-digit',
      minute: '2-digit',
    }).format(date),
    date: new Intl.DateTimeFormat('vi-VN', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    }).format(date),
  };
};

const formatResponseTime = (value: number | null) => {
  if (value === null || Number.isNaN(value)) return '--';
  return `${value.toFixed(2)}s`;
};

const formatDayLabel = (value: string) => {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat('vi-VN', {
    month: 'short',
    day: 'numeric',
  }).format(date);
};

const getHealthLabel = (value: boolean | null) => {
  if (value === true) return { label: 'Healthy', tone: 'bg-emerald-500/20 text-emerald-400' };
  if (value === false) return { label: 'Issue', tone: 'bg-rose-500/20 text-rose-400' };
  return { label: 'Unknown', tone: 'bg-slate-700 text-slate-400' };
};

const getPlatformLabel = (deviceId: string | null | undefined) => {
  if (!deviceId) return { label: 'Unknown', tone: 'bg-slate-700 text-slate-400' };
  const normalized = deviceId.toUpperCase();
  if (normalized.startsWith('AID')) {
    return { label: 'Android', tone: 'bg-emerald-500/20 text-emerald-400' };
  }
  if (normalized.startsWith('DID') || normalized.startsWith('IOS')) {
    return { label: 'iOS', tone: 'bg-indigo-500/20 text-indigo-400' };
  }
  return { label: 'Unknown', tone: 'bg-slate-700 text-slate-400' };
};

const formatCsvValue = (value: string | number | boolean | null | undefined) => {
  if (value === null || value === undefined) return '';
  const raw = String(value);
  const escaped = raw.replace(/"/g, '""');
  if (/[",\n]/.test(escaped)) return `"${escaped}"`;
  return escaped;
};

export default function TrackingPage() {
  const [records, setRecords] = useState<TrackingItem[]>([]);
  const [pagination, setPagination] = useState<TrackingResponse['pagination'] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [query, setQuery] = useState('');
  const [functionFilter, setFunctionFilter] = useState('all');
  const [countryFilter, setCountryFilter] = useState('all');
  const [appVersionFilter, setAppVersionFilter] = useState('all');

  const fetchTracking = async () => {
    setLoading(true);
    setError('');
    try {
      const response = await apiClient.getTracking();
      setRecords(response.data);
      setPagination(response.pagination);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể tải dữ liệu');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTracking();
  }, []);

  const versionedRecords = useMemo(
    () => records.filter((item) => item.app_version && item.app_version !== 'unknown'),
    [records]
  );

  const functions = useMemo(() => {
    return Array.from(new Set(versionedRecords.map((item) => item.function).filter(Boolean))).sort();
  }, [versionedRecords]);

  const countries = useMemo(() => {
    return Array.from(new Set(versionedRecords.map((item) => item.country_code || 'unknown'))).sort();
  }, [versionedRecords]);

  const appVersions = useMemo(() => {
    return Array.from(new Set(versionedRecords.map((item) => item.app_version || 'unknown'))).sort();
  }, [versionedRecords]);

  const functionCounts = useMemo(() => {
    const map = new Map<string, number>();
    versionedRecords.forEach((item) => {
      map.set(item.function, (map.get(item.function) ?? 0) + 1);
    });
    return map;
  }, [versionedRecords]);

  const filteredRecords = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    return versionedRecords.filter((item) => {
      if (functionFilter !== 'all' && item.function !== functionFilter) return false;
      if (countryFilter !== 'all' && item.country_code !== countryFilter) return false;
      if (appVersionFilter !== 'all' && item.app_version !== appVersionFilter) return false;
      if (!normalized) return true;
      const haystack = [item.device_id, item.result, item.app_version, item.country_code]
        .filter(Boolean)
        .join(' ')
        .toLowerCase();
      return haystack.includes(normalized);
    });
  }, [versionedRecords, query, functionFilter, countryFilter, appVersionFilter]);

  const stats = useMemo(() => {
    const total = versionedRecords.length;
    const deviceCount = new Set(versionedRecords.map((item) => item.device_id).filter(Boolean)).size;
    const responseTimes = versionedRecords
      .map((item) => item.response_time_seconds)
      .filter((value): value is number => value !== null && !Number.isNaN(value));
    const avgResponse = responseTimes.length
      ? responseTimes.reduce((sum, value) => sum + value, 0) / responseTimes.length
      : null;
    const healthyCount = versionedRecords.filter((item) => item.is_plant_healthy === true).length;
    const issueCount = versionedRecords.filter((item) => item.is_plant_healthy === false).length;
    return { total, deviceCount, avgResponse, healthyCount, issueCount };
  }, [versionedRecords]);

  const hasActiveFilters =
    query.trim().length > 0 || functionFilter !== 'all' || countryFilter !== 'all' || appVersionFilter !== 'all';

  const handleExportCsv = () => {
    const headers = ['date', 'function', 'result', 'is_plant_healthy', 'response_time_seconds', 'app_version', 'platform', 'device_id', 'country_code', 'image_url'];
    const rows = filteredRecords.map((item) => {
      const platform = getPlatformLabel(item.device_id).label;
      return [item.date, item.function, item.result, item.is_plant_healthy, item.response_time_seconds, item.app_version, platform, item.device_id, item.country_code, item.image_url].map(formatCsvValue);
    });
    const csvContent = ['\ufeff' + headers.join(','), ...rows.map((row) => row.join(','))].join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `tracking-${new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-')}.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-4 md:p-6">
      {/* Background effects */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden">
        <div className="absolute -top-32 right-[-10%] h-[420px] w-[420px] rounded-full bg-[radial-gradient(circle_at_center,rgba(59,130,246,0.2),transparent_65%)] blur-3xl animate-float" />
        <div className="absolute -bottom-40 left-[-10%] h-[420px] w-[420px] rounded-full bg-[radial-gradient(circle_at_center,rgba(249,115,22,0.15),transparent_60%)] blur-3xl animate-float" style={{ animationDelay: '2s' }} />
      </div>

      <div className="relative z-10 mx-auto max-w-7xl">
        {/* Header */}
        <header className="flex flex-wrap items-center justify-between gap-4 animate-fade-in">
          <div className="flex items-center gap-4">
            <Link
              href="/"
              className="inline-flex h-10 w-10 items-center justify-center rounded-lg bg-slate-800 text-slate-300 ring-1 ring-slate-700 transition hover:bg-slate-700 cursor-pointer"
            >
              <ArrowLeft className="h-5 w-5" />
            </Link>
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.35em] text-slate-500">Analytics</p>
              <h1 className="text-2xl font-bold text-white md:text-3xl">Tracking Dashboard</h1>
              <p className="text-sm text-slate-500">Plant Identify & Diagnose logs</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Link href="/tools" className="btn-secondary rounded-lg cursor-pointer">Tools</Link>
            <button onClick={fetchTracking} disabled={loading} className="btn-primary rounded-lg cursor-pointer">
              <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
              Refresh
            </button>
          </div>
        </header>

        {/* Stats */}
        <section className="mt-6 grid gap-4 md:grid-cols-2 lg:grid-cols-4 animate-fade-up">
          {[
            { label: 'Total Requests', value: stats.total, sub: `${filteredRecords.length} filtered`, icon: BarChart3, color: 'text-cyan-400' },
            { label: 'Devices', value: stats.deviceCount, sub: 'Unique IDs', icon: Smartphone, color: 'text-violet-400' },
            { label: 'Avg Response', value: stats.avgResponse ? `${stats.avgResponse.toFixed(2)}s` : '--', sub: 'Response time', icon: Clock3, color: 'text-amber-400' },
            { label: 'Health', value: `${stats.healthyCount}/${stats.issueCount}`, sub: 'Healthy / Issue', icon: HeartPulse, color: 'text-emerald-400' },
          ].map((stat) => (
            <div key={stat.label} className="card">
              <div className="flex items-center justify-between">
                <p className="text-xs font-semibold uppercase tracking-widest text-slate-500">{stat.label}</p>
                <stat.icon className={`h-4 w-4 ${stat.color}`} />
              </div>
              <p className="mt-3 text-3xl font-bold text-white">{stat.value}</p>
              <p className="mt-1 text-xs text-slate-500">{stat.sub}</p>
            </div>
          ))}
        </section>

        {/* Filters */}
        <section className="mt-6 rounded-xl bg-slate-900 p-4 ring-1 ring-slate-800 animate-fade-up">
          <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-widest text-slate-500">
              Filters
              {hasActiveFilters && <span className="rounded-full bg-blue-500 px-2 py-0.5 text-[10px] text-white">Active</span>}
            </div>
            <div className="flex items-center gap-2 text-xs text-slate-500">
              <Globe2 className="h-4 w-4" />
              {pagination ? `${pagination.total} records` : 'Loading...'}
            </div>
          </div>
          <div className="flex flex-wrap items-end gap-3">
            {/* Search */}
            <div className="flex-1 min-w-[200px]">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
                <input
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Search device, result..."
                  className="input pl-10"
                />
              </div>
            </div>
            {/* Function */}
            <div className="relative">
              <select value={functionFilter} onChange={(e) => setFunctionFilter(e.target.value)} className="input appearance-none pr-8">
                <option value="all">All Functions</option>
                {functions.map((f) => <option key={f} value={f}>{f} ({functionCounts.get(f) ?? 0})</option>)}
              </select>
              <ChevronDown className="pointer-events-none absolute right-2 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
            </div>
            {/* Version */}
            <div className="relative">
              <select value={appVersionFilter} onChange={(e) => setAppVersionFilter(e.target.value)} className="input appearance-none pr-8">
                <option value="all">All Versions</option>
                {appVersions.map((v) => <option key={v} value={v}>{v}</option>)}
              </select>
              <ChevronDown className="pointer-events-none absolute right-2 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
            </div>
            {/* Country */}
            <div className="relative">
              <select value={countryFilter} onChange={(e) => setCountryFilter(e.target.value)} className="input appearance-none pr-8">
                <option value="all">All Countries</option>
                {countries.map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
              <ChevronDown className="pointer-events-none absolute right-2 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
            </div>
            {/* Reset */}
            <button
              onClick={() => { setQuery(''); setFunctionFilter('all'); setCountryFilter('all'); setAppVersionFilter('all'); }}
              className="btn-secondary"
            >
              Reset
            </button>
            {/* Export */}
            <button onClick={handleExportCsv} disabled={filteredRecords.length === 0} className="btn-primary">
              <Download className="h-4 w-4" />
              Export
            </button>
          </div>
        </section>

        {/* Table */}
        <section className="mt-6 overflow-hidden rounded-xl bg-slate-900 ring-1 ring-slate-800 animate-fade-up">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-800 text-xs uppercase tracking-widest text-slate-500">
                <tr>
                  <th className="px-4 py-3 text-left">Date</th>
                  <th className="px-4 py-3 text-left">Function</th>
                  <th className="px-4 py-3 text-left">Result</th>
                  <th className="px-4 py-3 text-left">Health</th>
                  <th className="px-4 py-3 text-left">Response</th>
                  <th className="px-4 py-3 text-left">Version</th>
                  <th className="px-4 py-3 text-left">Platform</th>
                  <th className="px-4 py-3 text-left">Country</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {loading && (
                  <tr><td colSpan={8} className="px-4 py-8 text-center text-slate-500">
                    <RefreshCw className="mx-auto h-5 w-5 animate-spin mb-2" />Loading...
                  </td></tr>
                )}
                {!loading && error && (
                  <tr><td colSpan={8} className="px-4 py-8 text-center text-rose-400">{error}</td></tr>
                )}
                {!loading && !error && filteredRecords.length === 0 && (
                  <tr><td colSpan={8} className="px-4 py-8 text-center text-slate-500">No data found</td></tr>
                )}
                {!loading && !error && filteredRecords.slice(0, 100).map((item, index) => {
                  const health = getHealthLabel(item.is_plant_healthy ?? null);
                  const platform = getPlatformLabel(item.device_id);
                  const dateParts = getDateParts(item.date);
                  return (
                    <tr key={`${item.device_id}-${index}`} className="hover:bg-slate-800/50 transition">
                      <td className="px-4 py-3">
                        <p className="font-medium text-white">{dateParts.time}</p>
                        <p className="text-xs text-slate-500">{dateParts.date}</p>
                      </td>
                      <td className="px-4 py-3">
                        <span className="rounded-md bg-cyan-500/20 px-2 py-1 text-xs font-medium text-cyan-400">{item.function}</span>
                      </td>
                      <td className="px-4 py-3">
                        <p className="max-w-[200px] truncate text-slate-300" title={item.result}>{item.result || '—'}</p>
                      </td>
                      <td className="px-4 py-3">
                        <span className={`rounded-md px-2 py-1 text-xs font-medium ${health.tone}`}>{health.label}</span>
                      </td>
                      <td className="px-4 py-3 text-slate-400">{formatResponseTime(item.response_time_seconds)}</td>
                      <td className="px-4 py-3">
                        <span className="rounded-md bg-slate-700 px-2 py-1 text-xs text-slate-300">{item.app_version}</span>
                      </td>
                      <td className="px-4 py-3">
                        <span className={`rounded-md px-2 py-1 text-xs font-medium ${platform.tone}`}>{platform.label}</span>
                      </td>
                      <td className="px-4 py-3 text-slate-400">{item.country_code || '—'}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {filteredRecords.length > 100 && (
            <div className="px-4 py-3 text-center text-xs text-slate-500 border-t border-slate-800">
              Showing 100 of {filteredRecords.length} records
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
