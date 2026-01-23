import Link from "next/link";
import { ArrowLeft, ExternalLink, ShieldCheck } from "lucide-react";

const endpoints = [
  {
    group: "Video",
    items: [
      { path: "/upload", method: "POST", note: "Upload video lấy file_id" },
      { path: "/convert", method: "POST", note: "Đổi FPS (download mp4)" },
      { path: "/export", method: "POST", note: "Loop export theo duration" },
      { path: "/webm-to-gif", method: "POST", note: "WebM → GIF" },
    ],
  },
  {
    group: "Image",
    items: [
      { path: "/png-to-webp", method: "POST", note: "PNG/JPG → WebP" },
      {
        path: "/images-to-animated-webp",
        method: "POST",
        note: "Ảnh → WebP động",
      },
      {
        path: "/mp4-to-animated-webp",
        method: "POST",
        note: "MP4 → WebP động",
      },
      { path: "/gif-to-webp", method: "POST", note: "GIF → WebP động" },
    ],
  },
  {
    group: "Batch",
    items: [
      { path: "/images-to-webp-zip", method: "POST", note: "Ảnh → WebP ZIP" },
      {
        path: "/images-convert-zip",
        method: "POST",
        note: "Convert ảnh đa format",
      },
      {
        path: "/tgs-to-gif-zip",
        method: "POST",
        note: "TGS → GIF ZIP",
      },
      {
        path: "/batch-animated-resize-zip",
        method: "POST",
        note: "Resize WebP/GIF động",
      },
      {
        path: "/webp-resize-zip",
        method: "POST",
        note: "Resize ảnh tĩnh + target size",
      },
    ],
  },
  {
    group: "Monitoring",
    items: [
      { path: "/api/android-log", method: "GET", note: "Danh sách logs" },
      { path: "/api/android-log", method: "DELETE", note: "Xoá logs" },
      {
        path: "/api/android-log/stream",
        method: "GET",
        note: "SSE realtime logs",
      },
      { path: "/api/analytics/stats", method: "GET", note: "Stats tổng hợp" },
    ],
  },
];

export default function ToolsOverviewPage() {
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
              Reference
            </p>
            <h1 className="text-3xl font-heading font-semibold text-[var(--foreground)] md:text-4xl">
              API Overview
            </h1>
            <p className="mt-1 text-sm text-[var(--muted)]">
              Tổng hợp nhanh endpoint & use-case để team dễ map workflow.
            </p>
          </div>
        </div>
        <span className="rounded-full bg-[var(--secondary)] px-4 py-2 text-xs font-semibold text-[var(--muted)] border border-[var(--border)]">
          Base URL: {process.env.NEXT_PUBLIC_API_URL || "http://localhost:5001"}
        </span>
      </header>

      <section className="mt-8 grid gap-6 md:grid-cols-2">
        {endpoints.map((group, index) => (
          <div
            key={group.group}
            style={{ animationDelay: `${index * 0.08}s` }}
            className="glass-card p-6 motion-safe:animate-fade-up"
          >
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-heading font-semibold text-[var(--foreground)]">
                {group.group}
              </h2>
              <ShieldCheck className="h-5 w-5 text-emerald-400" />
            </div>
            <div className="mt-4 space-y-3 text-sm text-[var(--muted)]">
              {group.items.map((item) => (
                <div
                  key={`${item.method}-${item.path}`}
                  className="flex items-start justify-between gap-3 rounded-2xl bg-[var(--secondary)] px-4 py-3 border border-[var(--border)] transition-colors hover:border-[var(--primary)]/30"
                >
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-widest text-[var(--muted)]">
                      {item.method}
                    </p>
                    <p className="mt-1 font-mono text-sm text-[var(--foreground)]">
                      {item.path}
                    </p>
                    <p className="mt-1 text-xs text-[var(--muted)]">{item.note}</p>
                  </div>
                  <ExternalLink className="mt-1 h-4 w-4 text-[var(--muted)]" />
                </div>
              ))}
            </div>
          </div>
        ))}
      </section>
    </main>
  );
}
