'use client'

import { ToastType } from '@/contexts/ToastContext'

interface ToastProps {
  message: string
  type: ToastType
  onClose: () => void
}

const TOAST_STYLES: Record<ToastType, { bg: string; icon: string }> = {
  success: { bg: 'bg-green-50 border-green-200 dark:bg-green-900/30 dark:border-green-700', icon: '✓' },
  error: { bg: 'bg-red-50 border-red-200 dark:bg-red-900/30 dark:border-red-700', icon: '✕' },
  warning: { bg: 'bg-yellow-50 border-yellow-200 dark:bg-yellow-900/30 dark:border-yellow-700', icon: '⚠' },
  info: { bg: 'bg-blue-50 border-blue-200 dark:bg-blue-900/30 dark:border-blue-700', icon: 'ℹ' },
}

const ICON_COLORS: Record<ToastType, string> = {
  success: 'text-green-600 dark:text-green-400',
  error: 'text-red-600 dark:text-red-400',
  warning: 'text-yellow-600 dark:text-yellow-400',
  info: 'text-blue-600 dark:text-blue-400',
}

export default function Toast({ message, type, onClose }: ToastProps) {
  const styles = TOAST_STYLES[type]

  return (
    <div
      className={`flex items-center gap-3 px-4 py-3 rounded-lg border shadow-lg animate-slide-in ${styles.bg}`}
    >
      <span className={`text-lg font-bold ${ICON_COLORS[type]}`}>{styles.icon}</span>
      <p className="text-sm text-gray-800 dark:text-gray-200 flex-1">{message}</p>
      <button
        onClick={onClose}
        className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition"
      >
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>
  )
}
