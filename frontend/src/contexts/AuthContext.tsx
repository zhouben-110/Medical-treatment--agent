'use client'

import { createContext, useContext, useEffect, useState, ReactNode, useCallback } from 'react'
import { User, Session } from '@supabase/supabase-js'
import { createClient } from '@/lib/supabase'
import { useRouter } from 'next/navigation'

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
  const supabase = createClient()

  const fetchRole = useCallback(async () => {
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
    // 获取初始 session
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session)
      setUser(session?.user ?? null)
      setLoading(false)
      if (session) fetchRole()
    })

    // 监听认证状态变化
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      async (event, session) => {
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
    const { error } = await supabase.auth.signInWithPassword({
      email,
      password,
    })
    return { error }
  }

  const signUp = async (email: string, password: string) => {
    const { error } = await supabase.auth.signUp({
      email,
      password,
    })
    return { error }
  }

  const signOut = async () => {
    await supabase.auth.signOut()
  }

  const getAccessToken = async () => {
    const { data: { session } } = await supabase.auth.getSession()
    return session?.access_token ?? null
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
