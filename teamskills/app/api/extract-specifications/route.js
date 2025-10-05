import { NextResponse } from 'next/server';

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || process.env.BACKEND_URL || 'http://localhost:8000';
export const runtime = 'nodejs';

export async function POST(req) {
  try {
    const payload = await req.json();
    const url = `${BACKEND_URL.replace(/\/$/, '')}/api/extract-specifications`;
    const backendRes = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    const contentType = backendRes.headers.get('content-type') || '';
    if (!backendRes.ok) {
      const errorPayload = contentType.includes('application/json')
        ? await backendRes.json().catch(() => ({ error: backendRes.statusText }))
        : { error: await backendRes.text().catch(() => backendRes.statusText) };
      return NextResponse.json(
        { success: false, error: errorPayload, status: backendRes.status },
        { status: 502 }
      );
    }

    if (contentType.includes('application/json')) {
      const data = await backendRes.json();
      return NextResponse.json(data, { status: backendRes.status });
    }
    const text = await backendRes.text();
    return new Response(text, { status: backendRes.status, headers: { 'content-type': contentType || 'text/plain' } });
  } catch (error) {
    return NextResponse.json({ success: false, error: error.message }, { status: 500 });
  }
}
