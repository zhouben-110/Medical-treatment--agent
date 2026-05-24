export interface Message {
  role: 'user' | 'assistant';
  content: string;
  timestamp?: string;
}

export interface Session {
  id: string;
  title: string;
  created_at: string;
  message_count: number;
}

export interface ChatResponse {
  reply: string;
  stage: string;
  symptoms: string[];
  session_id: string;
}

export interface SymptomCategory {
  name: string;
  symptoms: string[];
}
