"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import {
  AlertCircle,
  ArrowLeft,
  CheckCircle2,
  Lock,
  ShieldCheck,
} from "lucide-react";

export default function MonitorLoginClient() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const from = searchParams.get("from") || "/tracking";
  const errorFlag = searchParams.get("error");

  const [password, setPassword] = useState("");
  const [status, setStatus] = useState<"idle" | "loading" | "success" | "error">(
    "idle"
  );
  const [message, setMessage] = useState("");

  const initialError = useMemo(() => {
    if (errorFlag === "missing") {
      return "Chưa cấu hình MONITOR_PASSWORD trong môi trường server.";
    }
    return "";
  }, [errorFlag]);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!password) {
      setStatus("error");
      setMessage("Vui lòng nhập mật khẩu.");
      return;
    }

    try {
      setStatus("loading");
      setMessage("");
      const response = await fetch("/api/monitor-login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password }),
      });

      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data?.error || "Mật khẩu không chính xác.");
      }

      setStatus("success");
      setMessage("Đăng nhập thành công. Đang chuyển hướng...");
      setTimeout(() => {
        router.replace(from);
      }, 450);
    } catch (err) {
      setStatus("error");
      setMessage(err instanceof Error ? err.message : "Có lỗi xảy ra.");
    }
  };

  return (
    <div className="relative min-h-screen overflow-hidden bg-background text-foreground">
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute -top-44 right-[-5%] h-[520px] w-[520px] rounded-full bg-[radial-gradient(circle_at_center,rgba(14,165,233,0.45),transparent_65%)] blur-3xl opacity-80 motion-safe:animate-float-slow" />
        <div className="absolute -bottom-52 left-[-15%] h-[520px] w-[520px] rounded-full bg-[radial-gradient(circle_at_center,rgba(249,115,22,0.35),transparent_60%)] blur-3xl opacity-80 motion-safe:animate-float-medium" />
        <div className="absolute inset-0 bg-[linear-gradient(120deg,rgba(255,255,255,0.9),rgba(255,255,255,0))] opacity-70" />
      </div>

      <div className="relative z-10 mx-auto flex min-h-screen max-w-5xl flex-col px-4 pb-16 pt-10 md:pt-16">
        <nav className="flex items-center justify-between">
          <Link
            href="/"
            className="inline-flex items-center gap-2 rounded-full bg-white/80 px-4 py-2 text-xs font-semibold text-slate-700 shadow-sm ring-1 ring-slate-200 transition hover:-translate-y-0.5"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to Home
          </Link>
          <span className="rounded-full bg-white/70 px-4 py-2 text-xs font-semibold text-slate-600 shadow-sm ring-1 ring-slate-200">
            Secure Access
          </span>
        </nav>

        <main className="mt-12 grid gap-10 lg:grid-cols-[1.1fr_0.9fr]">
          <section className="space-y-6">
            <div className="inline-flex w-fit items-center gap-2 rounded-full bg-white/70 px-4 py-1 text-xs font-semibold text-slate-600 shadow-sm ring-1 ring-slate-200 motion-safe:animate-fade-in">
              <ShieldCheck className="h-4 w-4 text-emerald-500" />
              Protected zone
            </div>
            <div className="space-y-4">
              <h1 className="text-4xl font-heading font-semibold text-slate-900 md:text-5xl">
                Nhập mật khẩu để truy cập Live Monitor & Tracking.
              </h1>
              <p className="max-w-xl text-base text-slate-600 md:text-lg">
                Khu vực này hiển thị dữ liệu vận hành realtime và analytics. Vui
                lòng xác thực trước khi tiếp tục.
              </p>
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              {[
                {
                  title: "Live Monitor",
                  description: "Theo dõi log Android realtime.",
                },
                {
                  title: "Tracking Dashboard",
                  description: "Analytics & tracking API.",
                },
              ].map((item) => (
                <div
                  key={item.title}
                  className="rounded-2xl bg-white/80 p-4 text-sm text-slate-600 shadow-sm ring-1 ring-slate-200"
                >
                  <p className="text-sm font-semibold text-slate-900">
                    {item.title}
                  </p>
                  <p className="mt-2 text-xs text-slate-500">
                    {item.description}
                  </p>
                </div>
              ))}
            </div>
          </section>

          <section className="rounded-3xl bg-white/85 p-6 shadow-lg ring-1 ring-slate-200">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">
                  Authenticate
                </p>
                <h2 className="mt-2 text-xl font-heading font-semibold text-slate-900">
                  Nhập mật khẩu quản trị
                </h2>
                <p className="mt-1 text-sm text-slate-500">
                  Phiên sẽ được lưu trong 12 giờ.
                </p>
              </div>
              <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-sky-100 text-sky-600">
                <Lock className="h-5 w-5" />
              </div>
            </div>

            <form onSubmit={handleSubmit} className="mt-6 space-y-4">
              <label className="block text-xs font-semibold uppercase tracking-widest text-slate-500">
                Password
              </label>
              <input
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700 focus:border-slate-400 focus:outline-none"
                placeholder="••••••••"
              />
              <button
                type="submit"
                disabled={status === "loading"}
                className="w-full rounded-2xl bg-slate-900 px-4 py-3 text-sm font-semibold text-white shadow-sm transition hover:-translate-y-0.5 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {status === "loading" ? "Đang xác thực..." : "Mở quyền truy cập"}
              </button>
            </form>

            {initialError && (
              <div className="mt-4 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
                <div className="flex items-center gap-3">
                  <AlertCircle className="h-4 w-4" />
                  <span>{initialError}</span>
                </div>
              </div>
            )}

            {message && (
              <div
                className={`mt-4 rounded-2xl border px-4 py-3 text-sm ${
                  status === "success"
                    ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                    : "border-rose-200 bg-rose-50 text-rose-700"
                }`}
              >
                <div className="flex items-center gap-3">
                  {status === "success" ? (
                    <CheckCircle2 className="h-4 w-4" />
                  ) : (
                    <AlertCircle className="h-4 w-4" />
                  )}
                  <span>{message}</span>
                </div>
              </div>
            )}
          </section>
        </main>
      </div>
    </div>
  );
}
