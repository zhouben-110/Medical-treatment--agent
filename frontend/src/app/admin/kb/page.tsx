'use client'

import { useEffect, useState, useCallback, useMemo } from 'react'
import { useAuth } from '@/contexts/AuthContext'
import { useToast } from '@/contexts/ToastContext'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import {
  listKBDiseases,
  getKBDisease,
  createKBDisease,
  updateKBDisease,
  deleteKBDisease,
  listKBGuidelines,
  addKBGuideline,
  deleteKBGuideline,
  getKBStats,
  testKBSearch,
  KBDisease,
  KBGuidelineChunk,
  KBStats,
  KBSearchResult
} from '@/api/kb'

export default function KBAdminPage() {
  const { role, loading: authLoading } = useAuth()
  const { showToast, confirm } = useToast()
  const router = useRouter()

  // Tab State: 'diseases' | 'guidelines' | 'search-test'
  const [activeSubTab, setActiveSubTab] = useState<'diseases' | 'guidelines' | 'search-test'>('diseases')

  // Stats State
  const [stats, setStats] = useState<KBStats>({ disease_count: 0, embedded_count: 0, guideline_chunk_count: 0 })
  const [statsLoading, setStatsLoading] = useState(true)

  // Diseases Tab State
  const [diseases, setDiseases] = useState<KBDisease[]>([])
  const [diseaseTotal, setDiseaseTotal] = useState(0)
  const [diseasePage, setDiseasePage] = useState(1)
  const [diseaseSearch, setDiseaseSearch] = useState('')
  const [diseasesLoading, setDiseasesLoading] = useState(true)
  
  // Guideline Tab State
  const [guidelines, setGuidelines] = useState<KBGuidelineChunk[]>([])
  const [guidelineTotal, setGuidelineTotal] = useState(0)
  const [guidelinePage, setGuidelinePage] = useState(1)
  const [guidelineSearch, setGuidelineSearch] = useState('')
  const [guidelinesLoading, setGuidelinesLoading] = useState(true)

  // Search Test Tab State
  const [testQuery, setTestQuery] = useState('')
  const [testMode, setTestMode] = useState<'guidelines' | 'diseases'>('guidelines')
  const [testK, setTestK] = useState(5)
  const [testResults, setTestResults] = useState<KBSearchResult | null>(null)
  const [testSearching, setTestSearching] = useState(false)

  // Modals
  const [isDiseaseModalOpen, setIsDiseaseModalOpen] = useState(false)
  const [editingDisease, setEditingDisease] = useState<KBDisease | null>(null) // null means create mode
  const [diseaseForm, setDiseaseForm] = useState({
    name: '',
    symptomsStr: '',
    description: '',
    treatment: '',
    when_to_see_doctor: '',
    severity: '轻'
  })
  const [diseaseSubmitting, setDiseaseSubmitting] = useState(false)

  const [isGuidelineModalOpen, setIsGuidelineModalOpen] = useState(false)
  const [guidelineForm, setGuidelineForm] = useState({
    title: '',
    content: ''
  })
  const [guidelineSubmitting, setGuidelineSubmitting] = useState(false)

  // Load General Stats
  const fetchStats = useCallback(async () => {
    setStatsLoading(true)
    try {
      const data = await getKBStats()
      setStats(data)
    } catch (err: any) {
      console.error('获取统计失败:', err)
    } finally {
      setStatsLoading(false)
    }
  }, [])

  // Load Diseases
  const fetchDiseases = useCallback(async (p: number, search = '') => {
    setDiseasesLoading(true)
    try {
      const data = await listKBDiseases(p, 10, search)
      setDiseases(data.items)
      setDiseaseTotal(data.total)
      setDiseasePage(data.page)
    } catch (err: any) {
      showToast(err.message || '加载疾病列表失败', 'error')
    } finally {
      setDiseasesLoading(false)
    }
  }, [showToast])

  // Load Guidelines
  const fetchGuidelines = useCallback(async (p: number, search = '') => {
    setGuidelinesLoading(true)
    try {
      const data = await listKBGuidelines(p, 10, search)
      setGuidelines(data.items)
      setGuidelineTotal(data.total)
      setGuidelinePage(data.page)
    } catch (err: any) {
      showToast(err.message || '加载指南列表失败', 'error')
    } finally {
      setGuidelinesLoading(false)
    }
  }, [showToast])

  useEffect(() => {
    if (!authLoading && role !== 'admin') {
      router.push('/')
      return
    }
    if (role === 'admin') {
      fetchStats()
      fetchDiseases(1)
    }
  }, [authLoading, role, router, fetchStats, fetchDiseases])

  const handleSubTabChange = (tab: 'diseases' | 'guidelines' | 'search-test') => {
    setActiveSubTab(tab)
    if (tab === 'diseases') {
      fetchDiseases(1, diseaseSearch)
    } else if (tab === 'guidelines') {
      fetchGuidelines(1, guidelineSearch)
    }
  }

  // Disease Form Handlers
  const openCreateDiseaseModal = () => {
    setEditingDisease(null)
    setDiseaseForm({
      name: '',
      symptomsStr: '',
      description: '',
      treatment: '',
      when_to_see_doctor: '',
      severity: '轻'
    })
    setIsDiseaseModalOpen(true)
  }

  const openEditDiseaseModal = (d: KBDisease) => {
    setEditingDisease(d)
    setDiseaseForm({
      name: d.name,
      symptomsStr: d.symptoms.join('、'),
      description: d.description || '',
      treatment: d.treatment || '',
      when_to_see_doctor: d.when_to_see_doctor || '',
      severity: d.severity || '轻'
    })
    setIsDiseaseModalOpen(true)
  }

  const handleDiseaseSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!diseaseForm.name.trim()) {
      showToast('请输入疾病名称', 'error')
      return
    }
    const symptoms = diseaseForm.symptomsStr
      .split(/[、,，\n]+/)
      .map(s => s.trim())
      .filter(s => s.length > 0)
    if (symptoms.length === 0) {
      showToast('请至少输入一个症状', 'error')
      return
    }

    setDiseaseSubmitting(true)
    try {
      const payload = {
        name: diseaseForm.name.trim(),
        symptoms,
        description: diseaseForm.description.trim(),
        treatment: diseaseForm.treatment.trim(),
        when_to_see_doctor: diseaseForm.when_to_see_doctor.trim(),
        severity: diseaseForm.severity
      }

      if (editingDisease) {
        await updateKBDisease(editingDisease.id, payload)
        showToast(`成功更新疾病: ${payload.name}`, 'success')
      } else {
        await createKBDisease(payload)
        showToast(`成功创建疾病: ${payload.name}`, 'success')
      }
      setIsDiseaseModalOpen(false)
      fetchDiseases(diseasePage, diseaseSearch)
      fetchStats()
    } catch (err: any) {
      showToast(err.message || '操作失败', 'error')
    } finally {
      setDiseaseSubmitting(false)
    }
  }

  const handleDeleteDisease = async (d: KBDisease) => {
    const ok = await confirm(`确定要删除疾病「${d.name}」吗？此操作不可逆。`)
    if (!ok) return
    try {
      await deleteKBDisease(d.id)
      showToast(`已删除疾病: ${d.name}`, 'success')
      fetchDiseases(1, diseaseSearch)
      fetchStats()
    } catch (err: any) {
      showToast(err.message || '删除失败', 'error')
    }
  }

  // Guideline Form Handlers
  const handleGuidelineSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!guidelineForm.title.trim()) {
      showToast('请输入指南标题', 'error')
      return
    }
    if (!guidelineForm.content.trim()) {
      showToast('请输入指南内容', 'error')
      return
    }

    setGuidelineSubmitting(true)
    try {
      const res = await addKBGuideline(guidelineForm.title.trim(), guidelineForm.content.trim())
      showToast(`指南添加成功，已切分为 ${res.chunks} 个片段并写入向量库`, 'success')
      setIsGuidelineModalOpen(false)
      setGuidelineForm({ title: '', content: '' })
      fetchGuidelines(1)
      fetchStats()
    } catch (err: any) {
      showToast(err.message || '导入指南失败', 'error')
    } finally {
      setGuidelineSubmitting(false)
    }
  }

  const handleDeleteGuideline = async (chunk: KBGuidelineChunk) => {
    const ok = await confirm(`确定删除此指南片段吗？「${chunk.text.slice(0, 30)}...」`)
    if (!ok) return
    try {
      await deleteKBGuideline(chunk.id)
      showToast('片段已删除', 'success')
      fetchGuidelines(guidelinePage, guidelineSearch)
      fetchStats()
    } catch (err: any) {
      showToast('删除失败', 'error')
    }
  }

  // Search Test Handlers
  const handleSearchTest = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!testQuery.trim()) {
      showToast('请输入检索关键词或症状', 'error')
      return
    }
    setTestSearching(true)
    try {
      const res = await testKBSearch(testQuery.trim(), testMode, testK)
      setTestResults(res)
    } catch (err: any) {
      showToast(err.message || '检索测试失败', 'error')
    } finally {
      setTestSearching(false)
    }
  }

  if (authLoading || role !== 'admin') {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-gray-500 dark:text-gray-400">正在验证权限...</div>
      </div>
    )
  }

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      {/* Admin Nav */}
      <div className="flex border-b border-gray-200 dark:border-gray-700 mb-6">
        <Link
          href="/admin"
          className="px-4 py-2 font-medium text-sm text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200"
        >
          用户管理
        </Link>
        <Link
          href="/admin/kb"
          className="px-4 py-2 font-medium text-sm border-b-2 border-blue-500 text-blue-600 dark:text-blue-400"
        >
          知识库管理
        </Link>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <div className="bg-gradient-to-br from-blue-50 to-blue-100 dark:from-blue-900/10 dark:to-blue-900/30 p-6 rounded-xl border border-blue-200/50 dark:border-blue-800/30 shadow-sm flex items-center gap-4">
          <div className="w-12 h-12 bg-blue-500/10 dark:bg-blue-400/10 rounded-lg flex items-center justify-center text-blue-600 dark:text-blue-400">
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
            </svg>
          </div>
          <div>
            <div className="text-xs text-blue-600/70 dark:text-blue-400/70 font-semibold uppercase tracking-wider">疾病总数</div>
            <div className="text-2xl font-bold text-blue-900 dark:text-blue-300 mt-1">
              {statsLoading ? '...' : stats.disease_count}
            </div>
          </div>
        </div>

        <div className="bg-gradient-to-br from-purple-50 to-purple-100 dark:from-purple-900/10 dark:to-purple-900/30 p-6 rounded-xl border border-purple-200/50 dark:border-purple-800/30 shadow-sm flex items-center gap-4">
          <div className="w-12 h-12 bg-purple-500/10 dark:bg-purple-400/10 rounded-lg flex items-center justify-center text-purple-600 dark:text-purple-400">
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364.364l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
            </svg>
          </div>
          <div>
            <div className="text-xs text-purple-600/70 dark:text-purple-400/70 font-semibold uppercase tracking-wider">已嵌入向量疾病</div>
            <div className="text-2xl font-bold text-purple-900 dark:text-purple-300 mt-1">
              {statsLoading ? '...' : stats.embedded_count}
            </div>
          </div>
        </div>

        <div className="bg-gradient-to-br from-indigo-50 to-indigo-100 dark:from-indigo-900/10 dark:to-indigo-900/30 p-6 rounded-xl border border-indigo-200/50 dark:border-indigo-800/30 shadow-sm flex items-center gap-4">
          <div className="w-12 h-12 bg-indigo-500/10 dark:bg-indigo-400/10 rounded-lg flex items-center justify-center text-indigo-600 dark:text-indigo-400">
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
            </svg>
          </div>
          <div>
            <div className="text-xs text-indigo-600/70 dark:text-indigo-400/70 font-semibold uppercase tracking-wider">诊疗指南切片</div>
            <div className="text-2xl font-bold text-indigo-900 dark:text-indigo-300 mt-1">
              {statsLoading ? '...' : stats.guideline_chunk_count}
            </div>
          </div>
        </div>
      </div>

      {/* Main Tabs Dashboard */}
      <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-sm border border-gray-100 dark:border-gray-700 overflow-hidden">
        {/* Tab Headers */}
        <div className="flex border-b border-gray-200 dark:border-gray-700 bg-gray-50/50 dark:bg-gray-800/50">
          <button
            onClick={() => handleSubTabChange('diseases')}
            className={`px-6 py-4 font-semibold text-sm transition flex items-center gap-2 border-b-2 ${
              activeSubTab === 'diseases'
                ? 'border-blue-500 text-blue-600 dark:text-blue-400 bg-white dark:bg-gray-800'
                : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'
            }`}
          >
            疾病库管理
          </button>
          <button
            onClick={() => handleSubTabChange('guidelines')}
            className={`px-6 py-4 font-semibold text-sm transition flex items-center gap-2 border-b-2 ${
              activeSubTab === 'guidelines'
                ? 'border-blue-500 text-blue-600 dark:text-blue-400 bg-white dark:bg-gray-800'
                : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'
            }`}
          >
            诊疗指南管理
          </button>
          <button
            onClick={() => handleSubTabChange('search-test')}
            className={`px-6 py-4 font-semibold text-sm transition flex items-center gap-2 border-b-2 ${
              activeSubTab === 'search-test'
                ? 'border-blue-500 text-blue-600 dark:text-blue-400 bg-white dark:bg-gray-800'
                : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'
            }`}
          >
            检索诊断测试
          </button>
        </div>

        {/* Tab Body */}
        <div className="p-6">
          {/* TAB 1: Diseases Library */}
          {activeSubTab === 'diseases' && (
            <div>
              <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-6">
                {/* Search Bar */}
                <div className="flex gap-2 w-full sm:max-w-md">
                  <input
                    type="text"
                    value={diseaseSearch}
                    onChange={(e) => setDiseaseSearch(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && fetchDiseases(1, diseaseSearch)}
                    placeholder="搜疾病名称、描述..."
                    className="flex-1 px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:border-blue-500 dark:focus:border-blue-400 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 placeholder-gray-400 dark:placeholder-gray-500"
                  />
                  <button
                    onClick={() => fetchDiseases(1, diseaseSearch)}
                    className="px-4 py-2 bg-gray-100 hover:bg-gray-200 dark:bg-gray-700 dark:hover:bg-gray-600 rounded-lg text-sm text-gray-700 dark:text-gray-200 transition font-medium"
                  >
                    搜索
                  </button>
                </div>
                {/* Add New */}
                <button
                  onClick={openCreateDiseaseModal}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-semibold transition shadow-sm flex items-center gap-2"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                  </svg>
                  新建疾病
                </button>
              </div>

              {diseasesLoading ? (
                <div className="text-center py-12 text-gray-500 dark:text-gray-400">疾病数据加载中...</div>
              ) : (
                <div className="overflow-x-auto border border-gray-100 dark:border-gray-700/50 rounded-xl">
                  <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                    <thead className="bg-gray-50 dark:bg-gray-700/50">
                      <tr>
                        <th className="px-6 py-3 text-left text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">疾病名称</th>
                        <th className="px-6 py-3 text-left text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">严重度</th>
                        <th className="px-6 py-3 text-left text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">典型症状</th>
                        <th className="px-6 py-3 text-left text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">向量索引</th>
                        <th className="px-6 py-3 text-right text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">操作</th>
                      </tr>
                    </thead>
                    <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
                      {diseases.length === 0 ? (
                        <tr>
                          <td colSpan={5} className="px-6 py-8 text-center text-sm text-gray-500 dark:text-gray-400">
                            暂无符合条件的疾病数据。
                          </td>
                        </tr>
                      ) : (
                        diseases.map((d) => (
                          <tr key={d.id} className="hover:bg-gray-50/50 dark:hover:bg-gray-700/20 transition-colors">
                            <td className="px-6 py-4 whitespace-nowrap">
                              <span className="font-semibold text-gray-900 dark:text-gray-100">{d.name}</span>
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap">
                              <span className={`inline-flex px-2 py-0.5 text-xs font-semibold rounded-full ${
                                d.severity === '重' || d.severity === '中-重'
                                  ? 'bg-red-50 text-red-700 dark:bg-red-900/20 dark:text-red-400'
                                  : d.severity === '中'
                                  ? 'bg-yellow-50 text-yellow-700 dark:bg-yellow-900/20 dark:text-yellow-400'
                                  : 'bg-green-50 text-green-700 dark:bg-green-900/20 dark:text-green-400'
                              }`}>
                                {d.severity || '轻'}
                              </span>
                            </td>
                            <td className="px-6 py-4 max-w-xs truncate">
                              <span className="text-sm text-gray-600 dark:text-gray-300">
                                {d.symptoms.slice(0, 6).join('、')}
                                {d.symptoms.length > 6 && ' ...'}
                              </span>
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap">
                              <span className={`inline-flex items-center gap-1.5 text-xs font-semibold ${
                                d.has_embedding ? 'text-green-600 dark:text-green-400' : 'text-gray-400'
                              }`}>
                                <span className={`w-2 h-2 rounded-full ${d.has_embedding ? 'bg-green-500' : 'bg-gray-400'}`} />
                                {d.has_embedding ? '已计算向量' : '未就绪'}
                              </span>
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap text-right text-sm space-x-3">
                              <button
                                onClick={() => openEditDiseaseModal(d)}
                                className="text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300 font-semibold"
                              >
                                编辑
                              </button>
                              <button
                                onClick={() => handleDeleteDisease(d)}
                                className="text-red-600 hover:text-red-800 dark:text-red-400 dark:hover:text-red-300 font-semibold"
                              >
                                删除
                              </button>
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              )}

              {/* Disease Pagination */}
              {!diseasesLoading && diseaseTotal > 10 && (
                <div className="flex justify-between items-center mt-6">
                  <span className="text-sm text-gray-500 dark:text-gray-400">
                    第 {diseasePage} / {Math.ceil(diseaseTotal / 10)} 页，共 {diseaseTotal} 个疾病
                  </span>
                  <div className="flex gap-2">
                    <button
                      onClick={() => fetchDiseases(diseasePage - 1, diseaseSearch)}
                      disabled={diseasePage <= 1}
                      className="px-3 py-1.5 border border-gray-300 dark:border-gray-600 rounded-lg text-sm disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50 dark:hover:bg-gray-700 bg-white dark:bg-gray-800 dark:text-gray-200"
                    >
                      上一页
                    </button>
                    <button
                      onClick={() => fetchDiseases(diseasePage + 1, diseaseSearch)}
                      disabled={diseasePage >= Math.ceil(diseaseTotal / 10)}
                      className="px-3 py-1.5 border border-gray-300 dark:border-gray-600 rounded-lg text-sm disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50 dark:hover:bg-gray-700 bg-white dark:bg-gray-800 dark:text-gray-200"
                    >
                      下一页
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* TAB 2: Guidelines Management */}
          {activeSubTab === 'guidelines' && (
            <div>
              <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-6">
                {/* Search Bar */}
                <div className="flex gap-2 w-full sm:max-w-md">
                  <input
                    type="text"
                    value={guidelineSearch}
                    onChange={(e) => setGuidelineSearch(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && fetchGuidelines(1, guidelineSearch)}
                    placeholder="搜指南片段正文或标题..."
                    className="flex-1 px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:border-blue-500 dark:focus:border-blue-400 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 placeholder-gray-400 dark:placeholder-gray-500"
                  />
                  <button
                    onClick={() => fetchGuidelines(1, guidelineSearch)}
                    className="px-4 py-2 bg-gray-100 hover:bg-gray-200 dark:bg-gray-700 dark:hover:bg-gray-600 rounded-lg text-sm text-gray-700 dark:text-gray-200 transition font-medium"
                  >
                    搜索
                  </button>
                </div>
                {/* Add New */}
                <button
                  onClick={() => setIsGuidelineModalOpen(true)}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-semibold transition shadow-sm flex items-center gap-2"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                  </svg>
                  上传新指南文档
                </button>
              </div>

              {guidelinesLoading ? (
                <div className="text-center py-12 text-gray-500 dark:text-gray-400">指南片段加载中...</div>
              ) : (
                <div className="space-y-4">
                  {guidelines.length === 0 ? (
                    <div className="text-center py-12 border border-dashed border-gray-200 dark:border-gray-700 rounded-xl text-gray-500 dark:text-gray-400 text-sm">
                      没有找到指南向量数据。你可以点击上方按钮上传新指南。
                    </div>
                  ) : (
                    guidelines.map((chunk) => (
                      <div
                        key={chunk.id}
                        className="p-5 border border-gray-100 dark:border-gray-700/50 bg-gray-50/20 dark:bg-gray-900/10 rounded-xl hover:shadow-sm transition flex flex-col md:flex-row justify-between items-start md:items-center gap-4"
                      >
                        <div className="flex-1 max-w-4xl">
                          <div className="flex items-center gap-2 mb-2">
                            <span className="text-xs font-semibold bg-indigo-50 dark:bg-indigo-950/40 text-indigo-700 dark:text-indigo-400 px-2 py-0.5 rounded">
                              📖 {chunk.metadata.title || '诊疗参考'}
                            </span>
                            <span className="text-xs text-gray-400 dark:text-gray-500">ID: {chunk.id.slice(0, 8)}</span>
                          </div>
                          <p className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed font-mono whitespace-pre-wrap select-all">
                            {chunk.text}
                          </p>
                        </div>
                        <button
                          onClick={() => handleDeleteGuideline(chunk)}
                          className="px-3 py-1.5 border border-red-200 hover:bg-red-50 hover:text-red-700 dark:border-red-900/30 dark:hover:bg-red-955 text-red-600 dark:text-red-400 rounded-lg text-xs font-semibold transition"
                        >
                          物理删除
                        </button>
                      </div>
                    ))
                  )}
                </div>
              )}

              {/* Guideline Pagination */}
              {!guidelinesLoading && guidelineTotal > 10 && (
                <div className="flex justify-between items-center mt-6">
                  <span className="text-sm text-gray-500 dark:text-gray-400">
                    第 {guidelinePage} / {Math.ceil(guidelineTotal / 10)} 页，共 {guidelineTotal} 个切片
                  </span>
                  <div className="flex gap-2">
                    <button
                      onClick={() => fetchGuidelines(guidelinePage - 1, guidelineSearch)}
                      disabled={guidelinePage <= 1}
                      className="px-3 py-1.5 border border-gray-300 dark:border-gray-600 rounded-lg text-sm disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50 dark:hover:bg-gray-700 bg-white dark:bg-gray-800 dark:text-gray-200"
                    >
                      上一页
                    </button>
                    <button
                      onClick={() => fetchGuidelines(guidelinePage + 1, guidelineSearch)}
                      disabled={guidelinePage >= Math.ceil(guidelineTotal / 10)}
                      className="px-3 py-1.5 border border-gray-300 dark:border-gray-600 rounded-lg text-sm disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50 dark:hover:bg-gray-700 bg-white dark:bg-gray-800 dark:text-gray-200"
                    >
                      下一页
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* TAB 3: Search Test & RAG diagnostic sandbox */}
          {activeSubTab === 'search-test' && (
            <div>
              <div className="max-w-3xl mx-auto border border-gray-100 dark:border-gray-700 p-6 rounded-2xl bg-gray-50/30 dark:bg-gray-900/10 mb-8">
                <h3 className="text-base font-bold text-gray-900 dark:text-gray-100 mb-4 flex items-center gap-1.5">
                  <span className="inline-block w-2.5 h-2.5 bg-blue-500 rounded-full" />
                  RAG 语义检索沙箱与混合打分校验
                </h3>
                <form onSubmit={handleSearchTest} className="space-y-4">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-xs font-semibold text-gray-500 dark:text-gray-400 mb-1.5 uppercase">检索目标模式</label>
                      <div className="grid grid-cols-2 gap-2 bg-gray-100 dark:bg-gray-700/50 p-1 rounded-lg">
                        <button
                          type="button"
                          onClick={() => setTestMode('guidelines')}
                          className={`py-1.5 text-xs font-semibold rounded-md transition ${
                            testMode === 'guidelines'
                              ? 'bg-white dark:bg-gray-700 text-blue-600 dark:text-blue-400 shadow-sm'
                              : 'text-gray-500 hover:text-gray-800 dark:hover:text-gray-300'
                          }`}
                        >
                          诊疗指南 (语义向量)
                        </button>
                        <button
                          type="button"
                          onClick={() => setTestMode('diseases')}
                          className={`py-1.5 text-xs font-semibold rounded-md transition ${
                            testMode === 'diseases'
                              ? 'bg-white dark:bg-gray-700 text-blue-600 dark:text-blue-400 shadow-sm'
                              : 'text-gray-500 hover:text-gray-800 dark:hover:text-gray-300'
                          }`}
                        >
                          症状匹配 (Dice+向量)
                        </button>
                      </div>
                    </div>

                    <div>
                      <label className="block text-xs font-semibold text-gray-500 dark:text-gray-400 mb-1.5 uppercase">检索结果数量 (K)</label>
                      <input
                        type="number"
                        min={1}
                        max={10}
                        value={testK}
                        onChange={(e) => setTestK(parseInt(e.target.value) || 3)}
                        className="w-full px-3 py-1.5 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500/20 text-sm"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-gray-500 dark:text-gray-400 mb-1.5 uppercase">
                      {testMode === 'guidelines' ? '自然语言检索词' : '疾病症状关键词 (用空格分隔)'}
                    </label>
                    <div className="flex gap-2">
                      <input
                        type="text"
                        value={testQuery}
                        onChange={(e) => setTestQuery(e.target.value)}
                        placeholder={testMode === 'guidelines' ? '例如：高血压有哪些用药禁忌？' : '例如：发热 咳嗽 肌肉酸痛'}
                        className="flex-1 px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:border-blue-500 dark:focus:border-blue-400 bg-white dark:bg-gray-700 text-sm"
                      />
                      <button
                        type="submit"
                        disabled={testSearching}
                        className="px-5 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm font-semibold rounded-lg transition"
                      >
                        {testSearching ? '匹配中...' : '测试检索'}
                      </button>
                    </div>
                  </div>
                </form>
              </div>

              {/* RAG Results Display */}
              {testResults && (
                <div className="space-y-4">
                  <h4 className="text-sm font-semibold text-gray-900 dark:text-gray-100 flex items-center justify-between">
                    <span>测试结果 ({testResults.results.length} 项)</span>
                    <span className="text-xs text-gray-400">检索源: {testResults.mode === 'guidelines' ? 'PGVector VectorStore' : 'Cosine + Dice Hybrid Match'}</span>
                  </h4>
                  <div className="space-y-3">
                    {testResults.results.length === 0 ? (
                      <div className="text-center py-8 bg-gray-50/50 dark:bg-gray-800/50 border border-dashed border-gray-200 dark:border-gray-700 rounded-xl text-sm text-gray-500 dark:text-gray-400">
                        未匹配到相关内容。请调整关键词。
                      </div>
                    ) : (
                      testResults.results.map((r, i) => (
                        <div key={i} className="p-4 border border-gray-100 dark:border-gray-700 bg-white dark:bg-gray-800/80 rounded-xl shadow-sm">
                          <div className="flex items-center justify-between gap-3 mb-2.5">
                            {r.name ? (
                              <div className="flex items-center gap-2">
                                <span className="font-bold text-gray-900 dark:text-gray-100 text-sm">{r.name}</span>
                                <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                                  r.severity === '重' ? 'bg-red-50 text-red-600 dark:bg-red-950/20' : 'bg-green-50 text-green-600 dark:bg-green-950/20'
                                }`}>
                                  {r.severity}
                                </span>
                              </div>
                            ) : (
                              <span className="text-xs font-semibold text-indigo-700 dark:text-indigo-400 bg-indigo-50 dark:bg-indigo-950/30 px-2 py-0.5 rounded">
                                指南匹配候选 #{i + 1}
                              </span>
                            )}
                            <div className="flex items-center gap-2">
                              <span className="text-xs text-gray-500">匹配得分:</span>
                              <span className="text-xs font-bold text-blue-600 dark:text-blue-400">{r.score}</span>
                            </div>
                          </div>
                          {r.text && (
                            <p className="text-sm font-mono text-gray-700 dark:text-gray-300 bg-gray-50 dark:bg-gray-900/40 p-2.5 rounded border border-gray-100 dark:border-gray-700/50 leading-relaxed select-all">
                              {r.text}
                            </p>
                          )}
                          {r.matched_symptoms && r.matched_symptoms.length > 0 && (
                            <div className="flex items-center gap-1.5 flex-wrap">
                              <span className="text-xs text-gray-400">匹配中症状:</span>
                              {r.matched_symptoms.map((s, idx) => (
                                <span key={idx} className="text-[11px] bg-blue-50 dark:bg-blue-950/30 text-blue-700 dark:text-blue-400 px-1.5 py-0.5 rounded-md font-medium border border-blue-100/50 dark:border-blue-900/30">
                                  {s}
                                </span>
                              ))}
                            </div>
                          )}
                        </div>
                      ))
                    )}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* MODAL 1: Disease Creation / Editing */}
      {isDiseaseModalOpen && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4 overflow-y-auto">
          <div className="bg-white dark:bg-gray-800 rounded-2xl w-full max-w-xl shadow-xl overflow-hidden animate-in fade-in zoom-in duration-200">
            <div className="px-6 py-4 bg-gray-50 dark:bg-gray-700/30 border-b border-gray-100 dark:border-gray-700 flex justify-between items-center">
              <h3 className="text-lg font-bold text-gray-900 dark:text-gray-100">
                {editingDisease ? `编辑疾病「${editingDisease.name}」` : '新建疾病条目'}
              </h3>
              <button
                onClick={() => setIsDiseaseModalOpen(false)}
                className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 transition"
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <form onSubmit={handleDiseaseSubmit} className="p-6 space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-bold text-gray-500 dark:text-gray-400 mb-1.5 uppercase">疾病名称</label>
                  <input
                    type="text"
                    required
                    value={diseaseForm.name}
                    onChange={(e) => setDiseaseForm(prev => ({ ...prev, name: e.target.value }))}
                    placeholder="例如：急性扁桃体炎"
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500/20 text-sm text-gray-900 dark:text-gray-100"
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold text-gray-500 dark:text-gray-400 mb-1.5 uppercase">严重程度</label>
                  <select
                    value={diseaseForm.severity}
                    onChange={(e) => setDiseaseForm(prev => ({ ...prev, severity: e.target.value }))}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500/20 text-sm text-gray-900 dark:text-gray-100"
                  >
                    <option value="轻">轻 (Minor)</option>
                    <option value="轻-中">轻-中 (Mild-Moderate)</option>
                    <option value="中">中 (Moderate)</option>
                    <option value="中-重">中-重 (Moderate-Severe)</option>
                    <option value="重">重 (Severe / High-Risk)</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold text-gray-500 dark:text-gray-400 mb-1.5 uppercase">典型症状 (用顿号“、”或逗号分隔)</label>
                <textarea
                  required
                  rows={2}
                  value={diseaseForm.symptomsStr}
                  onChange={(e) => setDiseaseForm(prev => ({ ...prev, symptomsStr: e.target.value }))}
                  placeholder="例如：发热、咽痛、吞咽困难、扁桃体红肿"
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500/20 text-sm text-gray-900 dark:text-gray-100 font-mono"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-gray-500 dark:text-gray-400 mb-1.5 uppercase">疾病基本描述</label>
                <textarea
                  rows={2}
                  value={diseaseForm.description}
                  onChange={(e) => setDiseaseForm(prev => ({ ...prev, description: e.target.value }))}
                  placeholder="该疾病的简要病理病机介绍..."
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500/20 text-sm text-gray-900 dark:text-gray-100"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-gray-500 dark:text-gray-400 mb-1.5 uppercase">对症治疗建议</label>
                <textarea
                  rows={2}
                  value={diseaseForm.treatment}
                  onChange={(e) => setDiseaseForm(prev => ({ ...prev, treatment: e.target.value }))}
                  placeholder="如：物理降温、抗病毒治疗、口服退热药、注意补水等..."
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500/20 text-sm text-gray-900 dark:text-gray-100"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-gray-500 dark:text-gray-400 mb-1.5 uppercase">就医指征/分诊时机</label>
                <textarea
                  rows={2}
                  value={diseaseForm.when_to_see_doctor}
                  onChange={(e) => setDiseaseForm(prev => ({ ...prev, when_to_see_doctor: e.target.value }))}
                  placeholder="何时应当立即前往线下门急诊就医..."
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500/20 text-sm text-gray-900 dark:text-gray-100"
                />
              </div>

              <div className="pt-2 border-t border-gray-100 dark:border-gray-700 flex justify-end gap-3">
                <button
                  type="button"
                  onClick={() => setIsDiseaseModalOpen(false)}
                  className="px-4 py-2 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 text-sm font-semibold rounded-lg hover:bg-gray-50 dark:hover:bg-gray-750 transition"
                >
                  取消
                </button>
                <button
                  type="submit"
                  disabled={diseaseSubmitting}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold rounded-lg transition disabled:opacity-50"
                >
                  {diseaseSubmitting ? '保存中...' : '保存条目'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL 2: Guideline Document Import */}
      {isGuidelineModalOpen && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4 overflow-y-auto">
          <div className="bg-white dark:bg-gray-800 rounded-2xl w-full max-w-2xl shadow-xl overflow-hidden animate-in fade-in zoom-in duration-200">
            <div className="px-6 py-4 bg-gray-50 dark:bg-gray-700/30 border-b border-gray-100 dark:border-gray-700 flex justify-between items-center">
              <h3 className="text-lg font-bold text-gray-900 dark:text-gray-100">
                上传/导入诊疗指南文档
              </h3>
              <button
                onClick={() => setIsGuidelineModalOpen(false)}
                className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 transition"
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <form onSubmit={handleGuidelineSubmit} className="p-6 space-y-4">
              <div>
                <label className="block text-xs font-bold text-gray-500 dark:text-gray-400 mb-1.5 uppercase">指南/参考标题</label>
                <input
                  type="text"
                  required
                  value={guidelineForm.title}
                  onChange={(e) => setGuidelineForm(prev => ({ ...prev, title: e.target.value }))}
                  placeholder="例如：2026年中国成人慢性高血压防治指南"
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500/20 text-sm text-gray-900 dark:text-gray-100"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-gray-500 dark:text-gray-400 mb-1.5 uppercase">文档正文内容 (段落间建议空一行 \n\n，系统会自动按段落切分)</label>
                <textarea
                  required
                  rows={10}
                  value={guidelineForm.content}
                  onChange={(e) => setGuidelineForm(prev => ({ ...prev, content: e.target.value }))}
                  placeholder="请在此输入或粘贴医学参考文献、诊疗手册、专家指南片段正文..."
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500/20 text-sm text-gray-900 dark:text-gray-100 font-mono leading-relaxed"
                />
              </div>

              <div className="pt-2 border-t border-gray-100 dark:border-gray-700 flex justify-end gap-3">
                <button
                  type="button"
                  onClick={() => setIsGuidelineModalOpen(false)}
                  className="px-4 py-2 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 text-sm font-semibold rounded-lg hover:bg-gray-50 dark:hover:bg-gray-750 transition"
                >
                  取消
                </button>
                <button
                  type="submit"
                  disabled={guidelineSubmitting}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold rounded-lg transition disabled:opacity-50 flex items-center gap-2"
                >
                  {guidelineSubmitting ? (
                    <>
                      <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                      </svg>
                      正在切分并写入向量...
                    </>
                  ) : (
                    '导入并生成向量索引'
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
