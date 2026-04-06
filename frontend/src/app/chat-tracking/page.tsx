'use client';

import { useEffect, useMemo, useState, useCallback } from 'react';
import Link from 'next/link';
import {
  ArrowLeft,
  BarChart3,
  Clock3,
  Download,
  Globe2,
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
  MessageSquare,
  Bot
} from 'lucide-react';
import {
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
import { apiClient, ChatTrackingItem, ChatTrackingResponse, ChatSummaryResponse } from '@/lib/api-client';

// ==================== UTILITIES ====================

const formatDateTime = (value: string) => {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat('vi-VN', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date);
};

const formatResponseTime = (value: number | null) => {
  if (value === null || Number.isNaN(value)) return '--';
  return `${value.toFixed(2)}s`;
};

const getStatusLabel = (value: string | null) => {
  if (value === 'success') return { label: 'Success', tone: 'bg-emerald-500/20 text-emerald-400 ring-emerald-500/30' };
  if (value === 'upstream_error' || value === 'proxy_error') return { label: 'Error', tone: 'bg-rose-500/20 text-rose-400 ring-rose-500/30' };
  if (value === 'client_aborted') return { label: 'Aborted', tone: 'bg-amber-500/20 text-amber-400 ring-amber-500/30' };
  return { label: value || 'Unknown', tone: 'bg-slate-700/50 text-slate-400 ring-slate-600/30' };
};

const getPlatformLabel = (platform: string | null | undefined) => {
  if (!platform) return { label: 'Unknown', tone: 'bg-slate-700/50 text-slate-400' };
  const normalized = platform.toLowerCase();
  if (normalized === 'android') {
    return { label: 'Android', tone: 'bg-emerald-500/20 text-emerald-400' };
  }
  if (normalized === 'ios') {
    return { label: 'iOS', tone: 'bg-indigo-500/20 text-indigo-400' };
  }
  return { label: platform, tone: 'bg-slate-700/50 text-slate-400' };
};

const formatCsvValue = (value: string | number | boolean | null | undefined) => {
  if (value === null || value === undefined) return '';
  const stringValue = String(value);
  if (stringValue.includes(',') || stringValue.includes('"') || stringValue.includes('\n')) {
    return `"${stringValue.replace(/"/g, '""')}"`;
  }
  return stringValue;
};

// ==================== COMPONENTS ====================

type ColorType = 'blue' | 'indigo' | 'emerald' | 'amber';

const COLOR_STYLES: Record<ColorType, { bg: string, text: string, ring: string, shadow: string }> = {
  blue: { bg: 'bg-blue-500/10', text: 'text-blue-400', ring: 'ring-blue-500/20', shadow: 'shadow-[0_0_15px_rgba(59,130,246,0.1)]' },
  indigo: { bg: 'bg-indigo-500/10', text: 'text-indigo-400', ring: 'ring-indigo-500/20', shadow: 'shadow-[0_0_15px_rgba(99,102,241,0.1)]' },
  emerald: { bg: 'bg-emerald-500/10', text: 'text-emerald-400', ring: 'ring-emerald-500/20', shadow: 'shadow-[0_0_15px_rgba(16,185,129,0.1)]' },
  amber: { bg: 'bg-amber-500/10', text: 'text-amber-400', ring: 'ring-amber-500/20', shadow: 'shadow-[0_0_15px_rgba(245,158,11,0.1)]' },
};

const StatCard = ({ icon: Icon, label, value, subtext, color }: { icon: React.ElementType, label: string, value: string | number, subtext?: string, color: ColorType }) => {
  const styles = COLOR_STYLES[color] || COLOR_STYLES.blue;
  return (
    <div className="glass-panel p-5 relative overflow-hidden group">
      <div className={`absolute top-0 right-0 w-24 h-24 ${styles.bg} rounded-bl-full -mr-4 -mt-4 transition-transform group-hover:scale-110`} />
      <div className="flex items-start justify-between relative z-10">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.15em] text-slate-500">{label}</p>
          <p className="text-3xl font-bold text-white mt-2 mb-1 tracking-tight">{value}</p>
          {subtext && <p className="text-xs text-slate-400 font-medium">{subtext}</p>}
        </div>
        <div className={`p-3 rounded-xl ${styles.bg} ${styles.text} ring-1 ${styles.ring} ${styles.shadow}`}>
          <Icon size={24} strokeWidth={2} />
        </div>
      </div>
    </div>
  );
};

