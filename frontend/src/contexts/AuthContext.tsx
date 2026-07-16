'use client'

import { createContext, useContext, useEffect, useState, ReactNode, useCallback, useRef } from 'react'
import { User, Session } from '@supabase/supabase-js'
import { createClient } from '@/lib/supabase'
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
  const supabaseRef = useRef(createClient())
  const supabase = supabaseRef.current

  const fetchRole = useCallback(async () => {
    // If mock cookie is present, return immediately
    const mockRole = getCookie('mock-user-role')
    if (mockRole) {
      setRole(mockRole)
      return
    }

    try {
      const { data: { session: currentSession } } = await supabase.auth.getSession()
      if (!currentSession?.access_token) {
        setRole(null)
        return
      }
      const resp = await fetch('/api/auth/me', {
        headers: { Authorization: `Bearer ${currentSession.access_token}` },
      })
      if (resp.ok) {
        const data = await resp.json()
        setRole(data.role ?? 'user')
      } else {
        setRole(null)
      }
    } catch {
      setRole(null)
    }
  }, [supabase])

  useEffect(() => {
    // 1. Check if mock login is used
    const mockRole = getCookie('mock-user-role')
    if (mockRole) {
      const mockEmail = `${mockRole}@example.com`
      const mockUserObj: User = {
        id: `mock-${mockRole}-id`,
        email: mockEmail,
        aud: 'authenticated',
        role: 'authenticated',
        app_metadata: {},
        user_metadata: {},
        created_at: new Date().toISOString(),
      }
      const mockSessionObj: Session = {
        access_token: `mock-token-${mockRole}`,
        token_type: 'bearer',
        expires_in: 3600,
        refresh_token: 'mock-refresh-token',
        user: mockUserObj,
        expires_at: Math.floor(Date.now() / 1000) + 3600,
      }
      setUser(mockUserObj)
      setSession(mockSessionObj)
      setRole(mockRole)
      setLoading(false)
      return
    }

    // 2. Fallback to Supabase if mock not present
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session)
      setUser(session?.user ?? null)
      setLoading(false)
      if (session) fetchRole()
    }).catch((err) => {
      console.warn('Supabase session load failed:', err)
      setLoading(false)
    })

    // Listen for auth state change
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      async (event, session) => {
        // If we are in mock mode, ignore Supabase auth state change unless they explicitly signed out
        if (getCookie('mock-user-role')) return

        setSession(session)
        setUser(session?.user ?? null)
        setLoading(false)

        if (event === 'SIGNED_IN') {
          await fetchRole()
          router.refresh()
        }
        if (event === 'SIGNED_OUT') {
          setRole(null)
          router.push('/login')
          router.refresh()
        }
      }
    )

    return () => subscription.unsubscribe()
  }, [router, supabase, fetchRole])

  const signIn = async (email: string, password: string) => {
    // If using mock logins (e.g. admin@example.com / user@example.com)
    if (email === 'admin@example.com' || email === 'user@example.com') {
      const computedRole = email.startsWith('admin') ? 'admin' : 'user'
      setCookie('mock-user-role', computedRole, 7)
      setCookie('mock-access-token', `mock-token-${computedRole}`, 7)
      
      const mockUserObj: User = {
        id: `mock-${computedRole}-id`,
        email: email,
        aud: 'authenticated',
        role: 'authenticated',
        app_metadata: {},
        user_metadata: {},
        created_at: new Date().toISOString(),
      }
      const mockSessionObj: Session = {
        access_token: `mock-token-${computedRole}`,
        token_type: 'bearer',
        expires_in: 3600,
        refresh_token: 'mock-refresh-token',
        user: mockUserObj,
        expires_at: Math.floor(Date.now() / 1000) + 3600,
      }
      setUser(mockUserObj)
      setSession(mockSessionObj)
      setRole(computedRole)
      router.refresh()
      return { error: null }
    }

    try {
      const { error } = await supabase.auth.signInWithPassword({
        email,
        password,
      })
      if (error) return { error }
      return { error: null }
    } catch (err: any) {
      // Fallback/offline behavior: If connection failed and email/password are provided, offer offline bypass
      return { error: new Error('网络连接超时。您可以输入本地模拟账户以离线模式登录：\n管理员账户：admin@example.com（密码任意）\n普通账户：user@example.com（密码任意）') }
    }
  }

  const signUp = async (email: string, password: string) => {
    try {
      const { error } = await supabase.auth.signUp({
        email,
        password,
      })
      return { error }
    } catch (err: any) {
      return { error: err }
    }
  }

  const signOut = async () => {
    deleteCookie('mock-user-role')
    deleteCookie('mock-access-token')
    setUser(null)
    setSession(null)
    setRole(null)
    try {
      await supabase.auth.signOut()
    } catch (e) {
      // ignore offline signout errors
    }
    router.push('/login')
    router.refresh()
  }

  const getAccessToken = async () => {
    const mockToken = getCookie('mock-access-token')
    if (mockToken) return mockToken

    try {
      const { data: { session } } = await supabase.auth.getSession()
      return session?.access_token ?? null
    } catch {
      return null
    }
  }

  const refreshRole = async () => {
    await fetchRole()
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
