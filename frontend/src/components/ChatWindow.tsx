'use client';

import { useState, useRef, useEffect } from 'react';
import { ChatStage, Message, Session } from '@/types';
import { sendMessageStream, getHistory, getSessionDetail, deleteSession } from '@/api/client';
import MessageBubble from './MessageBubble';
import SymptomTags from './SymptomTags';
import Sidebar from './Sidebar';

export default function ChatWindow() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string>();
  const [symptoms, setSymptoms] = useState<string[]>([]);
  const [needMoreInfo, setNeedMoreInfo] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    loadHistory();
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const loadHistory = async () => {
    const data = await getHistory();
    setSessions(data);
  };

  const loadSession = async (sessionId: string) => {
    const data = await getSessionDetail(sessionId);
    setMessages(data.messages);
    setCurrentSessionId(sessionId);
    setNeedMoreInfo(false);
  };

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

  const handleSend = async () => {
    if (!input.trim() || loading) return;

    const userMessage: Message = { role: 'user', content: input };
    setMessages((prev) => [...prev, userMessage]);
    const userMsg = input;
    setInput('');
    setLoading(true);
    setNeedMoreInfo(false);

    const aiMessage: Message = { role: 'assistant', content: '' };
    setMessages((prev) => [...prev, aiMessage]);

    sendMessageStream(
      userMsg,
      currentSessionId,
      // onChunk
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
      // onMeta
      (meta) => {
        if (meta.session_id) setCurrentSessionId(meta.session_id);
        if (meta.symptoms) setSymptoms(meta.symptoms);
        if (typeof meta.need_more_info === 'boolean') setNeedMoreInfo(meta.need_more_info);
        if (meta.stage) setLastAssistantStage(meta.stage);
      },
      // onStage
      (stage) => {
        setLastAssistantStage(stage);
      },
      // onDone
      () => {
        setLoading(false);
        loadHistory();
      },
      // onError
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
  };

  const handleNewSession = () => {
    setMessages([]);
    setCurrentSessionId(undefined);
    setSymptoms([]);
    setNeedMoreInfo(false);
  };

  const handleDeleteSession = async (sessionId: string) => {
    try {
      await deleteSession(sessionId);
    } catch (err) {
      console.error('Failed to delete session:', err);
      alert(err instanceof Error ? err.message : '删除失败');
      return;
    }
    setSessions((prev) => prev.filter((s) => s.id !== sessionId));
    if (currentSessionId === sessionId) {
      handleNewSession();
    }
  };

  return (
    <div className="flex h-screen">
      <Sidebar
        sessions={sessions}
        currentSessionId={currentSessionId}
        onSelectSession={loadSession}
        onNewSession={handleNewSession}
        onDeleteSession={handleDeleteSession}
      />
      <div className="flex-1 flex flex-col">
        <div className="flex-1 overflow-y-auto p-4">
          {messages.length === 0 && (
            <div className="text-center text-gray-500 mt-20">
              <h2 className="text-2xl font-bold mb-2">医疗健康助手</h2>
              <p>描述您的症状，AI将为您提供初步建议</p>
            </div>
          )}
          {messages.map((msg, i) => (
            <MessageBubble key={i} message={msg} />
          ))}
          {symptoms.length > 0 && <SymptomTags symptoms={symptoms} />}
          {loading && (
            <div className="flex justify-start mb-4">
              <div className="bg-gray-200 p-3 rounded-lg rounded-bl-none">
                <div className="flex space-x-2">
                  <div className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" />
                  <div className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }} />
                  <div className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }} />
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>
        <div className="p-4 border-t">
          <div className="flex gap-2">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && handleSend()}
              className="flex-1 p-2 border rounded focus:outline-none focus:border-blue-500"
              placeholder={needMoreInfo ? '请回答上面的追问...' : '描述您的症状...'}
              disabled={loading}
            />
            <button
              onClick={handleSend}
              disabled={loading}
              className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 disabled:bg-gray-400"
            >
              发送
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
