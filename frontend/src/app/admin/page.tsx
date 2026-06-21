'use client'

import { useEffect, useState, useCallback } from 'react'
import { useAuth } from '@/contexts/AuthContext'
import { useRouter } from 'next/navigation'
import { getAdminUsers, updateUserRole, updateUserStatus, deleteUser, AdminUser } from '@/api/client'

export default function AdminPage() {
  const { role, loading: authLoading } = useAuth()
  const router = useRouter()
  const [users, setUsers] = useState<AdminUser[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [actionLoading, setActionLoading] = useState<string | null>(null)

  const fetchUsers = useCallback(async (p: number) => {
    setLoading(true)
    setError(null)
    try {
      const data = await getAdminUsers(p, 20)
      setUsers(data.items)
      setTotal(data.total)
      setPage(data.page)
    } catch (err: any) {
      if (err.message === 'FORBIDDEN') {
        setError('需要管理员权限')
      } else {
        setError(err.message || '加载失败')
      }
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (!authLoading && role !== 'admin') {
      router.push('/')
      return
    }
    if (role === 'admin') {
      fetchUsers(1)
    }
  }, [authLoading, role, router, fetchUsers])

  const handleRoleToggle = async (user: AdminUser) => {
    const newRole = user.role === 'admin' ? 'user' : 'admin'
    if (!confirm(`确定将 ${user.email} 的角色更改为 "${newRole}" 吗？`)) return

    setActionLoading(user.id)
    try {
      await updateUserRole(user.id, newRole)
      setUsers(prev => prev.map(u => u.id === user.id ? { ...u, role: newRole } : u))
    } catch (err: any) {
      alert(err.message || '操作失败')
    } finally {
      setActionLoading(null)
    }
  }

  const handleStatusToggle = async (user: AdminUser) => {
    const newStatus = !user.is_active
    if (!confirm(`确定${newStatus ? '启用' : '禁用'} ${user.email} 吗？`)) return

    setActionLoading(user.id)
    try {
      await updateUserStatus(user.id, newStatus)
      setUsers(prev => prev.map(u => u.id === user.id ? { ...u, is_active: newStatus } : u))
    } catch (err: any) {
      alert(err.message || '操作失败')
    } finally {
      setActionLoading(null)
    }
  }

  const handleDelete = async (user: AdminUser) => {
    if (!confirm(`确定删除用户 ${user.email} 吗？\n该操作将同时删除该用户的所有会话和消息记录，且不可恢复。`)) return

    setActionLoading(user.id)
    try {
      await deleteUser(user.id)
      setUsers(prev => prev.filter(u => u.id !== user.id))
      setTotal(prev => prev - 1)
    } catch (err: any) {
      alert(err.message || '删除失败')
    } finally {
      setActionLoading(null)
    }
  }

  const totalPages = Math.ceil(total / 20)

  if (authLoading || role !== 'admin') {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-gray-500">加载中...</div>
      </div>
    )
  }

  return (
    <div className="max-w-6xl mx-auto px-4 py-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">用户管理</h1>
        <span className="text-sm text-gray-500">共 {total} 个用户</span>
      </div>

      {error && (
        <div className="p-4 mb-4 text-sm text-red-600 bg-red-50 rounded-lg">{error}</div>
      )}

      {loading ? (
        <div className="text-center py-12 text-gray-500">加载中...</div>
      ) : (
        <div className="bg-white rounded-xl shadow overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">邮箱</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">角色</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">状态</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">注册时间</th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">操作</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {users.map((user) => (
                <tr key={user.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {user.email || '-'}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${
                      user.role === 'admin'
                        ? 'bg-purple-100 text-purple-800'
                        : 'bg-gray-100 text-gray-800'
                    }`}>
                      {user.role === 'admin' ? '管理员' : '用户'}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${
                      user.is_active
                        ? 'bg-green-100 text-green-800'
                        : 'bg-red-100 text-red-800'
                    }`}>
                      {user.is_active ? '正常' : '已禁用'}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {user.created_at ? new Date(user.created_at).toLocaleDateString('zh-CN') : '-'}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-right text-sm space-x-2">
                    <button
                      onClick={() => handleRoleToggle(user)}
                      disabled={actionLoading === user.id}
                      className="text-purple-600 hover:text-purple-900 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {user.role === 'admin' ? '设为用户' : '设为管理员'}
                    </button>
                    <button
                      onClick={() => handleStatusToggle(user)}
                      disabled={actionLoading === user.id}
                      className={`disabled:opacity-50 disabled:cursor-not-allowed ${
                        user.is_active
                          ? 'text-red-600 hover:text-red-900'
                          : 'text-green-600 hover:text-green-900'
                      }`}
                    >
                      {user.is_active ? '禁用' : '启用'}
                    </button>
                    <button
                      onClick={() => handleDelete(user)}
                      disabled={actionLoading === user.id}
                      className="text-red-600 hover:text-red-900 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      删除
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {totalPages > 1 && (
            <div className="px-6 py-3 flex items-center justify-between border-t border-gray-200">
              <span className="text-sm text-gray-500">
                第 {page} / {totalPages} 页
              </span>
              <div className="flex gap-2">
                <button
                  onClick={() => fetchUsers(page - 1)}
                  disabled={page <= 1}
                  className="px-3 py-1 text-sm border rounded disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  上一页
                </button>
                <button
                  onClick={() => fetchUsers(page + 1)}
                  disabled={page >= totalPages}
                  className="px-3 py-1 text-sm border rounded disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  下一页
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
