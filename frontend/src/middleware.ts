import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

/**
 * 服务端中间件：将 API Key 从环境变量注入请求头，
 * 避免密钥暴露在前端 JS 包中。
 */
export function middleware(request: NextRequest) {
  const apiKey = process.env.API_KEY;

  if (request.nextUrl.pathname.startsWith('/api/') && apiKey) {
    const requestHeaders = new Headers(request.headers);
    requestHeaders.set('X-API-Key', apiKey);

    return NextResponse.next({
      request: {
        headers: requestHeaders,
      },
    });
  }

  return NextResponse.next();
}

export const config = {
  matcher: '/api/:path*',
};
