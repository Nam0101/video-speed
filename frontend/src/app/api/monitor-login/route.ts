import { NextResponse } from "next/server";
import { createHash } from "crypto";

export const runtime = "nodejs";

const hashValue = (value: string) =>
  createHash("sha256").update(value).digest("hex");

export async function POST(request: Request) {
  const password = process.env.MONITOR_PASSWORD;

  if (!password) {
    return NextResponse.json(
      { error: "MONITOR_PASSWORD chưa được cấu hình." },
      { status: 500 }
    );
  }

  const body = await request.json().catch(() => ({}));
  const input = typeof body?.password === "string" ? body.password : "";

  if (!input || input !== password) {
    return NextResponse.json(
      { error: "Mật khẩu không chính xác." },
      { status: 401 }
    );
  }

  const response = NextResponse.json({ ok: true });
  response.cookies.set("monitor_access", hashValue(password), {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    maxAge: 60 * 60 * 12,
    path: "/",
  });
  return response;
}
