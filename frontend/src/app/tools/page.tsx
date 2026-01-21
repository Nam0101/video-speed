import Link from "next/link";
import {
  Activity,
  Boxes,
  ImageIcon,
  Layers,
  Sparkles,
  Video,
  ArrowRight,
} from "lucide-react";

const tools = [
  {
    title: "Video Export Loop",
    description: "Xuất video FPS cố định theo thời lượng, loop mượt.",
    href: "/tools/video-export",
    icon: Video,
    badge: "Export",
    tone: "from-blue-500 via-cyan-500 to-indigo-500",
  },
  {
    title: "Image to WebP",
    description: "Chuyển PNG/JPG sang WebP nhanh, giữ chất lượng.",
    href: "/tools/image-webp",
    icon: ImageIcon,
    badge: "Image",
    tone: "from-emerald-400 via-teal-400 to-cyan-500",
  },
  {
    title: "Animated WebP Studio",
    description: "GIF, MP4, hoặc chuỗi ảnh thành WebP động.",
    href: "/tools/animated-webp",
    icon: Sparkles,
    badge: "Motion",
    tone: "from-orange-400 via-amber-400 to-rose-400",
  },
  {
    title: "Batch Conversion",
    description: "Xử lý hàng loạt ảnh, sticker, resize, zip.",
    href: "/tools/batch",
    icon: Boxes,
    badge: "Batch",
    tone: "from-fuchsia-500 via-purple-500 to-indigo-500",
  },
  {
    title: "Android Logs",
    description: "Theo dõi log Android theo thời gian thực.",
    href: "/tools/logs",
    icon: Activity,
    badge: "Realtime",
    tone: "from-emerald-500 via-green-500 to-teal-500",
  },
  {
    title: "API Overview",
    description: "Tổng hợp nhanh các endpoint & preset phổ biến.",
    href: "/tools/overview",
    icon: Layers,
    badge: "Guide",
    tone: "from-cyan-500 via-blue-500 to-violet-500",
  },
];

export default function ToolsPage() {
  return (
    <main className="text-slate-100">
      <header className="space-y-4 animate-fade-in">
        <div className="inline-flex w-fit items-center gap-2 rounded-full bg-slate-800 px-4 py-1 text-xs font-semibold text-slate-300 ring-1 ring-slate-700">
          <span className="h-2 w-2 rounded-full bg-gradient-to-r from-blue-500 to-orange-400 animate-pulse" />
          Tool Library
        </div>
        <div className="space-y-2">
          <h1 className="text-4xl font-bold text-white md:text-5xl">
            Bộ công cụ chuyên sâu cho media pipeline.
          </h1>
          <p className="max-w-2xl text-base text-slate-400 md:text-lg">
            Mỗi trang là một workflow đầy đủ: upload, config, xử lý và tải về. Tối ưu
            cho creator, editor và đội vận hành.
          </p>
        </div>
      </header>

      <section className="mt-10 grid gap-5 md:grid-cols-2 lg:grid-cols-3">
        {tools.map((tool, index) => {
          const Icon = tool.icon;
          return (
            <Link
              key={tool.title}
              href={tool.href}
              style={{ animationDelay: `${index * 80}ms` }}
              className="group relative overflow-hidden rounded-2xl bg-slate-900 p-5 ring-1 ring-slate-800 transition-all duration-300 hover:-translate-y-1 hover:ring-blue-500/50 hover-lift cursor-pointer animate-fade-up"
            >
              {/* Gradient overlay */}
              <div
                className={`absolute inset-x-0 top-0 h-[120px] bg-gradient-to-r ${tool.tone} opacity-10 transition-opacity duration-300 group-hover:opacity-25`}
              />

              {/* Icon */}
              <div className="relative z-10 flex h-12 w-12 items-center justify-center rounded-xl bg-slate-800 ring-1 ring-slate-700 transition group-hover:ring-blue-500/50">
                <Icon className="h-6 w-6 text-slate-400 transition group-hover:text-blue-400" />
              </div>

              {/* Badge */}
              <span className="relative z-10 mt-4 inline-flex w-fit rounded-full bg-blue-500/20 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.2em] text-blue-400">
                {tool.badge}
              </span>

              {/* Title & Description */}
              <h2 className="relative z-10 mt-3 text-lg font-semibold text-white">
                {tool.title}
              </h2>
              <p className="relative z-10 mt-2 text-sm text-slate-500">
                {tool.description}
              </p>

              {/* CTA */}
              <div className="relative z-10 mt-4 inline-flex items-center gap-2 text-xs font-semibold text-slate-500 transition group-hover:text-blue-400">
                Mở công cụ
                <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-slate-800 text-slate-500 transition group-hover:bg-blue-500 group-hover:text-white">
                  <ArrowRight className="h-3 w-3" />
                </span>
              </div>
            </Link>
          );
        })}
      </section>

      <section className="mt-12 grid gap-4 md:grid-cols-3">
        {[
          {
            title: "Preset thông minh",
            description: "Các mức FPS, width, quality được gợi ý sẵn theo use-case.",
          },
          {
            title: "Realtime feedback",
            description: "Thông báo tiến trình rõ ràng, hạn chế lỗi silent fail.",
          },
          {
            title: "Ready for batch",
            description: "Tải zip hàng loạt, rename tự động, an toàn.",
          },
        ].map((item, index) => (
          <div
            key={item.title}
            style={{ animationDelay: `${index * 120}ms` }}
            className="card animate-fade-up"
          >
            <p className="text-sm font-semibold text-white">{item.title}</p>
            <p className="mt-2 text-xs text-slate-500">{item.description}</p>
          </div>
        ))}
      </section>

      {/* Back to home */}
      <div className="mt-10 text-center">
        <Link
          href="/"
          className="btn-secondary rounded-full cursor-pointer"
        >
          ← Về trang chủ
        </Link>
      </div>
    </main>
  );
}
