import { ChatResponse, ChatStage, Session, StreamMeta, SymptomCategory } from '@/types';

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
  onChunk: (content: string, stage: ChatStage) => void,
  onMeta: (meta: StreamMeta) => void,
  onStage: (stage: ChatStage) => void,
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
            // ignore parse errors
          }
        }
      }
    }

    if (buffer.startsWith('data: ')) {
      try {
        handleEvent(JSON.parse(buffer.slice(6)));
      } catch (e) {
        // ignore
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
