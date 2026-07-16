import { createServerClient } from '@supabase/ssr'
import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

// 需要保护的路由（未登录时重定向到登录页）
const protectedRoutes = ['/', '/admin']
// 不需要保护的路由（已登录时可访问）
const authRoutes = ['/login', '/register']

export async function middleware(request: NextRequest) {
  let supabaseResponse = NextResponse.next({
    request,
  })

  const pathname = request.nextUrl.pathname

  // 1. 检查是否存在本地 Mock 登录 Cookie
  const mockUserRole = request.cookies.get('mock-user-role')?.value
  if (mockUserRole) {
    // 如果用户已登录且访问的是登录/注册页面，重定向到首页
    if (authRoutes.includes(pathname)) {
      const url = request.nextUrl.clone()
      url.pathname = '/'
      return NextResponse.redirect(url)
    }

    // 处理 API 路由
    if (pathname.startsWith('/api/')) {
      const requestHeaders = new Headers(request.headers)
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

    return supabaseResponse
  }

  // 2. 如果没有 Mock Cookie，尝试使用 Supabase（带超时保护）
  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return request.cookies.getAll()
        },
        setAll(cookiesToSet) {
          cookiesToSet.forEach(({ name, value }) => request.cookies.set(name, value))
          supabaseResponse = NextResponse.next({
            request,
          })
          cookiesToSet.forEach(({ name, value, options }) =>
            supabaseResponse.cookies.set(name, value, options)
          )
        },
      },
    }
  )

  // 刷新 session（如果过期），带 2.5s 超时保护
  let user = null
  try {
    const userPromise = supabase.auth.getUser()
    const timeoutPromise = new Promise((_, reject) =>
      setTimeout(() => reject(new Error('Supabase timeout')), 2500)
    )
    const { data } = await Promise.race([userPromise, timeoutPromise]) as any
    user = data?.user
  } catch (err) {
    console.warn('Supabase auth check timed out or failed, treating as guest:', err)
  }

  // 如果用户未登录且访问的是需要保护的路由
  if (!user && protectedRoutes.includes(pathname)) {
    const url = request.nextUrl.clone()
    url.pathname = '/login'
    return NextResponse.redirect(url)
  }

  // 如果用户已登录且访问的是登录/注册页面，重定向到首页
  if (user && authRoutes.includes(pathname)) {
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

  return supabaseResponse
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
