import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

export async function middleware(_request: NextRequest) {
  // Authentication disabled - allow all access
  return NextResponse.next();
}

export const config = {
  matcher: ["/tracking", "/tracking/:path*", "/tools/logs", "/tools/logs/:path*"],
};
