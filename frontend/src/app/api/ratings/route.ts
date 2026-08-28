import { NextResponse } from "next/server";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const limit = searchParams.get("limit");
  
  const baseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  const url = limit ? `${baseUrl}/metrics/ratings?limit=${limit}` : `${baseUrl}/metrics/ratings`;
  
  try {
    const res = await fetch(url, { cache: "no-store" });
    if (!res.ok) {
        return NextResponse.json({ error: "HTTP error", status: res.status }, { status: res.status });
    }
    const data = await res.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error("Fetch ratings error:", error);
    return NextResponse.json({ error: "Failed to fetch ratings" }, { status: 500 });
  }
}
