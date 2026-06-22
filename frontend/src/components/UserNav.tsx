'use client'

import { useState } from 'react'
import { useAuth } from '@/contexts/AuthContext'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import ChangePasswordModal from './ChangePasswordModal'

export default function UserNav() {
  const { user, role, loading, signOut } = useAuth()
  const router = useRouter()
  const [showChangePassword, setShowChangePassword] = useState(false)

  if (loading) {
    return (
      <div className="flex items-center gap-2">
        <div className="w-8 h-8 bg-gray-200 dark:bg-gray-700 rounded-full animate-pulse" />
      </div>
    )
  }

  if (!user) {
    return (
      <div className="flex items-center gap-3">
        <Link
          href="/login"
          className="px-4 py-2 text-sm text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-gray-100 transition"
        >
          登录
        </Link>
        <Link
          href="/register"
          className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition"
        >
          注册
        </Link>
      </div>
    )
  }

  const handleSignOut = async () => {
    await signOut()
    router.push('/login')
  }

  return (
    <>
      <div className="flex items-center gap-3">
        {role === 'admin' && (
          <Link
            href="/admin"
            className="px-3 py-1.5 text-sm text-purple-600 hover:text-purple-800 hover:bg-purple-50 dark:text-purple-400 dark:hover:text-purple-300 dark:hover:bg-purple-900/30 rounded-lg transition"
          >
            管理后台
          </Link>
        )}
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 bg-blue-100 dark:bg-blue-900/30 rounded-full flex items-center justify-center">
            <svg className="w-4 h-4 text-blue-600 dark:text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
            </svg>
          </div>
          <span className="text-sm text-gray-700 dark:text-gray-300 max-w-[150px] truncate">
            {user.email}
          </span>
        </div>
        <button
          onClick={() => setShowChangePassword(true)}
          className="px-3 py-1.5 text-sm text-gray-500 hover:text-blue-600 hover:bg-blue-50 dark:text-gray-400 dark:hover:text-blue-400 dark:hover:bg-blue-900/30 rounded-lg transition"
        >
          修改密码
        </button>
        <button
          onClick={handleSignOut}
          className="px-3 py-1.5 text-sm text-gray-500 hover:text-red-600 hover:bg-red-50 dark:text-gray-400 dark:hover:text-red-400 dark:hover:bg-red-900/30 rounded-lg transition"
        >
          登出
        </button>
      </div>

      <ChangePasswordModal
        isOpen={showChangePassword}
        onClose={() => setShowChangePassword(false)}
      />
    </>
  )
}
