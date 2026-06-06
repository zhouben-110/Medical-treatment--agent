export type ChatStage = 'analyzing' | 'questioning' | 'diagnosing' | 'completed' | 'unknown';

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  stage?: ChatStage;
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
  stage: ChatStage;
  symptoms: string[];
  session_id: string;
  need_more_info?: boolean;
  possible_diseases?: string[];
}

export interface StreamMeta {
  session_id: string;
  symptoms?: string[];
  stage?: ChatStage;
  need_more_info?: boolean;
  possible_diseases?: string[];
}

export interface SymptomCategory {
  name: string;
  symptoms: string[];
}
