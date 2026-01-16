import Link from "next/link";
import {
  Activity,
  Boxes,
  ImageIcon,
  Layers,
  Sparkles,
  Video,
} from "lucide-react";

const tools = [
  {
    title: "Video Export Loop",
    description: "Xuất video FPS cố định theo thời lượng, loop mượt.",
    href: "/tools/video-export",
    icon: Video,
    badge: "Export",
    tone: "from-sky-500 via-blue-500 to-indigo-500",
  },
  {
    title: "Image to WebP",
    description: "Chuyển PNG/JPG sang WebP nhanh, giữ chất lượng.",
    href: "/tools/image-webp",
    icon: ImageIcon,
    badge: "Image",
    tone: "from-emerald-400 via-teal-400 to-sky-500",
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
    tone: "from-slate-700 via-slate-800 to-slate-900",
  },
  {
    title: "API Overview",
    description: "Tổng hợp nhanh các endpoint & preset phổ biến.",
    href: "/tools/overview",
    icon: Layers,
    badge: "Guide",
    tone: "from-cyan-500 via-sky-500 to-blue-500",
  },
];

export default function ToolsPage() {
  return (
    <main className="mt-10 flex-1">
      <header className="space-y-4">
        <div className="inline-flex w-fit items-center gap-2 rounded-full bg-white/70 px-4 py-1 text-xs font-semibold text-slate-600 shadow-sm ring-1 ring-slate-200 motion-safe:animate-fade-in">
          <span className="h-2 w-2 rounded-full bg-gradient-to-r from-sky-500 to-orange-400 motion-safe:animate-pulse-soft" />
          Tool Library
        </div>
        <div className="space-y-2">
          <h1 className="text-4xl font-heading font-semibold text-slate-900 md:text-5xl">
            Bộ công cụ chuyên sâu cho media pipeline.
          </h1>
          <p className="max-w-2xl text-base text-slate-600 md:text-lg">
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
              style={{ animationDelay: `${index * 0.08}s` }}
              className="group relative overflow-hidden rounded-3xl bg-white/80 p-5 shadow-sm ring-1 ring-slate-200 transition-all duration-300 hover:-translate-y-1 hover:shadow-lg motion-safe:animate-fade-up"
            >
              <div
                className={`absolute inset-x-0 top-0 h-[120px] bg-gradient-to-r ${tool.tone} opacity-10 transition-opacity duration-300 group-hover:opacity-20`}
              />
              <div className="relative z-10 flex h-11 w-11 items-center justify-center rounded-2xl bg-white shadow-sm ring-1 ring-slate-200">
                <Icon className="h-5 w-5 text-slate-700" />
              </div>
              <span className="relative z-10 mt-4 inline-flex w-fit rounded-full bg-slate-900 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.2em] text-white">
                {tool.badge}
              </span>
              <h2 className="relative z-10 mt-3 text-lg font-semibold text-slate-900">
                {tool.title}
              </h2>
              <p className="relative z-10 mt-2 text-sm text-slate-600">
                {tool.description}
              </p>
              <div className="relative z-10 mt-4 inline-flex items-center gap-2 text-xs font-semibold text-slate-500 transition group-hover:text-slate-900">
                Mở công cụ
                <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-slate-100 text-slate-500 transition group-hover:bg-slate-900 group-hover:text-white">
                  →
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
            style={{ animationDelay: `${index * 0.12}s` }}
            className="rounded-2xl bg-white/80 p-5 text-sm text-slate-600 shadow-sm ring-1 ring-slate-200 motion-safe:animate-fade-up"
          >
            <p className="text-sm font-semibold text-slate-900">{item.title}</p>
            <p className="mt-2 text-xs text-slate-500">{item.description}</p>
          </div>
        ))}
      </section>
    </main>
  );
}
