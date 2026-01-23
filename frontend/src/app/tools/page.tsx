import Link from "next/link";
import {
  Activity,
  Boxes,
  ImageIcon,
  Layers,
  Sparkles,
  Video,
  ArrowRight,
  Zap,
  Shield,
  Download,
  Wrench,
  Clock,
  TrendingUp,
} from "lucide-react";

const tools = [
  {
    title: "Video Export Loop",
    description: "Xuất video FPS cố định theo thời lượng, loop mượt mà. Hỗ trợ nhiều preset và format.",
    href: "/tools/video-export",
    icon: Video,
    badge: "Export",
    gradient: "from-blue-500 via-indigo-500 to-purple-600",
    featured: true,
    stats: "1.2k+ exports",
  },
  {
    title: "Image to WebP",
    description: "Chuyển PNG/JPG sang WebP nhanh, giữ chất lượng cao với nhiều tùy chọn nén.",
    href: "/tools/image-webp",
    icon: ImageIcon,
    badge: "Image",
    gradient: "from-emerald-400 via-teal-500 to-cyan-500",
    featured: true,
    stats: "2.5k+ converted",
  },
  {
    title: "Animated WebP",
    description: "GIF, MP4, hoặc chuỗi ảnh thành WebP động.",
    href: "/tools/animated-webp",
    icon: Sparkles,
    badge: "Motion",
    gradient: "from-orange-400 via-rose-500 to-pink-500",
    featured: false,
  },
  {
    title: "Batch Conversion",
    description: "Xử lý hàng loạt, resize, zip chuyên nghiệp.",
    href: "/tools/batch",
    icon: Boxes,
    badge: "Batch",
    gradient: "from-fuchsia-500 via-purple-500 to-indigo-600",
    featured: false,
  },
  {
    title: "Android Logs",
    description: "Theo dõi log Android realtime.",
    href: "/tools/logs",
    icon: Activity,
    badge: "Realtime",
    gradient: "from-green-400 via-emerald-500 to-teal-600",
    featured: false,
  },
  {
    title: "API Overview",
    description: "Endpoint & preset reference cho developers.",
    href: "/tools/overview",
    icon: Layers,
    badge: "Guide",
    gradient: "from-cyan-400 via-blue-500 to-violet-600",
    featured: false,
    fullWidth: true,
  },
];

const stats = [
  { icon: Wrench, value: "6", label: "Tools" },
  { icon: Clock, value: "24/7", label: "Available" },
  { icon: TrendingUp, value: "99.9%", label: "Uptime" },
];

const features = [
  {
    icon: Zap,
    title: "Preset thông minh",
    description: "FPS, width, quality được gợi ý theo use-case.",
  },
  {
    icon: Shield,
    title: "Realtime feedback",
    description: "Thông báo tiến trình rõ ràng, hạn chế lỗi silent fail.",
  },
  {
    icon: Download,
    title: "Ready for batch",
    description: "Tải zip hàng loạt, rename tự động.",
  },
];

