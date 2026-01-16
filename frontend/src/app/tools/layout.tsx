import Link from "next/link";
import { Film, Grid2X2, LineChart } from "lucide-react";

export default function ToolsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="relative min-h-screen overflow-hidden bg-background text-foreground">
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute -top-44 right-[-5%] h-[520px] w-[520px] rounded-full bg-[radial-gradient(circle_at_center,rgba(14,165,233,0.45),transparent_65%)] blur-3xl opacity-80 motion-safe:animate-float-slow" />
        <div className="absolute -bottom-52 left-[-15%] h-[520px] w-[520px] rounded-full bg-[radial-gradient(circle_at_center,rgba(249,115,22,0.35),transparent_60%)] blur-3xl opacity-80 motion-safe:animate-float-medium" />
        <div className="absolute top-1/3 left-[15%] h-[360px] w-[360px] rounded-full bg-[radial-gradient(circle_at_center,rgba(56,189,248,0.3),transparent_65%)] blur-3xl opacity-70 motion-safe:animate-float-slow" />
        <div className="absolute inset-0 bg-[linear-gradient(120deg,rgba(255,255,255,0.88),rgba(255,255,255,0))] opacity-70" />
      </div>

      <div className="relative z-10 mx-auto flex min-h-screen max-w-6xl flex-col px-4 pb-16 pt-10 md:pt-14">
        <nav className="flex flex-wrap items-center justify-between gap-4">
          <Link href="/" className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-gradient-to-br from-sky-500 via-cyan-400 to-orange-400 shadow-lg shadow-sky-200/70">
              <Film className="h-5 w-5 text-white" />
            </div>
            <div>
              <p className="text-xs font-semibold tracking-[0.3em] text-slate-500">
                VIDEO SPEED
              </p>
              <p className="text-xs text-slate-400">Creative Tooling</p>
            </div>
          </Link>

          <div className="flex flex-wrap items-center gap-2 text-xs font-semibold">
            <Link
              href="/"
              className="flex items-center gap-2 rounded-full bg-white/80 px-4 py-2 text-slate-700 shadow-sm ring-1 ring-slate-200 transition hover:-translate-y-0.5"
            >
              <Film className="h-4 w-4" />
              Home
            </Link>
            <Link
              href="/tools"
              aria-current="page"
              className="flex items-center gap-2 rounded-full bg-slate-900 px-4 py-2 text-white shadow-sm transition hover:-translate-y-0.5"
            >
              <Grid2X2 className="h-4 w-4" />
              Tools
            </Link>
            <Link
              href="/tracking"
              className="flex items-center gap-2 rounded-full bg-white/80 px-4 py-2 text-slate-700 shadow-sm ring-1 ring-slate-200 transition hover:-translate-y-0.5"
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
