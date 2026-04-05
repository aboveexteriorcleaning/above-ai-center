import { createClient } from "@/lib/supabase-server";
import { NextRequest, NextResponse } from "next/server";

export async function POST(req: NextRequest) {
  // Verify Supabase session server-side
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();

  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const body = await req.json();
  if (!body.question || typeof body.question !== "string") {
    return NextResponse.json({ error: "question is required" }, { status: 400 });
  }

  const base = process.env.FASTAPI_URL;
  const key = process.env.DASHBOARD_API_KEY;

  if (!base || !key) {
    return NextResponse.json({ error: "Server configuration error" }, { status: 500 });
  }

  const upstream = await fetch(`${base}/api/query`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": key,
    },
    body: JSON.stringify({ question: body.question }),
  });

  const data = await upstream.json();
  return NextResponse.json(data, { status: upstream.status });
}
