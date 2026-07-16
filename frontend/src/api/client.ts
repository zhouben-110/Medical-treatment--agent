import { ChatResponse, ChatStage, Session, StreamMeta, SymptomCategory } from '@/types';

const API_BASE = '/api';

function getCookie(name: string) {
  if (typeof document === 'undefined') return null;
  const nameEQ = name + "=";
  const ca = document.cookie.split(';');
  for(let i=0;i < ca.length;i++) {
    let c = ca[i];
    while (c.charAt(0)==' ') c = c.substring(1,c.length);
    if (c.indexOf(nameEQ) == 0) return c.substring(nameEQ.length,c.length);
  }
  return null;
}

async function getHeaders(): Promise<Record<string, string>> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };

  const token = getCookie('access-token');
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  return headers;
}

export async function sendMessage(message: string, sessionId?: string): Promise<ChatResponse> {
  const response = await fetch(`${API_BASE}/chat`, {
    method: 'POST',
    headers: await getHeaders(),
    body: JSON.stringify({ message, session_id: sessionId }),
  });

  if (response.status === 401) {
    throw new Error('UNAUTHORIZED');
  }

  return response.json();
}

export function sendMessageStream(
  message: string,
  sessionId: string | undefined,
  onChunk: (content: string, stage: ChatStage) => void,
  onMeta: (meta: StreamMeta) => void,
  onStage: (stage: ChatStage) => void,
  onDone: () => void,
  onError: (error: Error) => void
): () => void {
  const controller = new AbortController();

  // 异步获取 headers 然后发起请求
  getHeaders().then((headers) => {
    fetch(`${API_BASE}/chat/stream`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ message, session_id: sessionId }),
      signal: controller.signal,
    }).then(async (response) => {
      if (response.status === 401) {
        throw new Error('UNAUTHORIZED');
      }
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error('No reader');

      const decoder = new TextDecoder();
      let buffer = '';
      let doneCalled = false;

      const safeOnDone = () => {
        if (!doneCalled) {
          doneCalled = true;
          onDone();
        }
      };

      const handleEvent = (data: any) => {
        if (data.type === 'meta') {
          onMeta({
            session_id: data.session_id,
            symptoms: data.symptoms,
            stage: data.stage,
            need_more_info: data.need_more_info,
            possible_diseases: data.possible_diseases,
          });
        } else if (data.type === 'stage') {
          onStage(data.stage);
        } else if (data.type === 'chunk') {
          onChunk(data.content, data.stage);
        } else if (data.type === 'done') {
          safeOnDone();
        } else if (data.type === 'error') {
          onError(new Error(data.content || 'stream error'));
        }
      };

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              handleEvent(JSON.parse(line.slice(6)));
            } catch (e) {
              console.debug('SSE parse error:', e, 'line:', line);
            }
          }
        }
      }

      if (buffer.startsWith('data: ')) {
        try {
          handleEvent(JSON.parse(buffer.slice(6)));
        } catch (e) {
          console.debug('SSE parse error:', e, 'buffer:', buffer);
        }
      }

      safeOnDone();
    }).catch((err) => {
      if (err.name !== 'AbortError') {
        onError(err);
      }
    });
  }).catch((err) => {
    onError(err);
  });

  return () => controller.abort();
}

export async function getHistory(): Promise<Session[]> {
  const response = await fetch(`${API_BASE}/history`, {
    headers: await getHeaders(),
  });

  if (response.status === 401) {
    throw new Error('UNAUTHORIZED');
  }

  return response.json();
}

export async function getSessionDetail(sessionId: string) {
  const response = await fetch(`${API_BASE}/history/${sessionId}`, {
    headers: await getHeaders(),
  });

  if (response.status === 401) {
    throw new Error('UNAUTHORIZED');
  }

  return response.json();
}

export async function deleteSession(sessionId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/history/${sessionId}`, {
    method: 'DELETE',
    headers: await getHeaders(),
  });

  if (response.status === 401) {
    throw new Error('UNAUTHORIZED');
  }

  if (!response.ok) {
    throw new Error(`删除失败 (${response.status})`);
  }
}

export async function getSymptoms(): Promise<{ categories: SymptomCategory[] }> {
  const response = await fetch(`${API_BASE}/symptoms`, {
    headers: await getHeaders(),
  });

  if (response.status === 401) {
    throw new Error('UNAUTHORIZED');
  }

  return response.json();
}

export async function updateSymptoms(sessionId: string, symptoms: string[]): Promise<void> {
  const response = await fetch(`${API_BASE}/chat/symptoms/update`, {
    method: 'POST',
    headers: await getHeaders(),
    body: JSON.stringify({ session_id: sessionId, symptoms }),
  });

  if (response.status === 401) {
    throw new Error('UNAUTHORIZED');
  }

  if (!response.ok) {
    throw new Error(`更新失败 (${response.status})`);
  }
}

// ========== 管理员 API ==========

export interface AdminUser {
  id: string;
  email: string;
  role: string;
  is_active: boolean;
  created_at: string;
}

export interface AdminUserList {
  total: number;
  page: number;
  size: number;
  items: AdminUser[];
}

export async function getAdminUsers(page = 1, size = 20): Promise<AdminUserList> {
  const response = await fetch(`${API_BASE}/admin/users?page=${page}&size=${size}`, {
    headers: await getHeaders(),
  });

  if (response.status === 403) {
    throw new Error('FORBIDDEN');
  }
  if (response.status === 401) {
    throw new Error('UNAUTHORIZED');
  }

  return response.json();
}

export async function updateUserRole(userId: string, role: string): Promise<{ id: string; email: string; role: string }> {
  const response = await fetch(`${API_BASE}/admin/users/${userId}/role`, {
    method: 'PUT',
    headers: await getHeaders(),
    body: JSON.stringify({ role }),
  });

  if (response.status === 403) {
    throw new Error('FORBIDDEN');
  }
  if (response.status === 401) {
    throw new Error('UNAUTHORIZED');
  }

  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new Error(data?.detail || `操作失败 (${response.status})`);
  }

  return response.json();
}

export async function updateUserStatus(userId: string, isActive: boolean): Promise<{ id: string; email: string; is_active: boolean }> {
  const response = await fetch(`${API_BASE}/admin/users/${userId}/status`, {
    method: 'PUT',
    headers: await getHeaders(),
    body: JSON.stringify({ is_active: isActive }),
  });

  if (response.status === 403) {
    throw new Error('FORBIDDEN');
  }
  if (response.status === 401) {
    throw new Error('UNAUTHORIZED');
  }

  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new Error(data?.detail || `操作失败 (${response.status})`);
  }

  return response.json();
}

export async function deleteUser(userId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/admin/users/${userId}`, {
    method: 'DELETE',
    headers: await getHeaders(),
  });

  if (response.status === 403) {
    throw new Error('FORBIDDEN');
  }
  if (response.status === 401) {
    throw new Error('UNAUTHORIZED');
  }

  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new Error(data?.detail || `操作失败 (${response.status})`);
  }
}

export async function changePassword(password: string): Promise<void> {
  const response = await fetch(`${API_BASE}/auth/change-password`, {
    method: 'POST',
    headers: await getHeaders(),
    body: JSON.stringify({ password }),
  });

  if (response.status === 401) {
    throw new Error('UNAUTHORIZED');
  }

  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new Error(data?.detail || '修改密码失败');
  }
}
