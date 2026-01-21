import Link from "next/link";
import { Film, Grid2X2, LineChart } from "lucide-react";

export default function ToolsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="relative min-h-screen bg-[#0a0f1a]">
      {/* Subtle gradient background */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-0 left-1/4 w-[600px] h-[600px] bg-blue-500/[0.03] rounded-full blur-3xl" />
        <div className="absolute bottom-0 right-1/4 w-[600px] h-[600px] bg-violet-500/[0.03] rounded-full blur-3xl" />
      </div>

      <div className="relative z-10 mx-auto max-w-6xl px-4 pb-16 pt-6 md:pt-10">
        {/* Navigation */}
        <nav className="flex flex-wrap items-center justify-between gap-4 mb-8">
          <Link href="/" className="flex items-center gap-3 group">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-blue-500 via-cyan-500 to-orange-400 shadow-lg shadow-blue-500/20 group-hover:shadow-blue-500/30 transition-shadow">
              <Film className="h-5 w-5 text-white" />
            </div>
            <div>
              <p className="text-xs font-semibold tracking-[0.25em] text-slate-500">
                VIDEO SPEED
              </p>
              <p className="text-xs text-slate-600">Creative Tooling</p>
            </div>
          </Link>

          <div className="flex items-center gap-2 text-xs font-medium">
            <Link
              href="/"
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-white/5 text-slate-400 border border-white/10 hover:bg-white/10 hover:text-white transition-all"
            >
              <Film className="h-4 w-4" />
              Home
            </Link>
            <Link
              href="/tools"
              aria-current="page"
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-500 text-white shadow-lg shadow-blue-500/25"
            >
              <Grid2X2 className="h-4 w-4" />
              Tools
            </Link>
            <Link
              href="/tracking"
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-white/5 text-slate-400 border border-white/10 hover:bg-white/10 hover:text-white transition-all"
            >
              <LineChart className="h-4 w-4" />
              Tracking
            </Link>
          </div>
        </nav>

        {children}
      </div>
    </div>
  );
}
