import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

const PROTECTED_PATHS = ["/tracking", "/tools/logs"];
const LOGIN_PATH = "/monitor-login";
const PASSWORD = process.env.MONITOR_PASSWORD;

let cachedHash: string | null = null;

const hashValue = async (value: string) => {
  const encoder = new TextEncoder();
  const data = encoder.encode(value);
  const digest = await crypto.subtle.digest("SHA-256", data);
  return Array.from(new Uint8Array(digest))
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
};

const getExpectedHash = async () => {
  if (!PASSWORD) return null;
  if (cachedHash) return cachedHash;
  cachedHash = await hashValue(PASSWORD);
  return cachedHash;
};

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const isProtected = PROTECTED_PATHS.some(
    (path) => pathname === path || pathname.startsWith(`${path}/`)
  );

  if (!isProtected) {
    return NextResponse.next();
  }

  // Build correct redirect URL using forwarded headers (for reverse proxy)
  const forwardedHost = request.headers.get("x-forwarded-host");
  const forwardedProto = request.headers.get("x-forwarded-proto") || "https";
  const host = forwardedHost || request.headers.get("host") || request.nextUrl.host;

  const expectedHash = await getExpectedHash();
  if (!expectedHash) {
    const redirectUrl = `${forwardedProto}://${host}${LOGIN_PATH}?from=${encodeURIComponent(pathname)}&error=missing`;
    return NextResponse.redirect(redirectUrl);
  }

  const cookieValue = request.cookies.get("monitor_access")?.value;
  if (!cookieValue || cookieValue !== expectedHash) {
    const redirectUrl = `${forwardedProto}://${host}${LOGIN_PATH}?from=${encodeURIComponent(pathname)}`;
    return NextResponse.redirect(redirectUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/tracking", "/tracking/:path*", "/tools/logs", "/tools/logs/:path*"],
};
