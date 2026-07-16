import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

// 需要保护的路由（未登录时重定向到登录页）
const protectedRoutes = ['/', '/admin']
// 不需要保护的路由（已登录时可访问）
const authRoutes = ['/login', '/register']

export function middleware(request: NextRequest) {
  const pathname = request.nextUrl.pathname
  const token = request.cookies.get('access-token')?.value

  // 如果用户未登录且访问的是需要保护的路由
  if (!token && protectedRoutes.includes(pathname)) {
    const url = request.nextUrl.clone()
    url.pathname = '/login'
    return NextResponse.redirect(url)
  }

  // 如果用户已登录且访问的是登录/注册页面，重定向到首页
  if (token && authRoutes.includes(pathname)) {
    const url = request.nextUrl.clone()
    url.pathname = '/'
    return NextResponse.redirect(url)
  }

  // 处理 API 路由
  if (pathname.startsWith('/api/')) {
    const requestHeaders = new Headers(request.headers)

    // 注入 API Key（向后兼容）
    const apiKey = process.env.API_KEY
    if (apiKey) {
      requestHeaders.set('X-API-Key', apiKey)
    }

    return NextResponse.next({
      request: {
        headers: requestHeaders,
      },
    })
  }

  return NextResponse.next()
}

export const config = {
  matcher: [
    /*
     * 匹配所有请求路径除了：
     * - _next/static（静态文件）
     * - _next/image（图片优化）
     * - favicon.ico（网站图标）
     * - 公共文件（public 目录）
     */
    '/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)',
  ],
}
