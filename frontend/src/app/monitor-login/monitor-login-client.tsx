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
  const [status, setStatus] = useState<"idle" | "loading" | "success" | "error">("idle");
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
      setMessage("Đăng nhập thành công. Nhấn tiếp tục để vào trang.");
    } catch (err) {
      setStatus("error");
      setMessage(err instanceof Error ? err.message : "Có lỗi xảy ra.");
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-4 md:p-6">
      {/* Background effects */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden">
        <div className="absolute -top-44 right-[-5%] h-[520px] w-[520px] rounded-full bg-[radial-gradient(circle_at_center,rgba(59,130,246,0.2),transparent_65%)] blur-3xl animate-float" />
        <div className="absolute -bottom-52 left-[-15%] h-[520px] w-[520px] rounded-full bg-[radial-gradient(circle_at_center,rgba(249,115,22,0.15),transparent_60%)] blur-3xl animate-float" style={{ animationDelay: '2s' }} />
      </div>

      <div className="relative z-10 mx-auto max-w-5xl">
        {/* Navigation */}
        <nav className="flex items-center justify-between animate-fade-in">
          <Link
            href="/"
            className="inline-flex items-center gap-2 rounded-lg bg-slate-800 px-4 py-2 text-xs font-semibold text-slate-300 ring-1 ring-slate-700 transition hover:bg-slate-700 cursor-pointer"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to Home
          </Link>
          <span className="rounded-lg bg-slate-800 px-4 py-2 text-xs font-semibold text-slate-400 ring-1 ring-slate-700">
            Secure Access
          </span>
        </nav>

        <main className="mt-12 grid gap-10 lg:grid-cols-[1.1fr_0.9fr]">
          {/* Left section */}
          <section className="space-y-6 animate-fade-up">
            <div className="inline-flex w-fit items-center gap-2 rounded-full bg-emerald-500/20 px-4 py-1 text-xs font-semibold text-emerald-400 ring-1 ring-emerald-500/30">
              <ShieldCheck className="h-4 w-4" />
              Protected zone
            </div>
            <div className="space-y-4">
              <h1 className="text-3xl font-bold text-white md:text-4xl">
                Nhập mật khẩu để truy cập Live Monitor & Tracking.
              </h1>
              <p className="max-w-xl text-base text-slate-400 md:text-lg">
                Khu vực này hiển thị dữ liệu vận hành realtime và analytics. Vui lòng xác thực trước khi tiếp tục.
              </p>
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              {[
                { title: "Live Monitor", description: "Theo dõi log Android realtime." },
                { title: "Tracking Dashboard", description: "Analytics & tracking API." },
              ].map((item) => (
                <div key={item.title} className="card">
                  <p className="text-sm font-semibold text-white">{item.title}</p>
                  <p className="mt-2 text-xs text-slate-500">{item.description}</p>
                </div>
              ))}
            </div>
          </section>

          {/* Right section - Login form */}
          <section className="rounded-2xl bg-slate-900 p-6 ring-1 ring-slate-800 animate-scale-in">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.3em] text-slate-500">
                  Authenticate
                </p>
                <h2 className="mt-2 text-xl font-bold text-white">
                  Nhập mật khẩu quản trị
                </h2>
                <p className="mt-1 text-sm text-slate-500">
                  Phiên sẽ được lưu trong 12 giờ.
                </p>
              </div>
              <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-blue-500/20 text-blue-400">
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
                className="input"
                placeholder="••••••••"
              />
              <button
                type="submit"
                disabled={status === "loading"}
                className="btn-primary w-full py-3 cursor-pointer"
              >
                {status === "loading" ? "Đang xác thực..." : "Mở quyền truy cập"}
              </button>
            </form>

            {initialError && (
              <div className="mt-4 rounded-lg border border-rose-500/30 bg-rose-500/20 px-4 py-3 text-sm text-rose-300">
                <div className="flex items-center gap-3">
                  <AlertCircle className="h-4 w-4" />
                  <span>{initialError}</span>
                </div>
              </div>
            )}

            {message && (
              <div
                className={`mt-4 rounded-lg border px-4 py-3 text-sm ${status === "success"
                    ? "border-emerald-500/30 bg-emerald-500/20 text-emerald-300"
                    : "border-rose-500/30 bg-rose-500/20 text-rose-300"
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

            {status === "success" && (
              <button
                type="button"
                onClick={() => router.replace(from)}
                className="btn-accent mt-4 w-full py-3 cursor-pointer"
              >
                Tiếp tục vào trang
              </button>
            )}
          </section>
        </main>
      </div>
    </div>
  );
}
