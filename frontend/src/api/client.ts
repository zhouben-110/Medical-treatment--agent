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
