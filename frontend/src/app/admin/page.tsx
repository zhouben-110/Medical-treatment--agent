'use client'

import { useEffect, useState, useCallback, useMemo } from 'react'
import { useAuth } from '@/contexts/AuthContext'
import { useToast } from '@/contexts/ToastContext'
import { useRouter } from 'next/navigation'
import { getAdminUsers, updateUserRole, updateUserStatus, deleteUser, AdminUser } from '@/api/client'

export default function AdminPage() {
  const { role, loading: authLoading } = useAuth()
  const { showToast, confirm } = useToast()
  const router = useRouter()
  const [users, setUsers] = useState<AdminUser[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [actionLoading, setActionLoading] = useState<string | null>(null)
  const [searchEmail, setSearchEmail] = useState('')
  const [filterRole, setFilterRole] = useState<string>('all')

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

  // 前端搜索和筛选
  const filteredUsers = useMemo(() => {
    return users.filter((user) => {
      const matchesEmail = !searchEmail || (user.email?.toLowerCase().includes(searchEmail.toLowerCase()))
      const matchesRole = filterRole === 'all' || user.role === filterRole
      return matchesEmail && matchesRole
    })
  }, [users, searchEmail, filterRole])

  const handleRoleToggle = async (user: AdminUser) => {
    const newRole = user.role === 'admin' ? 'user' : 'admin'
    const ok = await confirm(`确定将 ${user.email} 的角色更改为 "${newRole}" 吗？`)
    if (!ok) return

    setActionLoading(user.id)
    try {
      await updateUserRole(user.id, newRole)
      setUsers(prev => prev.map(u => u.id === user.id ? { ...u, role: newRole } : u))
      showToast(`已将 ${user.email} 角色更改为 ${newRole}`, 'success')
    } catch (err: any) {
      showToast(err.message || '操作失败', 'error')
    } finally {
      setActionLoading(null)
    }
  }

  const handleStatusToggle = async (user: AdminUser) => {
    const newStatus = !user.is_active
    const ok = await confirm(`确定${newStatus ? '启用' : '禁用'} ${user.email} 吗？`)
    if (!ok) return

    setActionLoading(user.id)
    try {
      await updateUserStatus(user.id, newStatus)
      setUsers(prev => prev.map(u => u.id === user.id ? { ...u, is_active: newStatus } : u))
      showToast(`已${newStatus ? '启用' : '禁用'} ${user.email}`, 'success')
    } catch (err: any) {
      showToast(err.message || '操作失败', 'error')
    } finally {
      setActionLoading(null)
    }
  }

  const handleDelete = async (user: AdminUser) => {
    const ok = await confirm(`确定删除用户 ${user.email} 吗？该操作将同时删除该用户的所有会话和消息记录，且不可恢复。`)
    if (!ok) return

    setActionLoading(user.id)
    try {
      await deleteUser(user.id)
      setUsers(prev => prev.filter(u => u.id !== user.id))
      setTotal(prev => prev - 1)
      showToast(`已删除用户 ${user.email}`, 'success')
    } catch (err: any) {
      showToast(err.message || '删除失败', 'error')
    } finally {
      setActionLoading(null)
    }
  }

  const totalPages = Math.ceil(total / 20)

  if (authLoading || role !== 'admin') {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-gray-500 dark:text-gray-400">加载中...</div>
      </div>
    )
  }

  return (
    <div className="max-w-6xl mx-auto px-4 py-8">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between mb-6 gap-4">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">用户管理</h1>
        <span className="text-sm text-gray-500 dark:text-gray-400">共 {total} 个用户</span>
      </div>

      {error && (
        <div className="p-4 mb-4 text-sm text-red-600 bg-red-50 dark:bg-red-900/30 dark:text-red-400 rounded-lg">{error}</div>
      )}

      {/* 搜索和筛选 */}
      <div className="flex flex-col sm:flex-row gap-3 mb-4">
        <input
          type="text"
          value={searchEmail}
          onChange={(e) => setSearchEmail(e.target.value)}
          placeholder="搜索邮箱..."
          className="px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:border-blue-500 dark:focus:border-blue-400 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 placeholder-gray-400 dark:placeholder-gray-500 sm:max-w-xs"
        />
        <select
          value={filterRole}
          onChange={(e) => setFilterRole(e.target.value)}
          className="px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:border-blue-500 dark:focus:border-blue-400 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 sm:max-w-xs"
        >
          <option value="all">全部角色</option>
          <option value="user">用户</option>
          <option value="admin">管理员</option>
        </select>
      </div>

      {loading ? (
        <div className="text-center py-12 text-gray-500 dark:text-gray-400">加载中...</div>
      ) : (
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
            <thead className="bg-gray-50 dark:bg-gray-700">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">邮箱</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">角色</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">状态</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">注册时间</th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">操作</th>
              </tr>
            </thead>
            <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
              {filteredUsers.map((user) => (
                <tr key={user.id} className="hover:bg-gray-50 dark:hover:bg-gray-700">
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 dark:text-gray-100">
                    {user.email || '-'}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${
                      user.role === 'admin'
                        ? 'bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-400'
                        : 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300'
                    }`}>
                      {user.role === 'admin' ? '管理员' : '用户'}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${
                      user.is_active
                        ? 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400'
                        : 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400'
                    }`}>
                      {user.is_active ? '正常' : '已禁用'}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                    {user.created_at ? new Date(user.created_at).toLocaleDateString('zh-CN') : '-'}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-right text-sm space-x-2">
                    <button
                      onClick={() => handleRoleToggle(user)}
                      disabled={actionLoading === user.id}
                      className="text-purple-600 hover:text-purple-900 dark:text-purple-400 dark:hover:text-purple-300 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {user.role === 'admin' ? '设为用户' : '设为管理员'}
                    </button>
                    <button
                      onClick={() => handleStatusToggle(user)}
                      disabled={actionLoading === user.id}
                      className={`disabled:opacity-50 disabled:cursor-not-allowed ${
                        user.is_active
                          ? 'text-red-600 hover:text-red-900 dark:text-red-400 dark:hover:text-red-300'
                          : 'text-green-600 hover:text-green-900 dark:text-green-400 dark:hover:text-green-300'
                      }`}
                    >
                      {user.is_active ? '禁用' : '启用'}
                    </button>
                    <button
                      onClick={() => handleDelete(user)}
                      disabled={actionLoading === user.id}
                      className="text-red-600 hover:text-red-900 dark:text-red-400 dark:hover:text-red-300 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      删除
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {totalPages > 1 && (
            <div className="px-6 py-3 flex items-center justify-between border-t border-gray-200 dark:border-gray-700">
              <span className="text-sm text-gray-500 dark:text-gray-400">
                第 {page} / {totalPages} 页
              </span>
              <div className="flex gap-2">
                <button
                  onClick={() => fetchUsers(page - 1)}
                  disabled={page <= 1}
                  className="px-3 py-1 text-sm border border-gray-300 dark:border-gray-600 rounded disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50 dark:hover:bg-gray-700"
                >
                  上一页
                </button>
                <button
                  onClick={() => fetchUsers(page + 1)}
                  disabled={page >= totalPages}
                  className="px-3 py-1 text-sm border border-gray-300 dark:border-gray-600 rounded disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50 dark:hover:bg-gray-700"
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
