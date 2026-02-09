'use client';

import { useEffect, useMemo, useState, useCallback } from 'react';
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
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
  Calendar,
  X,
  Image as ImageIcon,
  Filter,
  SlidersHorizontal,
  TrendingUp,
  PieChart,
} from 'lucide-react';
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  BarChart,
  Bar,
  PieChart as RechartsPieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import { apiClient, TrackingItem, TrackingResponse } from '@/lib/api-client';

// ==================== UTILITIES ====================

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
    }).format(date),
  };
};

const formatResponseTime = (value: number | null) => {
  if (value === null || Number.isNaN(value)) return '--';
  return `${value.toFixed(2)}s`;
};

const getHealthLabel = (value: boolean | null) => {
  if (value === true) return { label: 'Healthy', tone: 'bg-emerald-500/20 text-emerald-400 ring-emerald-500/30' };
  if (value === false) return { label: 'Issue', tone: 'bg-rose-500/20 text-rose-400 ring-rose-500/30' };
  return { label: 'Unknown', tone: 'bg-slate-700/50 text-slate-400 ring-slate-600/30' };
};

const getPlatformLabel = (deviceId: string | null | undefined) => {
  if (!deviceId) return { label: 'Unknown', tone: 'bg-slate-700/50 text-slate-400' };
  const normalized = deviceId.toUpperCase();
  const iosUuidPattern = /^[0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12}$/;
  if (normalized.startsWith('AID')) {
    return { label: 'Android', tone: 'bg-emerald-500/20 text-emerald-400' };
  }
  if (normalized.startsWith('DID') || normalized.startsWith('IOS') || iosUuidPattern.test(normalized)) {
    return { label: 'Ios', tone: 'bg-indigo-500/20 text-indigo-400' };
  }
  return { label: 'Unknown', tone: 'bg-slate-700/50 text-slate-400' };
};

