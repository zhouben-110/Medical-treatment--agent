// KB API client functions - 知识库管理相关 API

import { getHeaders } from './client'

const API_BASE = '/api'

// ─── Types ───────────────────────────────────────────────────────

export interface KBDisease {
  id: string
  name: string
  symptoms: string[]
  description: string
  treatment: string
  when_to_see_doctor: string
  severity: string
  has_embedding: boolean
}

export interface KBDiseaseList {
  total: number
  page: number
  size: number
  items: KBDisease[]
}

export interface KBGuidelineChunk {
  id: string
  text: string
  full_text: string
  metadata: Record<string, string>
}

export interface KBGuidelineList {
  total: number
  page: number
  size: number
  items: KBGuidelineChunk[]
}

export interface KBStats {
  disease_count: number
  embedded_count: number
  guideline_chunk_count: number
}

export interface KBSearchResult {
  mode: string
  query: string
  results: Array<{
    text?: string
    score: number
    name?: string
    severity?: string
    matched_symptoms?: string[]
  }>
}

// ─── Diseases ────────────────────────────────────────────────────

export async function listKBDiseases(page = 1, size = 20, search = ''): Promise<KBDiseaseList> {
  const params = new URLSearchParams({ page: String(page), size: String(size), search })
  const response = await fetch(`${API_BASE}/kb/diseases?${params}`, {
    headers: await getHeaders(),
  })
  if (response.status === 401) throw new Error('UNAUTHORIZED')
  if (response.status === 403) throw new Error('FORBIDDEN')
  if (!response.ok) throw new Error(`请求失败 (${response.status})`)
  return response.json()
}

export async function getKBDisease(id: string): Promise<KBDisease> {
  const response = await fetch(`${API_BASE}/kb/diseases/${id}`, {
    headers: await getHeaders(),
  })
  if (!response.ok) throw new Error(`获取失败 (${response.status})`)
  return response.json()
}

export async function createKBDisease(data: Omit<KBDisease, 'id' | 'has_embedding'>): Promise<{ id: string; name: string }> {
  const response = await fetch(`${API_BASE}/kb/diseases`, {
    method: 'POST',
    headers: await getHeaders(),
    body: JSON.stringify(data),
  })
  if (response.status === 409) throw new Error('疾病名称已存在')
  if (!response.ok) {
    const err = await response.json().catch(() => null)
    throw new Error(err?.detail || `创建失败 (${response.status})`)
  }
  return response.json()
}

export async function updateKBDisease(id: string, data: Partial<Omit<KBDisease, 'id' | 'has_embedding'>>): Promise<void> {
  const response = await fetch(`${API_BASE}/kb/diseases/${id}`, {
    method: 'PUT',
    headers: await getHeaders(),
    body: JSON.stringify(data),
  })
  if (!response.ok) {
    const err = await response.json().catch(() => null)
    throw new Error(err?.detail || `更新失败 (${response.status})`)
  }
}

export async function deleteKBDisease(id: string): Promise<void> {
  const response = await fetch(`${API_BASE}/kb/diseases/${id}`, {
    method: 'DELETE',
    headers: await getHeaders(),
  })
  if (!response.ok) throw new Error(`删除失败 (${response.status})`)
}

// ─── Guidelines ──────────────────────────────────────────────────

export async function listKBGuidelines(page = 1, size = 20, search = ''): Promise<KBGuidelineList> {
  const params = new URLSearchParams({ page: String(page), size: String(size), search })
  const response = await fetch(`${API_BASE}/kb/guidelines?${params}`, {
    headers: await getHeaders(),
  })
  if (!response.ok) throw new Error(`请求失败 (${response.status})`)
  return response.json()
}

export async function addKBGuideline(title: string, content: string): Promise<{ chunks: number }> {
  const response = await fetch(`${API_BASE}/kb/guidelines`, {
    method: 'POST',
    headers: await getHeaders(),
    body: JSON.stringify({ title, content }),
  })
  if (!response.ok) {
    const err = await response.json().catch(() => null)
    throw new Error(err?.detail || `添加失败 (${response.status})`)
  }
  return response.json()
}

export async function deleteKBGuideline(id: string): Promise<void> {
  const response = await fetch(`${API_BASE}/kb/guidelines/${id}`, {
    method: 'DELETE',
    headers: await getHeaders(),
  })
  if (!response.ok) throw new Error(`删除失败 (${response.status})`)
}

// ─── Stats ───────────────────────────────────────────────────────

export async function getKBStats(): Promise<KBStats> {
  const response = await fetch(`${API_BASE}/kb/stats`, {
    headers: await getHeaders(),
  })
  if (!response.ok) throw new Error(`获取统计失败 (${response.status})`)
  return response.json()
}

// ─── Search Test ─────────────────────────────────────────────────

export async function testKBSearch(query: string, mode: 'guidelines' | 'diseases', k = 5): Promise<KBSearchResult> {
  const response = await fetch(`${API_BASE}/kb/search/test`, {
    method: 'POST',
    headers: await getHeaders(),
    body: JSON.stringify({ query, mode, k }),
  })
  if (!response.ok) {
    const err = await response.json().catch(() => null)
    throw new Error(err?.detail || `搜索失败 (${response.status})`)
  }
  return response.json()
}
