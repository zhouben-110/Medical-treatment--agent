import { ChatResponse, ChatStage, Session, StreamMeta, SymptomCategory } from '@/types';

const API_BASE = '/api';
const API_KEY = process.env.NEXT_PUBLIC_API_KEY || '';

function getHeaders(): Record<string, string> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (API_KEY) {
    headers['X-API-Key'] = API_KEY;
  }
  return headers;
}

export async function sendMessage(message: string, sessionId?: string): Promise<ChatResponse> {
  const response = await fetch(`${API_BASE}/chat`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify({ message, session_id: sessionId }),
  });
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

  fetch(`${API_BASE}/chat/stream`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify({ message, session_id: sessionId }),
    signal: controller.signal,
  }).then(async (response) => {
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

  return () => controller.abort();
}

export async function getHistory(): Promise<Session[]> {
  const response = await fetch(`${API_BASE}/history`, { headers: getHeaders() });
  return response.json();
}

export async function getSessionDetail(sessionId: string) {
  const response = await fetch(`${API_BASE}/history/${sessionId}`, { headers: getHeaders() });
  return response.json();
}

export async function deleteSession(sessionId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/history/${sessionId}`, {
    method: 'DELETE',
    headers: getHeaders(),
  });
  if (!response.ok) {
    throw new Error(`删除失败 (${response.status})`);
  }
}

export async function getSymptoms(): Promise<{ categories: SymptomCategory[] }> {
  const response = await fetch(`${API_BASE}/symptoms`, { headers: getHeaders() });
  return response.json();
}
