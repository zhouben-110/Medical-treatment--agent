'use client'

import { createContext, useContext, useEffect, useState, ReactNode, useCallback } from 'react'
import { useRouter } from 'next/navigation'

// Helper functions for cookies
function setCookie(name: string, value: string, days = 7) {
  const date = new Date()
  date.setTime(date.getTime() + (days * 24 * 60 * 60 * 1000))
  const expires = "; expires=" + date.toUTCString()
  document.cookie = name + "=" + (value || "")  + expires + "; path=/"
}

function deleteCookie(name: string) {
  document.cookie = name +'=; Path=/; Expires=Thu, 01 Jan 1970 00:00:01 GMT;'
}

function getCookie(name: string) {
  const nameEQ = name + "="
  const ca = document.cookie.split(';')
  for(let i=0;i < ca.length;i++) {
    let c = ca[i]
    while (c.charAt(0)==' ') c = c.substring(1,c.length)
    if (c.indexOf(nameEQ) == 0) return c.substring(nameEQ.length,c.length)
  }
  return null
}

export interface User {
  id: string
  email: string
  is_active: boolean
  role: string
  created_at: string
}

export interface Session {
  access_token: string
  token_type: string
  user: User
}

interface AuthContextType {
  user: User | null
  session: Session | null
  role: string | null
  loading: boolean
  signIn: (email: string, password: string) => Promise<{ error: Error | null }>
  signUp: (email: string, password: string) => Promise<{ error: Error | null }>
  signOut: () => Promise<void>
  getAccessToken: () => Promise<string | null>
  refreshRole: () => Promise<void>
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [session, setSession] = useState<Session | null>(null)
  const [role, setRole] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const router = useRouter()

  const fetchUser = useCallback(async (token: string) => {
    try {
      const resp = await fetch('/api/auth/me', {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (resp.ok) {
        const userData = await resp.json()
        setUser(userData)
        setRole(userData.role ?? 'user')
        setSession({
          access_token: token,
          token_type: 'bearer',
          user: userData,
        })
      } else {
        // Token invalid or expired
        deleteCookie('access-token')
        setUser(null)
        setRole(null)
        setSession(null)
      }
    } catch (err) {
      console.error('Fetch user failed:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    const token = getCookie('access-token')
    if (token) {
      // If using mock token offline bypass
      if (token === 'mock-token-admin' || token === 'mock-token-user') {
        const computedRole = token === 'mock-token-admin' ? 'admin' : 'user'
        const mockUser: User = {
          id: `mock-${computedRole}-id`,
          email: `${computedRole}@example.com`,
          is_active: true,
          role: computedRole,
          created_at: new Date().toISOString(),
        }
        setUser(mockUser)
        setRole(computedRole)
        setSession({
          access_token: token,
          token_type: 'bearer',
          user: mockUser,
        })
        setLoading(false)
      } else {
        fetchUser(token)
      }
    } else {
      setLoading(false)
    }
  }, [fetchUser])

  const signIn = async (email: string, password: string) => {
    // offline/mock bypass
    if (email === 'admin@example.com' || email === 'user@example.com') {
      const computedRole = email.startsWith('admin') ? 'admin' : 'user'
      const mockToken = `mock-token-${computedRole}`
      setCookie('access-token', mockToken, 7)
      
      const mockUserObj: User = {
        id: `mock-${computedRole}-id`,
        email: email,
        is_active: true,
        role: computedRole,
        created_at: new Date().toISOString(),
      }
      setUser(mockUserObj)
      setSession({
        access_token: mockToken,
        token_type: 'bearer',
        user: mockUserObj,
      })
      setRole(computedRole)
      router.refresh()
      return { error: null }
    }

    try {
      const resp = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      })
      if (!resp.ok) {
        const data = await resp.json()
        return { error: new Error(data.detail || '登录失败') }
      }
      const data = await resp.json() // Contains access_token, user, etc.
      setCookie('access-token', data.access_token, 7)
      setUser(data.user)
      setRole(data.user.role)
      setSession(data)
      router.refresh()
      return { error: null }
    } catch (err: any) {
      return { error: new Error('网络连接错误。您可以输入本地模拟账户以离线模式登录：\n管理员账户：admin@example.com（密码任意）\n普通账户：user@example.com（密码任意）') }
    }
  }

  const signUp = async (email: string, password: string) => {
    try {
      const resp = await fetch('/api/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      })
      if (!resp.ok) {
        const data = await resp.json()
        return { error: new Error(data.detail || '注册失败') }
      }
      return { error: null }
    } catch (err: any) {
      return { error: err }
    }
  }

  const signOut = async () => {
    deleteCookie('access-token')
    setUser(null)
    setSession(null)
    setRole(null)
    router.push('/login')
    router.refresh()
  }

  const getAccessToken = async () => {
    return getCookie('access-token')
  }

  const refreshRole = async () => {
    const token = getCookie('access-token')
    if (token && token !== 'mock-token-admin' && token !== 'mock-token-user') {
      await fetchUser(token)
    }
  }

  const value = {
    user,
    session,
    role,
    loading,
    signIn,
    signUp,
    signOut,
    getAccessToken,
    refreshRole,
  }

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
