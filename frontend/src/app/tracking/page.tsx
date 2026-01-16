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
  if (value === true) return { label: 'Healthy', tone: 'bg-emerald-50 text-emerald-700' };
  if (value === false) return { label: 'Issue', tone: 'bg-rose-50 text-rose-700' };
  return { label: 'Unknown', tone: 'bg-slate-100 text-slate-700' };
};

const getPlatformLabel = (deviceId: string | null | undefined) => {
  if (!deviceId) return { label: 'Unknown', tone: 'bg-slate-100 text-slate-700' };
  const normalized = deviceId.toUpperCase();
  if (normalized.startsWith('AID')) {
    return { label: 'Android', tone: 'bg-emerald-50 text-emerald-700' };
  }
  if (normalized.startsWith('DID') || normalized.startsWith('IOS')) {
    return { label: 'iOS', tone: 'bg-indigo-50 text-indigo-700' };
  }
  return { label: 'Unknown', tone: 'bg-slate-100 text-slate-700' };
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
    const list = Array.from(
      new Set(versionedRecords.map((item) => item.function).filter(Boolean))
    ).sort();
    return list;
  }, [versionedRecords]);

  const countries = useMemo(() => {
    const list = Array.from(
      new Set(versionedRecords.map((item) => item.country_code || 'unknown'))
    ).sort();
    return list;
  }, [versionedRecords]);

  const appVersions = useMemo(() => {
    const list = Array.from(
      new Set(versionedRecords.map((item) => item.app_version || 'unknown'))
    ).sort();
    return list;
  }, [versionedRecords]);

  const functionCounts = useMemo(() => {
    const map = new Map<string, number>();
    versionedRecords.forEach((item) => {
      map.set(item.function, (map.get(item.function) ?? 0) + 1);
    });
    return map;
  }, [versionedRecords]);

  const countryCounts = useMemo(() => {
    const map = new Map<string, number>();
    versionedRecords.forEach((item) => {
      const key = item.country_code || 'unknown';
      map.set(key, (map.get(key) ?? 0) + 1);
    });
    return map;
  }, [versionedRecords]);

  const versionCounts = useMemo(() => {
    const map = new Map<string, number>();
    versionedRecords.forEach((item) => {
      const key = item.app_version || 'unknown';
      map.set(key, (map.get(key) ?? 0) + 1);
    });
    return map;
  }, [versionedRecords]);

  const filteredRecords = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    return versionedRecords.filter((item) => {
      const matchesFunction = functionFilter === 'all' || item.function === functionFilter;
      const matchesCountry = countryFilter === 'all' || item.country_code === countryFilter;
      const normalizedVersion = item.app_version || 'unknown';
      const matchesVersion =
        appVersionFilter === 'all' || normalizedVersion === appVersionFilter;
      if (!matchesFunction || !matchesCountry || !matchesVersion) return false;
      if (!normalized) return true;
      const haystack = [
        item.device_id,
        item.result,
        item.app_version,
        item.country_code,
      ]
        .filter(Boolean)
        .join(' ')
        .toLowerCase();
      return haystack.includes(normalized);
    });
  }, [versionedRecords, query, functionFilter, countryFilter, appVersionFilter]);

  const stats = useMemo(() => {
    const total = versionedRecords.length;
    const deviceCount = new Set(
      versionedRecords.map((item) => item.device_id).filter(Boolean)
    ).size;
    const responseTimes = versionedRecords
      .map((item) => item.response_time_seconds)
      .filter((value): value is number => value !== null && !Number.isNaN(value));
    const avgResponse = responseTimes.length
      ? responseTimes.reduce((sum, value) => sum + value, 0) / responseTimes.length
      : null;
    const healthyCount = versionedRecords.filter((item) => item.is_plant_healthy === true).length;
    const issueCount = versionedRecords.filter((item) => item.is_plant_healthy === false).length;
    const latestTimestamp = versionedRecords.reduce((max, item) => {
      const time = new Date(item.date).getTime();
      if (Number.isNaN(time)) return max;
      return Math.max(max, time);
    }, 0);
    return {
      total,
      deviceCount,
      avgResponse,
      healthyCount,
      issueCount,
      latestTimestamp: latestTimestamp ? new Date(latestTimestamp) : null,
    };
  }, [versionedRecords]);

  const chartRecords = filteredRecords;
  const hasActiveFilters =
    query.trim().length > 0 ||
    functionFilter !== 'all' ||
    countryFilter !== 'all' ||
    appVersionFilter !== 'all';

  const handleExportCsv = () => {
    const headers = [
      'date',
      'function',
      'result',
      'is_plant_healthy',
      'response_time_seconds',
      'app_version',
      'platform',
      'device_id',
      'country_code',
      'image_url',
    ];
    const rows = filteredRecords.map((item) => {
      const platform = getPlatformLabel(item.device_id).label;
      return [
        item.date,
        item.function,
        item.result,
        item.is_plant_healthy,
        item.response_time_seconds,
        item.app_version,
        platform,
        item.device_id,
        item.country_code,
        item.image_url,
      ].map(formatCsvValue);
    });
    const csvContent = ['\ufeff' + headers.join(','), ...rows.map((row) => row.join(','))].join(
      '\n'
    );
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    const timestamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-');
    link.href = url;
    link.download = `tracking-${timestamp}.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const dailySeries = useMemo(() => {
    const map = new Map<string, number>();
    chartRecords.forEach((item) => {
      const day = item.date ? item.date.slice(0, 10) : 'unknown';
      map.set(day, (map.get(day) ?? 0) + 1);
    });
    return Array.from(map.entries())
      .map(([date, count]) => ({ date, count }))
      .sort((a, b) => a.date.localeCompare(b.date));
  }, [chartRecords]);

  const lineChart = useMemo(() => {
    const width = 320;
    const height = 140;
    const padding = 18;
    if (dailySeries.length === 0) {
      return { width, height, path: '', area: '', points: [] as Array<{ x: number; y: number }> };
    }
    const counts = dailySeries.map((item) => item.count);
    const max = Math.max(...counts, 1);
    const span = max || 1;
    const step =
      dailySeries.length === 1 ? 0 : (width - padding * 2) / (dailySeries.length - 1);
    const points = dailySeries.map((item, index) => {
      const x = padding + step * index;
      const y = height - padding - (item.count / span) * (height - padding * 2);
      return { x, y };
    });
    const path = points
      .map((point, index) => `${index === 0 ? 'M' : 'L'} ${point.x} ${point.y}`)
      .join(' ');
    const area = `M ${points[0].x} ${height - padding} ${points
      .map((point) => `L ${point.x} ${point.y}`)
      .join(' ')} L ${points[points.length - 1].x} ${height - padding} Z`;
    return { width, height, path, area, points };
  }, [dailySeries]);

  const functionSeries = useMemo(() => {
    const map = new Map<string, number>();
    chartRecords.forEach((item) => {
      const key = item.function || 'Unknown';
      map.set(key, (map.get(key) ?? 0) + 1);
    });
    const items = Array.from(map.entries())
      .map(([name, count]) => ({ name, count }))
      .sort((a, b) => b.count - a.count);
    if (items.length <= 4) return items;
    const top = items.slice(0, 4);
    const otherCount = items.slice(4).reduce((sum, item) => sum + item.count, 0);
    if (otherCount > 0) top.push({ name: 'Other', count: otherCount });
    return top;
  }, [chartRecords]);

  const functionTotal = useMemo(
    () => functionSeries.reduce((sum, item) => sum + item.count, 0),
    [functionSeries]
  );

  const lineLabels = useMemo(() => {
    if (dailySeries.length <= 3) return dailySeries;
    return [
      dailySeries[0],
      dailySeries[Math.floor(dailySeries.length / 2)],
      dailySeries[dailySeries.length - 1],
    ];
  }, [dailySeries]);

  const healthSeries = useMemo(() => {
    const healthy = chartRecords.filter((item) => item.is_plant_healthy === true).length;
    const issue = chartRecords.filter((item) => item.is_plant_healthy === false).length;
    const unknown = chartRecords.filter((item) => item.is_plant_healthy == null).length;
    const total = Math.max(healthy + issue + unknown, 1);
    const radius = 42;
    const circumference = 2 * Math.PI * radius;
    const segments = [
      { label: 'Healthy', value: healthy, color: '#10B981' },
      { label: 'Issue', value: issue, color: '#F43F5E' },
      { label: 'Unknown', value: unknown, color: '#94A3B8' },
    ];
    let offset = 0;
    const arcs = segments.map((segment) => {
      const length = (segment.value / total) * circumference;
      const dasharray = `${length} ${circumference - length}`;
      const dashoffset = -offset;
      offset += length;
      return { ...segment, dasharray, dashoffset };
    });
    return { total: healthy + issue + unknown, radius, circumference, arcs };
  }, [chartRecords]);

  return (
    <div className="relative min-h-screen overflow-hidden bg-background text-foreground">
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute -top-32 right-[-10%] h-[420px] w-[420px] rounded-full bg-[radial-gradient(circle_at_center,rgba(14,165,233,0.45),transparent_65%)] blur-3xl opacity-80 motion-safe:animate-float-slow" />
        <div className="absolute -bottom-40 left-[-10%] h-[420px] w-[420px] rounded-full bg-[radial-gradient(circle_at_center,rgba(249,115,22,0.35),transparent_60%)] blur-3xl opacity-80 motion-safe:animate-float-medium" />
      </div>

      <div className="relative z-10 mx-auto flex min-h-screen max-w-6xl flex-col px-4 pb-16 pt-10 md:pt-14">
        <header className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <Link
              href="/"
              className="inline-flex h-11 w-11 items-center justify-center rounded-2xl bg-white/80 text-slate-700 shadow-sm ring-1 ring-slate-200 transition hover:-translate-y-0.5"
            >
              <ArrowLeft className="h-5 w-5" />
            </Link>
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.35em] text-slate-500">
                Analytics
              </p>
              <h1 className="text-3xl font-heading font-semibold text-slate-900 md:text-4xl">
                Tracking Dashboard
              </h1>
              <p className="mt-1 text-sm text-slate-600">
                Theo dõi log realtime cho Plant Identify & Diagnose.
              </p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Link
              href="/tools"
              className="inline-flex items-center gap-2 rounded-full bg-white/80 px-4 py-2 text-xs font-semibold text-slate-700 shadow-sm ring-1 ring-slate-200 transition hover:-translate-y-0.5"
            >
              Tools
            </Link>
            <button
              onClick={fetchTracking}
              className="inline-flex items-center gap-2 rounded-full bg-slate-900 px-4 py-2 text-xs font-semibold text-white shadow-sm transition hover:-translate-y-0.5"
              disabled={loading}
            >
              <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
              Làm mới
            </button>
          </div>
        </header>

        <section className="mt-8 grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          <div className="rounded-2xl bg-white/80 p-4 shadow-sm ring-1 ring-slate-200">
            <div className="flex items-center justify-between">
              <p className="text-xs font-semibold uppercase tracking-widest text-slate-500">
                Tổng request
              </p>
              <BarChart3 className="h-4 w-4 text-sky-500" />
            </div>
            <p className="mt-3 text-3xl font-semibold text-slate-900">{stats.total}</p>
            <p className="mt-1 text-xs text-slate-600">
              {filteredRecords.length} hiển thị · {versionedRecords.length} total
            </p>
          </div>
          <div className="rounded-2xl bg-white/80 p-4 shadow-sm ring-1 ring-slate-200">
            <div className="flex items-center justify-between">
              <p className="text-xs font-semibold uppercase tracking-widest text-slate-500">
                Thiết bị
              </p>
              <Smartphone className="h-4 w-4 text-sky-500" />
            </div>
            <p className="mt-3 text-3xl font-semibold text-slate-900">{stats.deviceCount}</p>
            <p className="mt-1 text-xs text-slate-600">Unique device_id</p>
          </div>
          <div className="rounded-2xl bg-white/80 p-4 shadow-sm ring-1 ring-slate-200">
            <div className="flex items-center justify-between">
              <p className="text-xs font-semibold uppercase tracking-widest text-slate-500">
                Avg response
              </p>
              <Clock3 className="h-4 w-4 text-sky-500" />
            </div>
            <p className="mt-3 text-3xl font-semibold text-slate-900">
              {stats.avgResponse ? `${stats.avgResponse.toFixed(2)}s` : '--'}
            </p>
            <p className="mt-1 text-xs text-slate-600">Chỉ tính records có thời gian</p>
          </div>
          <div className="rounded-2xl bg-white/80 p-4 shadow-sm ring-1 ring-slate-200">
            <div className="flex items-center justify-between">
              <p className="text-xs font-semibold uppercase tracking-widest text-slate-500">
                Health check
              </p>
              <HeartPulse className="h-4 w-4 text-rose-500" />
            </div>
            <p className="mt-3 text-3xl font-semibold text-slate-900">
              {stats.healthyCount} / {stats.issueCount}
            </p>
            <p className="mt-1 text-xs text-slate-600">Healthy / Issue</p>
          </div>
        </section>

        <section className="mt-8 rounded-3xl bg-white/85 p-4 shadow-sm ring-1 ring-slate-200 md:p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.3em] text-slate-500">
              Filters
              {hasActiveFilters && (
                <span className="rounded-full bg-slate-900 px-2 py-0.5 text-[10px] text-white">
                  Active
                </span>
              )}
            </div>
            <div className="flex items-center gap-2 text-xs text-slate-500">
              <Globe2 className="h-4 w-4" />
              {pagination ? `${pagination.total} records` : 'Loading...'}
            </div>
          </div>
          <div className="mt-4 grid gap-3 md:grid-cols-[1.2fr_repeat(3,1fr)_auto_auto]">
            <div className="flex items-center gap-2 rounded-2xl bg-slate-100/80 px-3 py-2">
              <Search className="h-4 w-4 text-slate-500" />
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Tìm device, result, version..."
                className="w-full bg-transparent text-sm text-slate-700 placeholder:text-slate-500 focus:outline-none"
              />
            </div>
            <div className="space-y-1">
              <p className="text-[11px] font-semibold uppercase tracking-widest text-slate-500">
                Function
              </p>
              <select
                value={functionFilter}
                onChange={(event) => setFunctionFilter(event.target.value)}
                className="w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700"
              >
                <option value="all">Tất cả ({versionedRecords.length})</option>
                {functions.map((item) => (
                  <option key={item} value={item}>
                    {item} ({functionCounts.get(item) ?? 0})
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-1">
              <p className="text-[11px] font-semibold uppercase tracking-widest text-slate-500">
                Version
              </p>
              <select
                value={appVersionFilter}
                onChange={(event) => setAppVersionFilter(event.target.value)}
                className="w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700"
              >
                <option value="all">Tất cả ({versionedRecords.length})</option>
                {appVersions.map((item) => (
                  <option key={item} value={item}>
                    {item} ({versionCounts.get(item) ?? 0})
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-1">
              <p className="text-[11px] font-semibold uppercase tracking-widest text-slate-500">
                Country
              </p>
              <select
                value={countryFilter}
                onChange={(event) => setCountryFilter(event.target.value)}
                className="w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700"
              >
                <option value="all">Tất cả ({versionedRecords.length})</option>
                {countries.map((item) => (
                  <option key={item} value={item}>
                    {item} ({countryCounts.get(item) ?? 0})
                  </option>
                ))}
              </select>
            </div>
            <button
              onClick={() => {
                setQuery('');
                setFunctionFilter('all');
                setCountryFilter('all');
                setAppVersionFilter('all');
              }}
              className="h-[46px] rounded-2xl border border-slate-200 bg-white px-4 text-xs font-semibold text-slate-700 shadow-sm transition hover:-translate-y-0.5"
            >
              Reset
            </button>
            <button
              onClick={handleExportCsv}
              disabled={filteredRecords.length === 0}
              className="flex h-[46px] items-center justify-center gap-2 rounded-2xl bg-slate-900 px-4 text-xs font-semibold text-white shadow-sm transition hover:-translate-y-0.5 disabled:cursor-not-allowed disabled:opacity-60"
            >
              <Download className="h-4 w-4" />
              Export CSV
            </button>
          </div>
        </section>

        <section className="mt-6 grid gap-4 lg:grid-cols-3">
          <div className="rounded-3xl bg-white/80 p-5 shadow-sm ring-1 ring-slate-200">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-semibold uppercase tracking-widest text-slate-500">
                  Requests theo ngày
                </p>
                <p className="mt-1 text-sm text-slate-700">
                  {dailySeries.length} ngày · {chartRecords.length} requests
                </p>
              </div>
              <span className="rounded-full bg-sky-50 px-3 py-1 text-xs font-semibold text-sky-600">
                Trend
              </span>
            </div>
            <div className="mt-4">
              {dailySeries.length === 0 ? (
                <div className="flex h-[140px] items-center justify-center rounded-2xl bg-slate-50 text-sm text-slate-500">
                  Không có dữ liệu
                </div>
              ) : (
                <svg
                  viewBox={`0 0 ${lineChart.width} ${lineChart.height}`}
                  className="h-[140px] w-full"
                >
                  <defs>
                    <linearGradient id="lineFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#38BDF8" stopOpacity="0.35" />
                      <stop offset="100%" stopColor="#38BDF8" stopOpacity="0" />
                    </linearGradient>
                    <linearGradient id="lineStroke" x1="0" y1="0" x2="1" y2="0">
                      <stop offset="0%" stopColor="#0EA5E9" />
                      <stop offset="100%" stopColor="#2563EB" />
                    </linearGradient>
                  </defs>
                  <path d={lineChart.area} fill="url(#lineFill)" />
                  <path
                    d={lineChart.path}
                    fill="none"
                    stroke="url(#lineStroke)"
                    strokeWidth="3"
                    strokeLinecap="round"
                  />
                  {lineChart.points.map((point, index) => (
                    <circle
                      key={`point-${index}`}
                      cx={point.x}
                      cy={point.y}
                      r="3.5"
                      fill="#0EA5E9"
                      stroke="#FFFFFF"
                      strokeWidth="2"
                    />
                  ))}
                </svg>
              )}
            </div>
            {lineLabels.length > 0 && (
              <div className="mt-3 flex items-center justify-between text-[11px] text-slate-500">
                {lineLabels.map((item) => (
                  <span key={item.date}>{formatDayLabel(item.date)}</span>
                ))}
              </div>
            )}
          </div>

          <div className="rounded-3xl bg-white/80 p-5 shadow-sm ring-1 ring-slate-200">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-semibold uppercase tracking-widest text-slate-500">
                  Function split
                </p>
                <p className="mt-1 text-sm text-slate-700">Top usage theo chức năng</p>
              </div>
              <span className="rounded-full bg-orange-50 px-3 py-1 text-xs font-semibold text-orange-600">
                Breakdown
              </span>
            </div>
            <div className="mt-5 space-y-4">
              {functionSeries.length === 0 ? (
                <div className="flex h-[140px] items-center justify-center rounded-2xl bg-slate-50 text-sm text-slate-500">
                  Không có dữ liệu
                </div>
              ) : (
                functionSeries.map((item) => {
                  const ratio = functionTotal ? (item.count / functionTotal) * 100 : 0;
                  return (
                    <div key={item.name} className="flex items-center gap-3">
                      <span className="w-28 truncate text-xs font-semibold text-slate-600">
                        {item.name}
                      </span>
                      <div className="h-2 flex-1 rounded-full bg-slate-100">
                        <div
                          className="h-2 rounded-full bg-gradient-to-r from-sky-500 via-blue-500 to-indigo-500"
                          style={{ width: `${ratio}%` }}
                        />
                      </div>
                      <span className="text-xs text-slate-600">{item.count}</span>
                    </div>
                  );
                })
              )}
            </div>
          </div>

          <div className="rounded-3xl bg-white/80 p-5 shadow-sm ring-1 ring-slate-200">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-semibold uppercase tracking-widest text-slate-500">
                  Health status
                </p>
                <p className="mt-1 text-sm text-slate-700">Tình trạng kết quả trả về</p>
              </div>
              <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-600">
                Health
              </span>
            </div>
            <div className="mt-5 flex flex-wrap items-center gap-6">
              <div className="relative h-28 w-28">
                <svg viewBox="0 0 120 120" className="h-28 w-28">
                  <circle
                    cx="60"
                    cy="60"
                    r={healthSeries.radius}
                    stroke="#E2E8F0"
                    strokeWidth="12"
                    fill="none"
                  />
                  {healthSeries.arcs.map((segment) => (
                    <circle
                      key={segment.label}
                      cx="60"
                      cy="60"
                      r={healthSeries.radius}
                      stroke={segment.color}
                      strokeWidth="12"
                      fill="none"
                      strokeLinecap="round"
                      strokeDasharray={segment.dasharray}
                      strokeDashoffset={segment.dashoffset}
                      transform="rotate(-90 60 60)"
                    />
                  ))}
                  <text
                    x="60"
                    y="58"
                    textAnchor="middle"
                    style={{ fill: '#0F172A', fontSize: '20px', fontWeight: 600 }}
                  >
                    {healthSeries.total}
                  </text>
                  <text
                    x="60"
                    y="76"
                    textAnchor="middle"
                    style={{ fill: '#64748B', fontSize: '9px', letterSpacing: '0.2em' }}
                  >
                    TOTAL
                  </text>
                </svg>
              </div>
              <div className="space-y-3 text-xs text-slate-600">
                {healthSeries.arcs.map((segment) => (
                  <div key={segment.label} className="flex items-center gap-3">
                    <span
                      className="h-2 w-2 rounded-full"
                      style={{ backgroundColor: segment.color }}
                    />
                    <span className="w-16 font-semibold text-slate-700">{segment.label}</span>
                    <span>{segment.value}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>

        <section className="mt-6 overflow-hidden rounded-3xl border border-slate-200 bg-white/85 shadow-sm">
          <div className="overflow-x-auto">
            <table className="min-w-[1260px] w-full text-left text-sm">
              <thead className="bg-slate-100/90 text-xs uppercase tracking-widest text-slate-500">
                <tr>
                  <th className="px-4 py-3">Date</th>
                  <th className="px-4 py-3">Function</th>
                  <th className="px-4 py-3">Result</th>
                  <th className="px-4 py-3">Health</th>
                  <th className="px-4 py-3">Response</th>
                  <th className="px-4 py-3">Version</th>
                  <th className="px-4 py-3">Platform</th>
                  <th className="px-4 py-3">Device</th>
                  <th className="px-4 py-3">Country</th>
                  <th className="px-4 py-3">Image</th>
                </tr>
              </thead>
              <tbody>
                {loading && (
                  <tr>
                    <td className="px-4 py-6 text-sm text-slate-600" colSpan={8}>
                      Đang tải dữ liệu...
                    </td>
                  </tr>
                )}
                {!loading && error && (
                  <tr>
                    <td className="px-4 py-6 text-sm text-rose-500" colSpan={8}>
                      {error}
                    </td>
                  </tr>
                )}
                {!loading && !error && filteredRecords.length === 0 && (
                  <tr>
                    <td className="px-4 py-6 text-sm text-slate-600" colSpan={8}>
                      Không có dữ liệu phù hợp.
                    </td>
                  </tr>
                )}
                {!loading &&
                  !error &&
                  filteredRecords.map((item, index) => {
                    const health = getHealthLabel(item.is_plant_healthy ?? null);
                    const platform = getPlatformLabel(item.device_id);
                    const dateParts = getDateParts(item.date);
                    return (
                      <tr
                        key={`${item.device_id}-${item.date}-${index}`}
                        className="border-b border-slate-100 transition hover:bg-slate-50/80 last:border-b-0"
                      >
                        <td className="px-4 py-4">
                          <div className="space-y-1">
                            <p className="text-sm font-semibold text-slate-800">
                              {dateParts.time}
                            </p>
                            <p className="text-xs text-slate-500">
                              {dateParts.date}
                            </p>
                          </div>
                        </td>
                        <td className="px-4 py-4">
                          <span className="rounded-full bg-sky-100 px-3 py-1 text-xs font-semibold text-sky-700">
                            {item.function}
                          </span>
                        </td>
                        <td className="px-4 py-4">
                          <p
                            className="max-w-[320px] truncate text-sm font-semibold text-slate-800"
                            title={item.result}
                          >
                            {item.result || '—'}
                          </p>
                        </td>
                        <td className="px-4 py-4">
                          <span
                            className={`rounded-full px-3 py-1 text-xs font-semibold ${health.tone}`}
                          >
                            {health.label}
                          </span>
                        </td>
                        <td className="px-4 py-4 text-sm font-semibold text-slate-700">
                          {formatResponseTime(item.response_time_seconds)}
                        </td>
                        <td className="px-4 py-4 text-xs text-slate-600">
                          <span className="rounded-full bg-indigo-50 px-3 py-1 font-semibold text-indigo-700">
                            {item.app_version || 'unknown'}
                          </span>
                        </td>
                        <td className="px-4 py-4 text-xs text-slate-600">
                          <span className={`rounded-full px-3 py-1 font-semibold ${platform.tone}`}>
                            {platform.label}
                          </span>
                        </td>
                        <td className="px-4 py-4 text-xs text-slate-600">
                          <span className="rounded-full bg-slate-100 px-2 py-1 font-mono text-slate-700">
                            {item.device_id || 'unknown'}
                          </span>
                        </td>
                        <td className="px-4 py-4 text-xs font-semibold text-slate-700">
                          {(item.country_code || 'unknown').toUpperCase()}
                        </td>
                        <td className="px-4 py-4">
                          {item.image_url ? (
                            <img
                              src={item.image_url}
                              alt="Tracking preview"
                              className="h-12 w-12 rounded-xl object-cover"
                              loading="lazy"
                            />
                          ) : (
                            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-slate-100 text-xs text-slate-500">
                              N/A
                            </div>
                          )}
                        </td>
                      </tr>
                    );
                  })}
              </tbody>
            </table>
          </div>
        </section>

        <div className="mt-6 flex flex-wrap items-center justify-between gap-3 text-xs text-slate-600">
          <span>
            Lần cập nhật gần nhất:{' '}
            {stats.latestTimestamp ? formatDateTime(stats.latestTimestamp.toISOString()) : '--'}
          </span>
          <span>Endpoint: /api/analytics/v1/tracking</span>
        </div>
      </div>
    </div>
  );
}