const PaginationButton = ({ onClick, disabled, children, active = false }: { onClick: () => void, disabled?: boolean, children: React.ReactNode, active?: boolean }) => (
  <button
    onClick={onClick}
    disabled={disabled}
    className={`
      flex items-center justify-center w-8 h-8 rounded-lg text-sm font-medium transition-all
      ${active
        ? 'bg-blue-600 text-white shadow-[0_0_10px_rgba(37,99,235,0.3)] ring-1 ring-blue-500'
        : 'text-slate-400 hover:text-white hover:bg-slate-800 disabled:opacity-30 disabled:hover:bg-transparent disabled:cursor-not-allowed'
      }
    `}
  >
    {children}
  </button>
);

const FilterBadge = ({ label, value, onRemove }: { label: string, value: string, onRemove: () => void }) => {
  if (!value) return null;
  return (
    <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-slate-800/80 text-xs text-slate-300 ring-1 ring-slate-700/50">
      <span className="text-slate-500">{label}:</span>
      <span className="font-medium text-slate-200">{value}</span>
      <button onClick={onRemove} className="ml-1 text-slate-500 hover:text-rose-400 transition-colors">
        <X size={12} />
      </button>
    </div>
  );
};

// ==================== MAIN COMPONENT ====================

export default function ChatTrackingPage() {
  const [records, setRecords] = useState<ChatTrackingItem[]>([]);
  const [pagination, setPagination] = useState<ChatTrackingResponse['pagination'] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [summary, setSummary] = useState<ChatSummaryResponse | null>(null);

  // Filters & State
  const [page, setPage] = useState(1);
  const [limit, setLimit] = useState(100);
  const [searchSessionId, setSearchSessionId] = useState('');
  const [appliedSessionId, setAppliedSessionId] = useState('');

  // Date filters
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [appliedStartDate, setAppliedStartDate] = useState('');
  const [appliedEndDate, setAppliedEndDate] = useState('');

  // UI State
  const [showFilters, setShowFilters] = useState(false);
  const [activeTab, setActiveTab] = useState<'table' | 'analytics'>('table');

  const fetchTracking = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await apiClient.getChatTracking(page, limit, appliedSessionId || undefined);
      setRecords(response.data);
      setPagination(response.pagination);
    } catch (err: any) {
      console.error('Error fetching chat tracking data:', err);
      setError(err.message || 'Failed to fetch tracking data. Please try again.');
    } finally {
      setLoading(false);
    }
  }, [page, limit, appliedSessionId]);

  const fetchSummary = useCallback(async () => {
    try {
      const response = await apiClient.getChatSummary(
        appliedStartDate ? new Date(appliedStartDate).toISOString() : undefined,
        appliedEndDate ? new Date(appliedEndDate).toISOString() : undefined
      );
      setSummary(response);
    } catch (err: any) {
      console.error('Error fetching chat summary data:', err);
    }
  }, [appliedStartDate, appliedEndDate]);

  useEffect(() => {
    fetchTracking();
  }, [fetchTracking]);

  useEffect(() => {
    if (activeTab === 'analytics') {
      fetchSummary();
    }
  }, [activeTab, fetchSummary]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setAppliedSessionId(searchSessionId);
    setPage(1);
  };

  const handleApplyDateFilter = () => {
    setAppliedStartDate(startDate);
    setAppliedEndDate(endDate);
    if (activeTab === 'analytics') {
      fetchSummary();
    }
  };

  const handleClearFilters = () => {
    setSearchSessionId('');
    setAppliedSessionId('');
    setStartDate('');
    setEndDate('');
    setAppliedStartDate('');
    setAppliedEndDate('');
    setPage(1);
  };

  const handleExportCsv = async () => {
    try {
      setLoading(true);
      let allRecords: ChatTrackingItem[] = [];
      let currentPage = 1;
      let totalPages = 1;

      do {
        const response = await apiClient.getChatTracking(currentPage, 500, appliedSessionId || undefined);
        allRecords = [...allRecords, ...response.data];
        totalPages = response.pagination.total_pages;
        currentPage++;
      } while (currentPage <= totalPages);

      const headers = [
        'Time',
        'Session ID',
        'User ID',
        'Device ID',
        'Country',
        'Platform',
        'App Version',
        'Model',
        'Endpoint Type',
        'Status',
        'Has Image',
        'Response Time (s)',
        'User Chat',
        'Bot Response'
      ];

      const csvContent = [
        headers.join(','),
        ...allRecords.map(r => [
          formatCsvValue(r.time),
          formatCsvValue(r.session_id),
          formatCsvValue(r.user_id),
          formatCsvValue(r.device_id),
          formatCsvValue(r.country_id),
          formatCsvValue(r.platform),
          formatCsvValue(r.app_version),
          formatCsvValue(r.model),
          formatCsvValue(r.endpoint_type),
          formatCsvValue(r.status),
          formatCsvValue(r.has_image),
          formatCsvValue(r.time_response_seconds),
          formatCsvValue(r.user_chat),
          formatCsvValue(r.bot_response),
        ].join(','))
      ].join('\n');

      const blob = new Blob(['\ufeff' + csvContent], { type: 'text/csv;charset=utf-8;' });
      const link = document.createElement('a');
      const url = URL.createObjectURL(blob);
      link.setAttribute('href', url);
      link.setAttribute('download', `chat-tracking-${new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-')}.csv`);
      link.style.visibility = 'hidden';
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    } catch (err: any) {
      console.error('Export error:', err);
      alert('Export failed: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4'];

  return (
    <div className="min-h-screen bg-slate-950 bg-[url('/grid.svg')] bg-center bg-fixed">
      {/* HEADER */}
      <header className="sticky top-0 z-40 w-full border-b border-slate-800/60 bg-slate-950/80 backdrop-blur-xl supports-[backdrop-filter]:bg-slate-950/60">
        <div className="container mx-auto px-4 h-16 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link href="/" className="p-2 rounded-full hover:bg-slate-800 text-slate-400 hover:text-white transition-colors">
              <ArrowLeft size={20} />
            </Link>
            <div>
              <div className="flex items-center gap-2 mb-1">
                <span className="px-2 py-0.5 rounded-md bg-blue-500/20 text-blue-400 text-[10px] font-bold uppercase tracking-wider">Analytics</span>
              </div>
              <h1 className="text-2xl font-bold text-white md:text-3xl tracking-tight">Chat Tracking Dashboard</h1>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <button onClick={handleExportCsv} disabled={loading || records.length === 0} className="btn-secondary hidden sm:flex">
              <Download size={16} className="mr-2" />
              Export CSV
            </button>
            <button onClick={fetchTracking} disabled={loading} className="btn-primary cursor-pointer">
              <RefreshCw size={16} className={`mr-2 ${loading ? 'animate-spin' : ''}`} />
              Refresh
            </button>
          </div>
        </div>
      </header>

      <main className="container mx-auto px-4 py-8">
        {/* TABS */}
        <div className="flex p-1 mb-8 bg-slate-900/50 rounded-xl w-fit border border-slate-800/50">
          <button
            onClick={() => setActiveTab('table')}
            className={`flex items-center px-4 py-2 rounded-lg text-sm font-medium transition-all ${activeTab === 'table' ? 'bg-blue-600 text-white shadow-md' : 'text-slate-400 hover:text-white hover:bg-slate-800/50'}`}
          >
            <Clock3 size={16} className="mr-2" />
            Recent Chats
          </button>
          <button
            onClick={() => setActiveTab('analytics')}
            className={`flex items-center px-4 py-2 rounded-lg text-sm font-medium transition-all ${activeTab === 'analytics' ? 'bg-blue-600 text-white shadow-md' : 'text-slate-400 hover:text-white hover:bg-slate-800/50'}`}
          >
            <BarChart3 size={16} className="mr-2" />
            Analytics Overview
          </button>
        </div>

        {error && (
          <div className="mb-8 p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 flex items-start text-rose-400">
            <div className="mr-3 mt-0.5"><X size={18} /></div>
            <div>
              <h3 className="text-sm font-bold">Error Loading Data</h3>
              <p className="text-sm opacity-80 mt-1">{error}</p>
            </div>
          </div>
        )}

        {/* ANALYTICS TAB */}
        {activeTab === 'analytics' && summary && (
          <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
            {/* Filters for Summary */}
            <div className="glass-panel p-4 mb-6">
              <div className="flex flex-col sm:flex-row gap-4 items-end">
                <div className="w-full sm:w-auto">
                  <label className="block text-xs font-medium text-slate-400 mb-1">Start Date</label>
                  <input
                    type="date"
                    value={startDate}
                    onChange={(e) => setStartDate(e.target.value)}
                    className="w-full px-3 py-2 bg-slate-900/50 border border-slate-700/50 rounded-lg text-sm text-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500/50 transition-all"
                  />
                </div>
                <div className="w-full sm:w-auto">
                  <label className="block text-xs font-medium text-slate-400 mb-1">End Date</label>
                  <input
                    type="date"
                    value={endDate}
                    onChange={(e) => setEndDate(e.target.value)}
                    className="w-full px-3 py-2 bg-slate-900/50 border border-slate-700/50 rounded-lg text-sm text-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500/50 transition-all"
                  />
                </div>
                <button onClick={handleApplyDateFilter} className="btn-secondary w-full sm:w-auto">
                  Apply Dates
                </button>
                {(appliedStartDate || appliedEndDate) && (
                  <button onClick={handleClearFilters} className="text-slate-400 hover:text-white text-sm px-3 py-2">
                    Clear
                  </button>
                )}
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              <StatCard icon={MessageSquare} label="Total Turns" value={summary.total_turns.toLocaleString()} color="blue" />
              <StatCard icon={Bot} label="Total Sessions" value={summary.total_sessions.toLocaleString()} color="indigo" />
              <StatCard icon={Clock3} label="Avg Response Time" value={`${summary.response_time.avg_ms.toFixed(0)} ms`} subtext={`Min: ${summary.response_time.min_ms.toFixed(0)}ms | Max: ${summary.response_time.max_ms.toFixed(0)}ms`} color="emerald" />
              <StatCard icon={ImageIcon} label="Image Usage" value={`${summary.image_usage.with_image}`} subtext={`Without image: ${summary.image_usage.without_image}`} color="amber" />
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-6">
              <div className="glass-panel p-5">
                <h3 className="text-sm font-semibold text-white mb-4 flex items-center">
                  <Globe2 size={16} className="mr-2 text-blue-400" /> Requests by Country
                </h3>
                <div className="h-[300px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={summary.by_country} layout="vertical" margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#334155" horizontal={true} vertical={false} />
                      <XAxis type="number" stroke="#94a3b8" fontSize={12} />
                      <YAxis dataKey="country" type="category" stroke="#94a3b8" fontSize={12} width={60} />
                      <Tooltip contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', color: '#f8fafc', borderRadius: '0.5rem' }} cursor={{ fill: '#1e293b' }} />
                      <Bar dataKey="count" fill="#3b82f6" radius={[0, 4, 4, 0]}>
                        {summary.by_country.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>

              <div className="glass-panel p-5">
                <h3 className="text-sm font-semibold text-white mb-4 flex items-center">
                  <Smartphone size={16} className="mr-2 text-indigo-400" /> Platform Distribution
                </h3>
                <div className="h-[300px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <RechartsPieChart>
                      <Pie data={summary.by_platform} cx="50%" cy="50%" innerRadius={60} outerRadius={100} paddingAngle={5} dataKey="count" nameKey="platform" label={({ name, percent }) => `${name} ${((percent || 0) * 100).toFixed(0)}%`}>
                        {summary.by_platform.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                        ))}
                      </Pie>
                      <Tooltip contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', color: '#f8fafc', borderRadius: '0.5rem' }} />
                      <Legend verticalAlign="bottom" height={36} iconType="circle" wrapperStyle={{ fontSize: '12px', color: '#94a3b8' }} />
                    </RechartsPieChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </div>

             <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-6">
              <div className="glass-panel p-5">
                <h3 className="text-sm font-semibold text-white mb-4 flex items-center">
                  <Bot size={16} className="mr-2 text-blue-400" /> Model Usage
                </h3>
                <div className="h-[300px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={summary.by_model} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#334155" vertical={false} />
                      <XAxis dataKey="model" stroke="#94a3b8" fontSize={12} />
                      <YAxis stroke="#94a3b8" fontSize={12} />
                      <Tooltip contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', color: '#f8fafc', borderRadius: '0.5rem' }} cursor={{ fill: '#1e293b' }} />
                      <Bar dataKey="count" fill="#8b5cf6" radius={[4, 4, 0, 0]}>
                        {summary.by_model.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>

              <div className="glass-panel p-5">
                <h3 className="text-sm font-semibold text-white mb-4 flex items-center">
                  <TrendingUp size={16} className="mr-2 text-rose-400" /> Status Distribution
                </h3>
                <div className="h-[300px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <RechartsPieChart>
                      <Pie data={summary.by_status} cx="50%" cy="50%" innerRadius={60} outerRadius={100} paddingAngle={5} dataKey="count" nameKey="status" label={({ name, percent }) => `${name} ${((percent || 0) * 100).toFixed(0)}%`}>
                        {summary.by_status.map((entry, index) => {
                           let color = COLORS[index % COLORS.length];
                           if(entry.status === 'success') color = '#10b981';
                           if(entry.status === 'upstream_error' || entry.status === 'proxy_error') color = '#ef4444';
                           return <Cell key={`cell-${index}`} fill={color} />;
                        })}
                      </Pie>
                      <Tooltip contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', color: '#f8fafc', borderRadius: '0.5rem' }} />
                      <Legend verticalAlign="bottom" height={36} iconType="circle" wrapperStyle={{ fontSize: '12px', color: '#94a3b8' }} />
                    </RechartsPieChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* TABLE TAB */}
        {activeTab === 'table' && (
          <div className="space-y-4 animate-in fade-in slide-in-from-bottom-4 duration-500">
            {/* Filter Controls */}
            <div className="flex flex-col md:flex-row gap-4 items-center justify-between glass-panel p-3">
              <div className="flex items-center gap-2 w-full md:w-auto">
                <form onSubmit={handleSearch} className="relative w-full md:w-80">
                  <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
                  <input
                    type="text"
                    placeholder="Search by Session ID..."
                    value={searchSessionId}
                    onChange={(e) => setSearchSessionId(e.target.value)}
                    className="w-full pl-9 pr-4 py-2 bg-slate-900/50 border border-slate-700/50 rounded-lg text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500/50 transition-all"
                  />
                  {searchSessionId && (
                    <button type="button" onClick={() => setSearchSessionId('')} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300">
                      <X size={14} />
                    </button>
                  )}
                </form>
              </div>

              <div className="flex items-center gap-4 w-full md:w-auto justify-between md:justify-end">
                <div className="flex items-center gap-2">
                  <span className="text-sm text-slate-400">Rows per page:</span>
                  <select
                    value={limit}
                    onChange={(e) => {
                      setLimit(Number(e.target.value));
                      setPage(1);
                    }}
                    className="bg-slate-900/50 border border-slate-700/50 rounded-lg text-sm text-slate-200 py-1.5 pl-3 pr-8 focus:outline-none focus:ring-2 focus:ring-blue-500/50 appearance-none cursor-pointer"
                  >
                    <option value="50">50</option>
                    <option value="100">100</option>
                    <option value="200">200</option>
                    <option value="500">500</option>
                  </select>
                </div>
              </div>
            </div>

            {/* Active Filters Bar */}
            {(appliedSessionId) && (
              <div className="flex flex-wrap items-center gap-2 p-3 glass-panel border-t-0 rounded-t-none -mt-4 bg-slate-900/30">
                <span className="text-xs font-medium text-slate-500 uppercase tracking-wider mr-1"><Filter size={12} className="inline mr-1" /> Active Filters:</span>
                <FilterBadge label="Session" value={appliedSessionId} onRemove={() => { setAppliedSessionId(''); setSearchSessionId(''); setPage(1); }} />
                <button onClick={handleClearFilters} className="text-xs text-blue-400 hover:text-blue-300 ml-auto font-medium">Clear All</button>
              </div>
            )}

            {/* Data Table */}
            <div className="glass-panel overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse">
                  <thead className="bg-slate-900/50 text-xs uppercase tracking-wider text-slate-500 sticky top-0 z-10">
                    <tr>
                      <th className="px-4 py-4 font-semibold border-b border-slate-800 whitespace-nowrap">Time</th>
                      <th className="px-4 py-4 font-semibold border-b border-slate-800 whitespace-nowrap">Session & User</th>
                      <th className="px-4 py-4 font-semibold border-b border-slate-800 whitespace-nowrap">Device / Platform</th>
                      <th className="px-4 py-4 font-semibold border-b border-slate-800 whitespace-nowrap">Chat Summary</th>
                      <th className="px-4 py-4 font-semibold border-b border-slate-800 whitespace-nowrap">Model / Status</th>
                    </tr>
                  </thead>
                  <tbody className="text-sm divide-y divide-slate-800/50">
                    {loading && records.length === 0 ? (
                      <tr>
                        <td colSpan={5} className="px-4 py-12 text-center text-slate-400">
                          <div className="flex flex-col items-center justify-center">
                            <RefreshCw size={24} className="animate-spin text-blue-500 mb-3" />
                            <p>Loading tracking data...</p>
                          </div>
                        </td>
                      </tr>
                    ) : records.length === 0 ? (
                      <tr>
                        <td colSpan={5} className="px-4 py-12 text-center text-slate-400">
                          <div className="flex flex-col items-center justify-center">
                            <Search size={32} className="text-slate-600 mb-3" />
                            <p className="text-lg font-medium text-slate-300">No records found</p>
                            <p className="mt-1">Try adjusting your search or filters.</p>
                            {(appliedSessionId) && (
                              <button onClick={handleClearFilters} className="mt-4 text-blue-400 hover:text-blue-300 text-sm">
                                Clear all filters
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                    ) : (
                      records.map((record, idx) => {
                        const platLabel = getPlatformLabel(record.platform);
                        const statLabel = getStatusLabel(record.status);

                        return (
                          <tr key={`${record.session_id}-${idx}`} className="hover:bg-slate-800/20 transition-colors group">
                            {/* Time */}
                            <td className="px-4 py-3 align-top whitespace-nowrap">
                              <div className="font-medium text-slate-200">{formatDateTime(record.time)}</div>
                            </td>

                            {/* Session & User */}
                            <td className="px-4 py-3 align-top">
                              {record.session_id ? (
                                <div className="font-mono text-xs text-blue-400 bg-blue-500/10 px-2 py-0.5 rounded border border-blue-500/20 w-fit mb-1 truncate max-w-[200px]" title={record.session_id}>
                                  {record.session_id}
                                </div>
                              ) : (
                                <div className="text-xs text-slate-500 italic mb-1">No session ID</div>
                              )}
                              {record.user_id && (
                                <div className="text-xs text-slate-400 mt-1 truncate max-w-[200px]" title={record.user_id}>User: {record.user_id}</div>
                              )}
                              <div className="flex gap-2 mt-1.5">
                                <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-slate-800 text-slate-300 border border-slate-700">
                                  <Globe2 size={10} className="mr-1" /> {record.country_id || 'N/A'}
                                </span>
                                <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-slate-800 text-slate-300 border border-slate-700">
                                  v{record.app_version || 'N/A'}
                                </span>
                              </div>
                            </td>

                            {/* Device Info */}
                            <td className="px-4 py-3 align-top">
                              <div className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${platLabel.tone} mb-1`}>
                                <Smartphone size={12} className="mr-1" /> {platLabel.label}
                              </div>
                              <div className="text-xs font-mono text-slate-500 truncate max-w-[150px]" title={record.device_id}>
                                {record.device_id?.substring(0, 15)}{record.device_id && record.device_id.length > 15 ? '...' : ''}
                              </div>
                            </td>

                            {/* Chat Details */}
                            <td className="px-4 py-3 align-top max-w-[400px]">
                              <div className="flex flex-col gap-3">
                                {/* User Message */}
                                <div className="flex flex-col items-end">
                                  <div className="text-[10px] font-semibold text-slate-500 uppercase mb-1 flex items-center gap-1">
                                    {record.has_image && <ImageIcon size={10} className="text-blue-400" />}
                                    User
                                  </div>
                                  <div className="text-sm text-slate-200 bg-slate-700/60 px-3 py-2 rounded-2xl rounded-tr-sm border border-slate-600/50 max-w-[90%] max-h-32 overflow-y-auto custom-scrollbar break-words whitespace-pre-wrap shadow-sm">
                                    {record.user_chat}
                                  </div>
                                  {record.img_link && (
                                    <div className="mt-1 text-[10px] text-blue-400">
                                      <a href={record.img_link} target="_blank" rel="noopener noreferrer" className="hover:underline flex items-center">
                                        <ImageIcon size={10} className="mr-1" /> View attached image
                                      </a>
                                    </div>
                                  )}
                                </div>

                                {/* Bot Message */}
                                <div className="flex flex-col items-start">
                                  <div className="text-[10px] font-semibold text-blue-400/80 uppercase mb-1 flex items-center gap-1">
                                    <Bot size={10} /> Bot
                                  </div>
                                  <div className="text-sm text-blue-100 bg-blue-600/20 px-3 py-2 rounded-2xl rounded-tl-sm border border-blue-500/30 max-w-[90%] max-h-32 overflow-y-auto custom-scrollbar break-words whitespace-pre-wrap shadow-sm">
                                    {record.bot_response}
                                  </div>
                                </div>
                              </div>
                            </td>

                            {/* Model & Status */}
                            <td className="px-4 py-3 align-top">
                              <div className="flex flex-col gap-2">
                                <span className={`inline-flex items-center px-2 py-1 rounded-md text-xs font-medium ring-1 w-fit ${statLabel.tone}`}>
                                  {statLabel.label}
                                </span>
                                <div>
                                  <div className="text-xs font-mono text-slate-400 mb-1">{record.model}</div>
                                  <div className="text-[10px] text-slate-500 uppercase">{record.endpoint_type}</div>
                                </div>
                                <div className="text-xs font-medium text-slate-300 flex items-center mt-1">
                                  <Clock3 size={12} className="mr-1 text-slate-500" />
                                  {formatResponseTime(record.time_response_seconds)}
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
              {pagination && pagination.total_pages > 1 && (
                <div className="px-4 py-3 border-t border-slate-800/50 flex flex-col sm:flex-row items-center justify-between gap-4 bg-slate-900/30">
                  <div className="text-sm text-slate-400">
                    Showing <span className="font-medium text-white">{(pagination.page - 1) * pagination.limit + 1}</span> to{' '}
                    <span className="font-medium text-white">{Math.min(pagination.page * pagination.limit, pagination.total)}</span> of{' '}
                    <span className="font-medium text-white">{pagination.total}</span> results
                  </div>

                  <div className="flex items-center gap-1">
                    <PaginationButton onClick={() => setPage(1)} disabled={page === 1}>
                      <ChevronsLeft size={16} />
                    </PaginationButton>
                    <PaginationButton onClick={() => setPage(p => p - 1)} disabled={page === 1}>
                      <ChevronLeft size={16} />
                    </PaginationButton>

                    <div className="flex items-center px-2">
                      <span className="text-sm font-medium text-slate-300">
                        Page {page} <span className="text-slate-500 font-normal">of {pagination.total_pages}</span>
                      </span>
                    </div>

                    <PaginationButton onClick={() => setPage(p => p + 1)} disabled={page >= pagination.total_pages}>
                      <ChevronRight size={16} />
                    </PaginationButton>
                    <PaginationButton onClick={() => setPage(pagination.total_pages)} disabled={page >= pagination.total_pages}>
                      <ChevronsRight size={16} />
                    </PaginationButton>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
