'use client';

import { useState, useRef, useEffect } from 'react';
import { ChatStage, Message } from '@/types';
import { sendMessageStream } from '@/api/client';
import { randomUUID } from '@/lib/uuid';

export function useChat(sessionId: string | undefined, onSessionCreated: (id: string) => void) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [symptoms, setSymptoms] = useState<string[]>([]);
  const [needMoreInfo, setNeedMoreInfo] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const setLastAssistantStage = (stage: ChatStage) => {
    setMessages((prev) => {
      const updated = [...prev];
      const lastMsg = updated[updated.length - 1];
      if (lastMsg && lastMsg.role === 'assistant') {
        updated[updated.length - 1] = { ...lastMsg, stage };
      }
      return updated;
    });
  };

  // 组件卸载时中止正在进行的流
  useEffect(() => {
    return () => {
      abortRef.current?.();
    };
  }, []);

  const sendMessage = (content: string) => {
    if (!content.trim() || loading) return;

    // 中止之前的流
    abortRef.current?.();

    const userMessage: Message = { id: randomUUID(), role: 'user', content };
    setMessages((prev) => [...prev, userMessage]);
    setLoading(true);
    setNeedMoreInfo(false);

    const aiMessage: Message = { id: randomUUID(), role: 'assistant', content: '' };
    setMessages((prev) => [...prev, aiMessage]);

    const abort = sendMessageStream(
      content,
      sessionId,
      (chunk, stage) => {
        setMessages((prev) => {
          const updated = [...prev];
          const lastMsg = updated[updated.length - 1];
          if (lastMsg && lastMsg.role === 'assistant') {
            updated[updated.length - 1] = {
              ...lastMsg,
              content: lastMsg.content + chunk,
              stage: lastMsg.stage ?? stage,
            };
          }
          return updated;
        });
      },
      (meta) => {
        if (meta.session_id) onSessionCreated(meta.session_id);
        if (meta.symptoms) setSymptoms(meta.symptoms);
        if (typeof meta.need_more_info === 'boolean') setNeedMoreInfo(meta.need_more_info);
        if (meta.stage) setLastAssistantStage(meta.stage);
      },
      (stage) => setLastAssistantStage(stage),
      () => setLoading(false),
      (error) => {
        console.error('Failed to send message:', error);
        setMessages((prev) => {
          const updated = [...prev];
          const lastMsg = updated[updated.length - 1];
          if (lastMsg && lastMsg.role === 'assistant' && lastMsg.content === '') {
            updated[updated.length - 1] = {
              ...lastMsg,
              content: `请求失败：${error.message || '无法连接到后端服务'}`,
            };
          }
          return updated;
        });
        setLoading(false);
      }
    );
    abortRef.current = abort;
  };

  const resetChat = () => {
    setMessages([]);
    setSymptoms([]);
    setNeedMoreInfo(false);
  };

  const loadMessages = (msgs: Message[]) => {
    setMessages(msgs.map((m) => ({ ...m, id: m.id || randomUUID() })));
    setNeedMoreInfo(false);
  };

  return {
    messages,
    loading,
    symptoms,
    needMoreInfo,
    messagesEndRef,
    sendMessage,
    resetChat,
    loadMessages,
  };
}
