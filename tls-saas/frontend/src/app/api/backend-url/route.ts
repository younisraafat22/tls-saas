import { NextResponse } from "next/server";

/**
 * GET /api/backend-url
 *
 * Returns the current backend API URL so desktop clients can discover the
 * active Cloudflare tunnel without needing a rebuild.  The desktop app calls
 * this stable Vercel endpoint before performing any licence-verification or
 * monitoring requests.
 */
export async function GET() {
  const url = process.env.NEXT_PUBLIC_API_URL || "";
  return NextResponse.json({ url });
}
