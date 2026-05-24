import { ChatResponse, Session, SymptomCategory } from '@/types';

const API_BASE = '/api';

export async function sendMessage(message: string, sessionId?: string): Promise<ChatResponse> {
  const response = await fetch(`${API_BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, session_id: sessionId }),
  });
  return response.json();
}

export function sendMessageStream(
  message: string,
  sessionId: string | undefined,
  onChunk: (content: string) => void,
  onMeta: (meta: { session_id: string; symptoms: string[] }) => void,
  onDone: () => void,
  onError: (error: Error) => void
): () => void {
  const controller = new AbortController();

  fetch(`${API_BASE}/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
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

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6));
            if (data.type === 'meta') {
              onMeta({ session_id: data.session_id, symptoms: data.symptoms });
            } else if (data.type === 'chunk') {
              onChunk(data.content);
            } else if (data.type === 'done') {
              onDone();
            }
          } catch (e) {
            // ignore parse errors
          }
        }
      }
    }
  }).catch((err) => {
    if (err.name !== 'AbortError') {
      onError(err);
    }
  });

  return () => controller.abort();
}

export async function getHistory(): Promise<Session[]> {
  const response = await fetch(`${API_BASE}/history`);
  return response.json();
}

export async function getSessionDetail(sessionId: string) {
  const response = await fetch(`${API_BASE}/history/${sessionId}`);
  return response.json();
}

export async function getSymptoms(): Promise<{ categories: SymptomCategory[] }> {
  const response = await fetch(`${API_BASE}/symptoms`);
  return response.json();
}