const formatCsvValue = (value: string | number | boolean | null | undefined) => {
  if (value === null || value === undefined) return '';
  const raw = String(value);
  const escaped = raw.replace(/"/g, '""');
  if (/[",\n]/.test(escaped)) return `"${escaped}"`;
  return escaped;
};

// ==================== SKELETON COMPONENTS ====================

const SkeletonRow = () => (
  <tr className="animate-pulse">
    {[...Array(9)].map((_, i) => (
      <td key={i} className="px-4 py-4">
        <div className="h-4 bg-slate-700/50 rounded-md w-full" style={{ width: `${60 + Math.random() * 40}%` }} />
      </td>
    ))}
  </tr>
);

const StatCardSkeleton = () => (
  <div className="glass-card p-5 animate-pulse">
    <div className="flex items-center justify-between mb-4">
      <div className="h-3 bg-slate-700/50 rounded w-24" />
      <div className="h-5 w-5 bg-slate-700/50 rounded" />
    </div>
    <div className="h-8 bg-slate-700/50 rounded w-20 mb-2" />
    <div className="h-3 bg-slate-700/50 rounded w-16" />
  </div>
);

// ==================== PAGINATION COMPONENT ====================

interface PaginationProps {
  currentPage: number;
  totalPages: number;
  totalItems: number;
  itemsPerPage: number;
  onPageChange: (page: number) => void;
  onItemsPerPageChange: (count: number) => void;
}

const Pagination = ({
  currentPage,
  totalPages,
  totalItems,
  itemsPerPage,
  onPageChange,
  onItemsPerPageChange,
}: PaginationProps) => {
  const startItem = (currentPage - 1) * itemsPerPage + 1;
  const endItem = Math.min(currentPage * itemsPerPage, totalItems);

  const getPageNumbers = () => {
    const pages: (number | string)[] = [];
    const delta = 2;

    // Guard against invalid totalPages
    if (!totalPages || totalPages <= 0 || !Number.isFinite(totalPages)) {
      return [1];
    }

    if (totalPages <= 7) {
      return Array.from({ length: totalPages }, (_, i) => i + 1);
    }

    pages.push(1);

    if (currentPage > delta + 2) {
      pages.push('...');
    }

    const start = Math.max(2, currentPage - delta);
    const end = Math.min(totalPages - 1, currentPage + delta);

    for (let i = start; i <= end; i++) {
      if (!pages.includes(i)) pages.push(i);
    }

    if (currentPage < totalPages - delta - 1) {
      pages.push('...');
    }

    if (!pages.includes(totalPages)) {
      pages.push(totalPages);
    }

    return pages;
  };

  return (
    <div className="flex flex-wrap items-center justify-between gap-4 px-4 py-4 border-t border-white/5">
      {/* Info */}
      <div className="text-sm text-slate-400">
        Showing <span className="font-medium text-white">{startItem}</span> to{' '}
        <span className="font-medium text-white">{endItem}</span> of{' '}
        <span className="font-medium text-white">{totalItems.toLocaleString()}</span> results
      </div>

      {/* Controls */}
      <div className="flex items-center gap-2">
        {/* Items per page */}
        <div className="flex items-center gap-2 mr-4">
          <span className="text-xs text-slate-500">Per page:</span>
          <select
            value={itemsPerPage}
            onChange={(e) => onItemsPerPageChange(Number(e.target.value))}
            className="bg-slate-800/80 border border-white/10 rounded-lg px-2 py-1.5 text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500/50 cursor-pointer"
          >
            {[25, 50, 100].map((n) => (
              <option key={n} value={n}>{n}</option>
            ))}
          </select>
        </div>

        {/* First & Prev */}
        <button
          onClick={() => onPageChange(1)}
          disabled={currentPage === 1}
          className="p-2 rounded-lg bg-slate-800/50 border border-white/5 text-slate-400 hover:bg-slate-700/50 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed transition-all cursor-pointer"
        >
          <ChevronsLeft className="w-4 h-4" />
        </button>
        <button
          onClick={() => onPageChange(currentPage - 1)}
          disabled={currentPage === 1}
          className="p-2 rounded-lg bg-slate-800/50 border border-white/5 text-slate-400 hover:bg-slate-700/50 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed transition-all cursor-pointer"
        >
          <ChevronLeft className="w-4 h-4" />
        </button>

        {/* Page numbers */}
        <div className="flex items-center gap-1">
          {getPageNumbers().map((page, idx) =>
            typeof page === 'string' ? (
              <span key={`ellipsis-${idx}`} className="px-2 text-slate-500">...</span>
            ) : (
              <button
                key={page}
                onClick={() => onPageChange(page)}
                className={`min-w-[36px] h-9 rounded-lg text-sm font-medium transition-all cursor-pointer ${currentPage === page
                  ? 'bg-blue-500 text-white shadow-lg shadow-blue-500/25'
                  : 'bg-slate-800/50 border border-white/5 text-slate-400 hover:bg-slate-700/50 hover:text-white'
                  }`}
              >
                {page}
              </button>
            )
          )}
        </div>

        {/* Next & Last */}
        <button
          onClick={() => onPageChange(currentPage + 1)}
          disabled={currentPage === totalPages}
          className="p-2 rounded-lg bg-slate-800/50 border border-white/5 text-slate-400 hover:bg-slate-700/50 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed transition-all cursor-pointer"
        >
          <ChevronRight className="w-4 h-4" />
        </button>
        <button
          onClick={() => onPageChange(totalPages)}
          disabled={currentPage === totalPages}
          className="p-2 rounded-lg bg-slate-800/50 border border-white/5 text-slate-400 hover:bg-slate-700/50 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed transition-all cursor-pointer"
        >
          <ChevronsRight className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
};

// ==================== FILTER BADGE ====================

interface FilterBadgeProps {
  label: string;
  value: string;
  onRemove: () => void;
}

const FilterBadge = ({ label, value, onRemove }: FilterBadgeProps) => (
  <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-blue-500/20 text-blue-400 text-xs font-medium ring-1 ring-blue-500/30">
    <span className="text-blue-300/70">{label}:</span>
    {value}
    <button onClick={onRemove} className="ml-0.5 hover:text-white transition-colors cursor-pointer">
      <X className="w-3 h-3" />
    </button>
  </span>
);

// ==================== QUICK DATE PRESETS ====================

interface QuickDateProps {
  onSelect: (from: string, to: string) => void;
  activePreset: string | null;
}

const QuickDatePresets = ({ onSelect, activePreset }: QuickDateProps) => {
  const presets = [
    { label: 'Today', key: 'today', days: 0 },
    { label: 'Yesterday', key: 'yesterday', days: 1 },
    { label: 'Last 7 days', key: '7days', days: 7 },
    { label: 'Last 30 days', key: '30days', days: 30 },
  ];

  const handleClick = (key: string, days: number) => {
    const today = new Date();
    const to = today.toISOString().split('T')[0];

    if (key === 'yesterday') {
      const yesterday = new Date(today);
      yesterday.setDate(yesterday.getDate() - 1);
      const from = yesterday.toISOString().split('T')[0];
      onSelect(from, from);
    } else if (key === 'today') {
      onSelect(to, to);
    } else {
      const from = new Date(today);
      from.setDate(from.getDate() - days);
      onSelect(from.toISOString().split('T')[0], to);
    }
  };

  return (
    <div className="flex flex-wrap gap-2">
      {presets.map((p) => (
        <button
          key={p.key}
          onClick={() => handleClick(p.key, p.days)}
          className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all cursor-pointer ${activePreset === p.key
            ? 'bg-blue-500 text-white'
            : 'bg-slate-800/50 text-slate-400 hover:bg-slate-700/50 hover:text-white border border-white/5'
            }`}
        >
          {p.label}
        </button>
      ))}
    </div>
  );
};

// ==================== MAIN COMPONENT ====================

export default function TrackingPage() {
  const [records, setRecords] = useState<TrackingItem[]>([]);
  const [pagination, setPagination] = useState<TrackingResponse['pagination'] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [query, setQuery] = useState('');
  const [functionFilter, setFunctionFilter] = useState('all');
  const [countryFilter, setCountryFilter] = useState('all');
  const [appVersionFilter, setAppVersionFilter] = useState('all');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [previewImage, setPreviewImage] = useState<string | null>(null);
  const [showFilters, setShowFilters] = useState(true);
  const [activePreset, setActivePreset] = useState<string | null>(null);

  // Pagination state
  const [currentPage, setCurrentPage] = useState(1);
  const [itemsPerPage, setItemsPerPage] = useState(50);
  const [showCharts, setShowCharts] = useState(true);

  const fetchTracking = async () => {
    setLoading(true);
    setError('');
    try {
      // Fetch multiple pages to get all data
      let allRecords: TrackingItem[] = [];
      let page = 1;
      let hasMore = true;

      while (hasMore && page <= 30) { // Max 30 pages (3000 records)
        const response = await apiClient.getTracking(page, 100);
        allRecords = [...allRecords, ...response.data];
        setPagination(response.pagination);

        if (response.data.length < 100 || allRecords.length >= response.pagination.total) {
          hasMore = false;
        }
        page++;
      }

      setRecords(allRecords);
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

      if (dateFrom || dateTo) {
        const itemDate = new Date(item.date).getTime();
        if (Number.isNaN(itemDate)) return false;
        if (dateFrom) {
          const fromDate = new Date(dateFrom).setHours(0, 0, 0, 0);
          if (itemDate < fromDate) return false;
        }
        if (dateTo) {
          const toDate = new Date(dateTo).setHours(23, 59, 59, 999);
          if (itemDate > toDate) return false;
        }
      }

      if (!normalized) return true;
      const haystack = [item.device_id, item.result, item.app_version, item.country_code]
        .filter(Boolean)
        .join(' ')
        .toLowerCase();
      return haystack.includes(normalized);
    });
  }, [versionedRecords, query, functionFilter, countryFilter, appVersionFilter, dateFrom, dateTo]);

  // Paginated records
  const paginatedRecords = useMemo(() => {
    const start = (currentPage - 1) * itemsPerPage;
    return filteredRecords.slice(start, start + itemsPerPage);
  }, [filteredRecords, currentPage, itemsPerPage]);

  const totalPages = Math.ceil(filteredRecords.length / itemsPerPage);

  // Reset to page 1 when filters change
  useEffect(() => {
    setCurrentPage(1);
  }, [query, functionFilter, countryFilter, appVersionFilter, dateFrom, dateTo, itemsPerPage]);

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

  const activeFilters = useMemo(() => {
    const filters: { key: string; label: string; value: string; onRemove: () => void }[] = [];
    if (query.trim()) filters.push({ key: 'query', label: 'Search', value: query, onRemove: () => setQuery('') });
    if (functionFilter !== 'all') filters.push({ key: 'function', label: 'Function', value: functionFilter, onRemove: () => setFunctionFilter('all') });
    if (countryFilter !== 'all') filters.push({ key: 'country', label: 'Country', value: countryFilter, onRemove: () => setCountryFilter('all') });
    if (appVersionFilter !== 'all') filters.push({ key: 'version', label: 'Version', value: appVersionFilter, onRemove: () => setAppVersionFilter('all') });
    if (dateFrom) filters.push({ key: 'dateFrom', label: 'From', value: dateFrom, onRemove: () => { setDateFrom(''); setActivePreset(null); } });
    if (dateTo) filters.push({ key: 'dateTo', label: 'To', value: dateTo, onRemove: () => { setDateTo(''); setActivePreset(null); } });
    return filters;
  }, [query, functionFilter, countryFilter, appVersionFilter, dateFrom, dateTo]);

  const clearAllFilters = () => {
    setQuery('');
    setFunctionFilter('all');
    setCountryFilter('all');
    setAppVersionFilter('all');
    setDateFrom('');
    setDateTo('');
    setActivePreset(null);
  };

  const handleDatePreset = (from: string, to: string) => {
    setDateFrom(from);
    setDateTo(to);
    // Determine which preset was selected
    const today = new Date().toISOString().split('T')[0];
    if (from === to && from === today) setActivePreset('today');
    else if (from === to) setActivePreset('yesterday');
    else {
      const diffDays = Math.round((new Date(to).getTime() - new Date(from).getTime()) / (1000 * 60 * 60 * 24));
      if (diffDays === 6) setActivePreset('7days');
      else if (diffDays === 29) setActivePreset('30days');
      else setActivePreset(null);
    }
  };

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
    <div className="min-h-screen bg-[#0a0f1a] text-slate-100">
      {/* Gradient background orbs */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden">
        <div className="absolute -top-40 -right-40 h-[600px] w-[600px] rounded-full bg-blue-500/10 blur-[128px]" />
        <div className="absolute top-1/2 -left-40 h-[500px] w-[500px] rounded-full bg-purple-500/8 blur-[128px]" />
        <div className="absolute -bottom-40 right-1/4 h-[400px] w-[400px] rounded-full bg-cyan-500/8 blur-[128px]" />
      </div>

      <div className="relative z-10 mx-auto max-w-[1600px] px-4 py-6 md:px-6 lg:px-8">
        {/* Header */}
        <header className="flex flex-wrap items-center justify-between gap-4 mb-8">
          <div className="flex items-center gap-4">
            <Link
              href="/"
              className="inline-flex h-11 w-11 items-center justify-center rounded-xl bg-white/5 backdrop-blur-xl border border-white/10 text-slate-300 transition-all hover:bg-white/10 hover:border-white/20 hover:text-white cursor-pointer"
            >
              <ArrowLeft className="h-5 w-5" />
            </Link>
            <div>
              <div className="flex items-center gap-2 mb-1">
                <span className="px-2 py-0.5 rounded-md bg-blue-500/20 text-blue-400 text-[10px] font-bold uppercase tracking-wider">Analytics</span>
              </div>
              <h1 className="text-2xl font-bold text-white md:text-3xl tracking-tight">Tracking Dashboard</h1>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <Link href="/tools" className="btn-glass cursor-pointer">Tools</Link>
            <button onClick={fetchTracking} disabled={loading} className="btn-primary cursor-pointer">
              <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
              Refresh
            </button>
          </div>
        </header>

        {/* Stats Grid - Bento Style */}
        <section className="grid gap-4 md:grid-cols-2 lg:grid-cols-4 mb-6">
          {loading ? (
            [...Array(4)].map((_, i) => <StatCardSkeleton key={i} />)
          ) : (
            [
              { label: 'Total Requests', value: stats.total.toLocaleString(), sub: `${filteredRecords.length.toLocaleString()} filtered`, icon: BarChart3, color: 'from-cyan-500 to-blue-500', iconBg: 'bg-cyan-500/20' },
              { label: 'Unique Devices', value: stats.deviceCount.toLocaleString(), sub: 'Active devices', icon: Smartphone, color: 'from-violet-500 to-purple-500', iconBg: 'bg-violet-500/20' },
              { label: 'Avg Response', value: stats.avgResponse ? `${stats.avgResponse.toFixed(2)}s` : '--', sub: 'Response time', icon: Clock3, color: 'from-amber-500 to-orange-500', iconBg: 'bg-amber-500/20' },
              { label: 'Health Ratio', value: `${stats.healthyCount}/${stats.issueCount}`, sub: 'Healthy / Issues', icon: HeartPulse, color: 'from-emerald-500 to-teal-500', iconBg: 'bg-emerald-500/20' },
            ].map((stat, idx) => (
              <div
                key={stat.label}
                className="group relative overflow-hidden rounded-2xl bg-white/[0.03] backdrop-blur-xl border border-white/[0.05] p-5 transition-all duration-300 hover:bg-white/[0.06] hover:border-white/10 hover:shadow-2xl hover:shadow-black/20"
                style={{ animationDelay: `${idx * 100}ms` }}
              >
                {/* Gradient line at top */}
                <div className={`absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r ${stat.color} opacity-60`} />

                <div className="flex items-center justify-between mb-4">
                  <p className="text-xs font-semibold uppercase tracking-[0.15em] text-slate-500">{stat.label}</p>
                  <div className={`p-2 rounded-lg ${stat.iconBg}`}>
                    <stat.icon className="h-4 w-4 text-white/80" />
                  </div>
                </div>
                <p className="text-3xl font-bold text-white tracking-tight">{stat.value}</p>
                <p className="mt-1.5 text-xs text-slate-500">{stat.sub}</p>
              </div>
            ))
          )}
        </section>

        {/* Charts Section */}
        {!loading && versionedRecords.length > 0 && (
          <section className="mb-6">
            <div className="flex items-center justify-between mb-4">
              <button
                onClick={() => setShowCharts(!showCharts)}
                className="flex items-center gap-2 text-sm font-medium text-slate-300 hover:text-white transition-colors cursor-pointer"
              >
                <TrendingUp className="w-4 h-4" />
                Analytics Charts
                <ChevronDown className={`w-4 h-4 transition-transform ${showCharts ? 'rotate-180' : ''}`} />
              </button>
            </div>

            {showCharts && (
              <div className="grid gap-4 lg:grid-cols-2 xl:grid-cols-3">
                {/* Requests Over Time - Area Chart */}
                <div className="rounded-2xl bg-white/[0.03] backdrop-blur-xl border border-white/[0.05] p-5 lg:col-span-2">
                  <h3 className="text-sm font-semibold text-slate-400 mb-4">Requests Over Time (Last 7 Days)</h3>
                  <div className="h-[250px]">
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart
                        data={(() => {
                          const dailyMap = new Map<string, number>();
                          const last7Days = [];
                          for (let i = 6; i >= 0; i--) {
                            const d = new Date();
                            d.setDate(d.getDate() - i);
                            const key = d.toISOString().split('T')[0];
                            dailyMap.set(key, 0);
                            last7Days.push(key);
                          }
                          versionedRecords.forEach((item) => {
                            const dateKey = new Date(item.date).toISOString().split('T')[0];
                            if (dailyMap.has(dateKey)) {
                              dailyMap.set(dateKey, (dailyMap.get(dateKey) || 0) + 1);
                            }
                          });
                          return last7Days.map((date) => ({
                            date: new Date(date).toLocaleDateString('vi-VN', { day: 'numeric', month: 'short' }),
                            requests: dailyMap.get(date) || 0,
                          }));
                        })()}
                        margin={{ top: 5, right: 20, left: 0, bottom: 5 }}
                      >
                        <defs>
                          <linearGradient id="colorRequests" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="#06b6d4" stopOpacity={0.4} />
                            <stop offset="95%" stopColor="#06b6d4" stopOpacity={0} />
                          </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                        <XAxis dataKey="date" stroke="#64748b" fontSize={12} />
                        <YAxis stroke="#64748b" fontSize={12} />
                        <Tooltip
                          contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '8px' }}
                          labelStyle={{ color: '#f1f5f9' }}
                        />
                        <Area type="monotone" dataKey="requests" stroke="#06b6d4" fillOpacity={1} fill="url(#colorRequests)" strokeWidth={2} />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                </div>

                {/* Functions Distribution - Pie Chart */}
                <div className="rounded-2xl bg-white/[0.03] backdrop-blur-xl border border-white/[0.05] p-5">
                  <h3 className="text-sm font-semibold text-slate-400 mb-4">Functions Distribution</h3>
                  <div className="h-[250px]">
                    <ResponsiveContainer width="100%" height="100%">
                      <RechartsPieChart>
                        <Pie
                          data={(() => {
                            const funcMap = new Map<string, number>();
                            versionedRecords.forEach((item) => {
                              funcMap.set(item.function, (funcMap.get(item.function) || 0) + 1);
                            });
                            const COLORS = ['#06b6d4', '#8b5cf6', '#f59e0b', '#10b981', '#ef4444', '#ec4899'];
                            return Array.from(funcMap.entries())
                              .sort((a, b) => b[1] - a[1])
                              .slice(0, 6)
                              .map(([name, value], idx) => ({ name, value, fill: COLORS[idx % COLORS.length] }));
                          })()}
                          cx="50%"
                          cy="50%"
                          innerRadius={50}
                          outerRadius={80}
                          paddingAngle={3}
                          dataKey="value"
                        >
                        </Pie>
                        <Tooltip
                          contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '8px' }}
                          labelStyle={{ color: '#f1f5f9' }}
                        />
                        <Legend
                          wrapperStyle={{ fontSize: 11, color: '#94a3b8' }}
                          formatter={(value) => <span className="text-slate-400">{value}</span>}
                        />
                      </RechartsPieChart>
                    </ResponsiveContainer>
                  </div>
                </div>

                {/* Countries Distribution - Bar Chart */}
                <div className="rounded-2xl bg-white/[0.03] backdrop-blur-xl border border-white/[0.05] p-5">
                  <h3 className="text-sm font-semibold text-slate-400 mb-4">Top Countries</h3>
                  <div className="h-[250px]">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart
                        data={(() => {
                          const countryMap = new Map<string, number>();
                          versionedRecords.forEach((item) => {
                            const country = item.country_code || 'Unknown';
                            countryMap.set(country, (countryMap.get(country) || 0) + 1);
                          });
                          return Array.from(countryMap.entries())
                            .sort((a, b) => b[1] - a[1])
                            .slice(0, 8)
                            .map(([country, count]) => ({ country, count }));
                        })()}
                        layout="vertical"
                        margin={{ top: 5, right: 20, left: 30, bottom: 5 }}
                      >
                        <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                        <XAxis type="number" stroke="#64748b" fontSize={12} />
                        <YAxis type="category" dataKey="country" stroke="#64748b" fontSize={11} width={40} />
                        <Tooltip
                          contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '8px' }}
                          labelStyle={{ color: '#f1f5f9' }}
                        />
                        <Bar dataKey="count" fill="#8b5cf6" radius={[0, 4, 4, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </div>

                {/* Health Status - Donut Chart */}
                <div className="rounded-2xl bg-white/[0.03] backdrop-blur-xl border border-white/[0.05] p-5">
                  <h3 className="text-sm font-semibold text-slate-400 mb-4">Health Status</h3>
                  <div className="h-[250px]">
                    <ResponsiveContainer width="100%" height="100%">
                      <RechartsPieChart>
                        <Pie
                          data={[
                            { name: 'Healthy', value: stats.healthyCount, fill: '#10b981' },
                            { name: 'Issues', value: stats.issueCount, fill: '#ef4444' },
                            { name: 'Unknown', value: versionedRecords.length - stats.healthyCount - stats.issueCount, fill: '#64748b' },
                          ].filter(d => d.value > 0)}
                          cx="50%"
                          cy="50%"
                          innerRadius={50}
                          outerRadius={80}
                          paddingAngle={3}
                          dataKey="value"
                        />
                        <Tooltip
                          contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '8px' }}
                          labelStyle={{ color: '#f1f5f9' }}
                        />
                        <Legend
                          wrapperStyle={{ fontSize: 11 }}
                          formatter={(value) => <span className="text-slate-400">{value}</span>}
                        />
                      </RechartsPieChart>
                    </ResponsiveContainer>
                  </div>
                </div>

                {/* Response Time Trend - Line Chart */}
                <div className="rounded-2xl bg-white/[0.03] backdrop-blur-xl border border-white/[0.05] p-5">
                  <h3 className="text-sm font-semibold text-slate-400 mb-4">Avg Response Time (Last 7 Days)</h3>
                  <div className="h-[250px]">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart
                        data={(() => {
                          const dailyResponse = new Map<string, { total: number; count: number }>();
                          const last7Days = [];
                          for (let i = 6; i >= 0; i--) {
                            const d = new Date();
                            d.setDate(d.getDate() - i);
                            const key = d.toISOString().split('T')[0];
                            dailyResponse.set(key, { total: 0, count: 0 });
                            last7Days.push(key);
                          }
                          versionedRecords.forEach((item) => {
                            if (item.response_time_seconds !== null && !Number.isNaN(item.response_time_seconds)) {
                              const dateKey = new Date(item.date).toISOString().split('T')[0];
                              const existing = dailyResponse.get(dateKey);
                              if (existing) {
                                existing.total += item.response_time_seconds;
                                existing.count += 1;
                              }
                            }
                          });
                          return last7Days.map((date) => {
                            const data = dailyResponse.get(date);
                            return {
                              date: new Date(date).toLocaleDateString('vi-VN', { day: 'numeric', month: 'short' }),
                              avgTime: data && data.count > 0 ? +(data.total / data.count).toFixed(2) : 0,
                            };
                          });
                        })()}
                        margin={{ top: 5, right: 20, left: 0, bottom: 5 }}
                      >
                        <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                        <XAxis dataKey="date" stroke="#64748b" fontSize={12} />
                        <YAxis stroke="#64748b" fontSize={12} unit="s" />
                        <Tooltip
                          contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '8px' }}
                          labelStyle={{ color: '#f1f5f9' }}
                          formatter={(value) => [`${value}s`, 'Avg Time']}
                        />
                        <Line type="monotone" dataKey="avgTime" stroke="#f59e0b" strokeWidth={2} dot={{ fill: '#f59e0b', r: 4 }} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              </div>
            )}
          </section>
        )}

        {/* Filters Section */}
        <section className="mb-6 rounded-2xl bg-white/[0.03] backdrop-blur-xl border border-white/[0.05] overflow-hidden">
          {/* Filter Header */}
          <div className="flex items-center justify-between px-5 py-4 border-b border-white/5">
            <button
              onClick={() => setShowFilters(!showFilters)}
              className="flex items-center gap-2 text-sm font-medium text-slate-300 hover:text-white transition-colors cursor-pointer"
            >
              <SlidersHorizontal className="w-4 h-4" />
              Filters
              {activeFilters.length > 0 && (
                <span className="ml-1 px-2 py-0.5 rounded-full bg-blue-500 text-white text-xs font-bold">
                  {activeFilters.length}
                </span>
              )}
              <ChevronDown className={`w-4 h-4 transition-transform ${showFilters ? 'rotate-180' : ''}`} />
            </button>
            <div className="flex items-center gap-3">
              <span className="text-xs text-slate-500 flex items-center gap-1.5">
                <Globe2 className="h-3.5 w-3.5" />
                {pagination ? `${pagination.total.toLocaleString()} total records` : 'Loading...'}
              </span>
            </div>
          </div>

          {/* Active Filter Badges */}
          {activeFilters.length > 0 && (
            <div className="flex flex-wrap items-center gap-2 px-5 py-3 border-b border-white/5 bg-white/[0.02]">
              {activeFilters.map((f) => (
                <FilterBadge key={f.key} label={f.label} value={f.value} onRemove={f.onRemove} />
              ))}
              <button
                onClick={clearAllFilters}
                className="text-xs text-slate-400 hover:text-white transition-colors ml-2 cursor-pointer"
              >
                Clear all
              </button>
            </div>
          )}

          {/* Filter Controls */}
          {showFilters && (
            <div className="p-5 space-y-4">
              {/* Row 1: Search + Dropdowns */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
                {/* Search */}
                <div className="relative">
                  <Search className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
                  <input
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder="Search devices, results..."
                    className="w-full pl-10 pr-4 py-2.5 bg-slate-900/50 border border-white/10 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500/50 transition-all"
                  />
                </div>

                {/* Function */}
                <div className="relative">
                  <select
                    value={functionFilter}
                    onChange={(e) => setFunctionFilter(e.target.value)}
                    className="w-full appearance-none px-4 py-2.5 pr-10 bg-slate-900/50 border border-white/10 rounded-xl text-white focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500/50 transition-all cursor-pointer"
                  >
                    <option value="all">All Functions</option>
                    {functions.map((f) => (
                      <option key={f} value={f}>{f} ({functionCounts.get(f) ?? 0})</option>
                    ))}
                  </select>
                  <ChevronDown className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
                </div>

                {/* Version */}
                <div className="relative">
                  <select
                    value={appVersionFilter}
                    onChange={(e) => setAppVersionFilter(e.target.value)}
                    className="w-full appearance-none px-4 py-2.5 pr-10 bg-slate-900/50 border border-white/10 rounded-xl text-white focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500/50 transition-all cursor-pointer"
                  >
                    <option value="all">All Versions</option>
                    {appVersions.map((v) => (
                      <option key={v} value={v}>{v}</option>
                    ))}
                  </select>
                  <ChevronDown className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
                </div>

                {/* Country */}
                <div className="relative">
                  <select
                    value={countryFilter}
                    onChange={(e) => setCountryFilter(e.target.value)}
                    className="w-full appearance-none px-4 py-2.5 pr-10 bg-slate-900/50 border border-white/10 rounded-xl text-white focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500/50 transition-all cursor-pointer"
                  >
                    <option value="all">All Countries</option>
                    {countries.map((c) => (
                      <option key={c} value={c}>{c}</option>
                    ))}
                  </select>
                  <ChevronDown className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
                </div>
              </div>

              {/* Row 2: Date filters + Actions */}
              <div className="flex flex-wrap items-center gap-4">
                {/* Quick presets */}
                <QuickDatePresets onSelect={handleDatePreset} activePreset={activePreset} />

                <div className="h-6 w-px bg-white/10" />

                {/* Custom dates */}
                <div className="flex items-center gap-2">
                  <Calendar className="w-4 h-4 text-slate-500" />
                  <input
                    type="date"
                    value={dateFrom}
                    onChange={(e) => { setDateFrom(e.target.value); setActivePreset(null); }}
                    className="px-3 py-2 bg-slate-900/50 border border-white/10 rounded-lg text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500/50"
                  />
                  <span className="text-slate-500">→</span>
                  <input
                    type="date"
                    value={dateTo}
                    onChange={(e) => { setDateTo(e.target.value); setActivePreset(null); }}
                    className="px-3 py-2 bg-slate-900/50 border border-white/10 rounded-lg text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500/50"
                  />
                </div>

                <div className="flex-1" />

                {/* Export */}
                <button
                  onClick={handleExportCsv}
                  disabled={filteredRecords.length === 0}
                  className="btn-glass disabled:opacity-50 cursor-pointer"
                >
                  <Download className="h-4 w-4" />
                  Export CSV
                </button>
              </div>
            </div>
          )}
        </section>

        {/* Data Table */}
        <section className="rounded-2xl bg-white/[0.03] backdrop-blur-xl border border-white/[0.05] overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-900/50 text-xs uppercase tracking-wider text-slate-500 sticky top-0">
                <tr>
                  <th className="px-4 py-4 text-left font-semibold">Date</th>
                  <th className="px-4 py-4 text-left font-semibold">Function</th>
                  <th className="px-4 py-4 text-left font-semibold">Result</th>
                  <th className="px-4 py-4 text-left font-semibold">Health</th>
                  <th className="px-4 py-4 text-left font-semibold">Response</th>
                  <th className="px-4 py-4 text-left font-semibold">Version</th>
                  <th className="px-4 py-4 text-left font-semibold">Platform</th>
                  <th className="px-4 py-4 text-left font-semibold">Country</th>
                  <th className="px-4 py-4 text-left font-semibold">Image</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {loading && [...Array(10)].map((_, i) => <SkeletonRow key={i} />)}

                {!loading && error && (
                  <tr>
                    <td colSpan={9} className="px-4 py-12 text-center">
                      <div className="text-rose-400 mb-2">{error}</div>
                      <button onClick={fetchTracking} className="text-blue-400 hover:text-blue-300 text-sm cursor-pointer">
                        Try again
                      </button>
                    </td>
                  </tr>
                )}

                {!loading && !error && filteredRecords.length === 0 && (
                  <tr>
                    <td colSpan={9} className="px-4 py-16 text-center">
                      <div className="flex flex-col items-center gap-3">
                        <div className="w-16 h-16 rounded-full bg-slate-800/50 flex items-center justify-center">
                          <Search className="w-6 h-6 text-slate-500" />
                        </div>
                        <p className="text-slate-400">No records found</p>
                        {activeFilters.length > 0 && (
                          <button onClick={clearAllFilters} className="text-blue-400 hover:text-blue-300 text-sm cursor-pointer">
                            Clear all filters
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                )}

                {!loading && !error && paginatedRecords.map((item, index) => {
                  const health = getHealthLabel(item.is_plant_healthy ?? null);
                  const platform = getPlatformLabel(item.device_id);
                  const dateParts = getDateParts(item.date);
                  return (
                    <tr
                      key={`${item.device_id}-${index}`}
                      className="group hover:bg-white/[0.03] transition-colors"
                      style={{ animationDelay: `${index * 20}ms` }}
                    >
                      <td className="px-4 py-3.5">
                        <p className="font-medium text-white">{dateParts.time}</p>
                        <p className="text-xs text-slate-500">{dateParts.date}</p>
                      </td>
                      <td className="px-4 py-3.5">
                        <span className="inline-flex px-2.5 py-1 rounded-lg bg-cyan-500/15 text-cyan-400 text-xs font-medium ring-1 ring-cyan-500/20">
                          {item.function}
                        </span>
                      </td>
                      <td className="px-4 py-3.5">
                        <p className="max-w-[200px] truncate text-slate-300" title={item.result}>
                          {item.result || '—'}
                        </p>
                      </td>
                      <td className="px-4 py-3.5">
                        <span className={`inline-flex px-2.5 py-1 rounded-lg text-xs font-medium ring-1 ${health.tone}`}>
                          {health.label}
                        </span>
                      </td>
                      <td className="px-4 py-3.5 text-slate-400 font-mono text-xs">
                        {formatResponseTime(item.response_time_seconds)}
                      </td>
                      <td className="px-4 py-3.5">
                        <span className="inline-flex px-2 py-1 rounded-md bg-slate-700/50 text-slate-300 text-xs">
                          {item.app_version}
                        </span>
                      </td>
                      <td className="px-4 py-3.5">
                        <span className={`inline-flex px-2.5 py-1 rounded-lg text-xs font-medium ${platform.tone}`}>
                          {platform.label}
                        </span>
                      </td>
                      <td className="px-4 py-3.5 text-slate-400">{item.country_code || '—'}</td>
                      <td className="px-4 py-3.5">
                        {item.image_url ? (
                          <button
                            onClick={() => setPreviewImage(item.image_url)}
                            className="group/img relative w-10 h-10 rounded-lg overflow-hidden bg-slate-800 ring-1 ring-white/10 hover:ring-blue-500/50 transition-all cursor-pointer"
                          >
                            <img
                              src={item.image_url}
                              alt="Preview"
                              className="w-full h-full object-cover"
                              onError={(e) => {
                                (e.target as HTMLImageElement).style.display = 'none';
                              }}
                            />
                            <div className="absolute inset-0 bg-black/60 opacity-0 group-hover/img:opacity-100 transition flex items-center justify-center">
                              <ImageIcon className="w-4 h-4 text-white" />
                            </div>
                          </button>
                        ) : (
                          <span className="text-slate-600">—</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {!loading && !error && filteredRecords.length > 0 && (
            <Pagination
              currentPage={currentPage}
              totalPages={totalPages}
              totalItems={filteredRecords.length}
              itemsPerPage={itemsPerPage}
              onPageChange={setCurrentPage}
              onItemsPerPageChange={setItemsPerPage}
            />
          )}
        </section>
      </div>

      {/* Image Preview Modal */}
      {previewImage && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/90 backdrop-blur-xl p-4"
          onClick={() => setPreviewImage(null)}
        >
          <div className="relative max-w-4xl max-h-[90vh] animate-scale-in">
            <button
              onClick={() => setPreviewImage(null)}
              className="absolute -top-12 right-0 p-2 text-white/70 hover:text-white transition cursor-pointer"
            >
              <X className="w-6 h-6" />
            </button>
            <img
              src={previewImage}
              alt="Full preview"
              className="max-w-full max-h-[85vh] rounded-2xl shadow-2xl ring-1 ring-white/10"
              onClick={(e) => e.stopPropagation()}
            />
          </div>
        </div>
      )}

      {/* Custom styles */}
      <style jsx global>{`
        .btn-primary {
          display: inline-flex;
          align-items: center;
          gap: 0.5rem;
          padding: 0.625rem 1.25rem;
          background: linear-gradient(135deg, #3b82f6, #2563eb);
          color: white;
          font-size: 0.875rem;
          font-weight: 500;
          border-radius: 0.75rem;
          transition: all 0.2s;
          box-shadow: 0 4px 12px rgba(59, 130, 246, 0.25);
        }
        .btn-primary:hover {
          transform: translateY(-1px);
          box-shadow: 0 6px 20px rgba(59, 130, 246, 0.35);
        }
        .btn-primary:disabled {
          opacity: 0.5;
          cursor: not-allowed;
          transform: none;
        }
        .btn-glass {
          display: inline-flex;
          align-items: center;
          gap: 0.5rem;
          padding: 0.625rem 1.25rem;
          background: rgba(255, 255, 255, 0.05);
          backdrop-filter: blur(12px);
          color: #e2e8f0;
          font-size: 0.875rem;
          font-weight: 500;
          border-radius: 0.75rem;
          border: 1px solid rgba(255, 255, 255, 0.1);
          transition: all 0.2s;
        }
        .btn-glass:hover {
          background: rgba(255, 255, 255, 0.1);
          border-color: rgba(255, 255, 255, 0.2);
          color: white;
        }
        .glass-card {
          background: rgba(255, 255, 255, 0.03);
          backdrop-filter: blur(20px);
          border: 1px solid rgba(255, 255, 255, 0.05);
          border-radius: 1rem;
        }
      `}</style>
    </div>
  );
}
