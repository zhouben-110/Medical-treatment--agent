'use client'

import { createContext, useContext, useState, useCallback, ReactNode } from 'react'
import Toast from '@/components/Toast'

export type ToastType = 'success' | 'error' | 'info' | 'warning'

interface ToastItem {
  id: string
  message: string
  type: ToastType
}

interface ToastContextType {
  showToast: (message: string, type?: ToastType) => void
  confirm: (message: string) => Promise<boolean>
}

const ToastContext = createContext<ToastContextType | undefined>(undefined)

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([])
  const [confirmState, setConfirmState] = useState<{
    message: string
    resolve: (value: boolean) => void
  } | null>(null)

  const showToast = useCallback((message: string, type: ToastType = 'info') => {
    const id = crypto.randomUUID()
    setToasts((prev) => [...prev, { id, message, type }])
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id))
    }, 3000)
  }, [])

  const confirm = useCallback((message: string): Promise<boolean> => {
    return new Promise((resolve) => {
      setConfirmState({ message, resolve })
    })
  }, [])

  const handleConfirm = () => {
    confirmState?.resolve(true)
    setConfirmState(null)
  }

  const handleCancel = () => {
    confirmState?.resolve(false)
    setConfirmState(null)
  }

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  return (
    <ToastContext.Provider value={{ showToast, confirm }}>
      {children}

      {/* Toast 列表 */}
      <div className="fixed top-4 right-4 z-[100] flex flex-col gap-2">
        {toasts.map((toast) => (
          <Toast
            key={toast.id}
            message={toast.message}
            type={toast.type}
            onClose={() => removeToast(toast.id)}
          />
        ))}
      </div>

      {/* 确认对话框 */}
      {confirmState && (
        <div className="fixed inset-0 z-[110] flex items-center justify-center">
          <div className="absolute inset-0 bg-black/50" onClick={handleCancel} />
          <div className="relative w-full max-w-sm mx-4 p-6 bg-white dark:bg-gray-800 rounded-2xl shadow-xl">
            <p className="text-gray-900 dark:text-gray-100 mb-6">{confirmState.message}</p>
            <div className="flex gap-3 justify-end">
              <button
                onClick={handleCancel}
                className="px-4 py-2 text-sm text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition"
              >
                取消
              </button>
              <button
                onClick={handleConfirm}
                className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition"
              >
                确认
              </button>
            </div>
          </div>
        </div>
      )}
    </ToastContext.Provider>
  )
}

export function useToast() {
  const context = useContext(ToastContext)
  if (context === undefined) {
    throw new Error('useToast must be used within a ToastProvider')
  }
  return context
}