export default function ToolsPage() {
  return (
    <main className="text-slate-100">
      {/* Header */}
      <header className="space-y-8 animate-fade-in">
        {/* Badge */}
        <div className="inline-flex items-center gap-2 rounded-full bg-blue-500/10 backdrop-blur-sm px-4 py-2 text-xs font-medium text-blue-400 ring-1 ring-blue-500/20">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75" />
            <span className="relative inline-flex rounded-full h-2 w-2 bg-blue-500" />
          </span>
          Tool Library
        </div>

        {/* Title */}
        <div className="space-y-4">
          <h1 className="text-4xl md:text-5xl lg:text-6xl font-bold tracking-tight">
            <span className="text-white">Bộ công cụ </span>
            <span className="gradient-text-animated">chuyên sâu</span>
            <br />
            <span className="text-slate-400 font-medium text-2xl md:text-3xl lg:text-4xl">
              cho media pipeline của bạn
            </span>
          </h1>
          <p className="max-w-2xl text-base text-slate-500 md:text-lg leading-relaxed">
            Mỗi tool là một workflow hoàn chỉnh: upload, config, xử lý và tải về.
            Được tối ưu cho tốc độ và chất lượng cao nhất.
          </p>
        </div>

        {/* Stats Bar */}
        <div className="stats-bar inline-flex items-center gap-0 px-2 py-2">
          {stats.map((stat, index) => {
            const Icon = stat.icon;
            return (
              <div
                key={stat.label}
                className="stats-item flex items-center gap-3 px-5 py-2"
              >
                <div className="w-9 h-9 rounded-lg bg-blue-500/15 flex items-center justify-center">
                  <Icon className="w-4 h-4 text-blue-400" />
                </div>
                <div>
                  <p className="text-lg font-bold text-white">{stat.value}</p>
                  <p className="text-xs text-slate-500">{stat.label}</p>
                </div>
              </div>
            );
          })}
        </div>
      </header>

      {/* Bento Grid */}
      <section className="mt-12 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-6 gap-4 md:gap-5">
        {tools.map((tool, index) => {
          const Icon = tool.icon;
          const isFeatured = tool.featured;
          const isFullWidth = 'fullWidth' in tool && tool.fullWidth;

          return (
            <Link
              key={tool.title}
              href={tool.href}
              style={{ animationDelay: `${index * 80}ms` }}
              className={`
                group relative rounded-3xl p-6 cursor-pointer animate-fade-up
                gradient-border card-shine
                ${isFeatured ? 'lg:col-span-3 bento-featured neon-glow' : ''}
                ${isFullWidth ? 'lg:col-span-6 md:col-span-2' : ''}
                ${!isFeatured && !isFullWidth ? 'lg:col-span-2' : ''}
                transition-all duration-500 hover:scale-[1.02]
              `}
            >
              {/* Background gradient glow on hover */}
              <div
                className={`absolute -inset-1 rounded-3xl bg-gradient-to-br ${tool.gradient} opacity-0 blur-2xl transition-opacity duration-700 group-hover:opacity-25 -z-10`}
              />

              {/* Content */}
              <div className="relative z-10 h-full flex flex-col">
                {/* Top row: Icon + Badge */}
                <div className="flex items-start justify-between">
                  {/* Icon */}
                  <div
                    className={`
                      tool-icon w-14 h-14 rounded-2xl flex items-center justify-center
                      ${isFeatured
                        ? 'icon-gradient shadow-lg shadow-blue-500/20'
                        : 'bg-white/5 ring-1 ring-white/10 group-hover:ring-white/20'
                      }
                      transition-all duration-300 group-hover:scale-110
                    `}
                  >
                    <Icon
                      className={`w-7 h-7 ${isFeatured ? 'text-white' : 'text-slate-400 group-hover:text-white'} transition-colors duration-300`}
                    />
                  </div>

                  {/* Badge */}
                  <span
                    className={`
                      inline-flex px-3 py-1.5 rounded-full text-[10px] font-semibold uppercase tracking-wider
                      bg-gradient-to-r ${tool.gradient}
                      text-white shadow-lg
                    `}
                  >
                    {tool.badge}
                  </span>
                </div>

                {/* Title & Description */}
                <h2
                  className={`
                    mt-5 font-bold text-white transition-colors duration-300 group-hover:text-blue-400
                    ${isFeatured ? 'text-xl md:text-2xl' : 'text-lg'}
                  `}
                >
                  {tool.title}
                </h2>
                <p
                  className={`
                    mt-2 text-slate-400 leading-relaxed flex-grow
                    ${isFeatured ? 'text-sm md:text-base' : 'text-sm'}
                  `}
                >
                  {tool.description}
                </p>

                {/* Stats (for featured) */}
                {'stats' in tool && tool.stats && (
                  <p className="mt-3 text-xs text-blue-400/80 font-medium">
                    {tool.stats}
                  </p>
                )}

                {/* CTA */}
                <div className="mt-5 flex items-center gap-2 text-sm font-medium text-slate-500 transition-colors duration-300 group-hover:text-blue-400">
                  <span>Mở công cụ</span>
                  <div className="w-7 h-7 rounded-full bg-white/5 flex items-center justify-center transition-all duration-300 group-hover:bg-blue-500 group-hover:translate-x-1 group-hover:shadow-lg group-hover:shadow-blue-500/30">
                    <ArrowRight className="w-4 h-4 text-slate-500 group-hover:text-white transition-colors duration-300" />
                  </div>
                </div>
              </div>
            </Link>
          );
        })}
      </section>

      {/* Features */}
      <section className="mt-12 grid grid-cols-1 md:grid-cols-3 gap-4">
        {features.map((item, index) => {
          const Icon = item.icon;
          return (
            <div
              key={item.title}
              style={{ animationDelay: `${600 + index * 100}ms` }}
              className="glass-card p-5 animate-fade-up hover:border-blue-500/30 transition-colors duration-300"
            >
              <div className="flex items-start gap-4">
                <div className="w-11 h-11 rounded-xl bg-gradient-to-br from-blue-500/20 to-purple-500/10 flex items-center justify-center flex-shrink-0 ring-1 ring-blue-500/20">
                  <Icon className="w-5 h-5 text-blue-400" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-white">{item.title}</p>
                  <p className="mt-1.5 text-xs text-slate-500 leading-relaxed">
                    {item.description}
                  </p>
                </div>
              </div>
            </div>
          );
        })}
      </section>

      {/* Back to home */}
      <div className="mt-12 text-center animate-fade-up" style={{ animationDelay: '900ms' }}>
        <Link
          href="/"
          className="inline-flex items-center gap-2 px-6 py-3 rounded-full bg-white/5 text-slate-400 text-sm font-medium ring-1 ring-white/10 transition-all duration-300 hover:bg-white/10 hover:text-white hover:ring-blue-500/30 cursor-pointer group"
        >
          <ArrowRight className="w-4 h-4 rotate-180 transition-transform duration-300 group-hover:-translate-x-1" />
          Về trang chủ
        </Link>
      </div>
    </main>
  );
}
