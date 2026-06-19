import { NextRequest, NextResponse } from 'next/server';

const BACKEND = process.env.BACKEND_URL || 'http://localhost:8000';

/**
 * 代理所有 /api/* 请求到后端，支持 SSE 流式响应。
 * Next.js rewrites 会缓存 SSE 事件，导致流式输出卡住，
 * 因此使用自定义 Route Handler 透传。
 */
async function proxy(request: NextRequest, path: string[]) {
  const target = `${BACKEND}/api/${path.join('/')}`;

  const headers = new Headers();
  headers.set('Content-Type', 'application/json');

  // 从服务端环境变量注入 API Key
  const apiKey = process.env.API_KEY;
  if (apiKey) {
    headers.set('X-API-Key', apiKey);
  }

  const init: RequestInit = {
    method: request.method,
    headers,
  };

  // GET/DELETE 不带 body
  if (request.method !== 'GET' && request.method !== 'DELETE') {
    init.body = await request.text();
  }

  try {
    const res = await fetch(target, init);

    // 流式响应：直接透传 ReadableStream
    const contentType = res.headers.get('content-type') || '';
    if (contentType.includes('text/event-stream')) {
      return new Response(res.body, {
        status: res.status,
        headers: {
          'Content-Type': 'text/event-stream',
          'Cache-Control': 'no-cache, no-transform',
          'Connection': 'keep-alive',
          'X-Accel-Buffering': 'no',  // 告诉 nginx 不要缓冲
        },
      });
    }

    // 普通响应
    const data = await res.text();
    return new NextResponse(data, {
      status: res.status,
      headers: { 'Content-Type': 'application/json' },
    });
  } catch (error) {
    console.error('[API Proxy]', error);
    return NextResponse.json(
      { detail: 'Backend service unavailable' },
      { status: 502 }
    );
  }
}

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path } = await params;
  return proxy(request, path);
}

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path } = await params;
  return proxy(request, path);
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path } = await params;
  return proxy(request, path);
}
