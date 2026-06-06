'use client';

import { useState } from 'react';
import { useChat } from '@/hooks/useChat';
import { useSession } from '@/hooks/useSession';
import MessageBubble from './MessageBubble';
import SymptomTags from './SymptomTags';
import Sidebar from './Sidebar';

export default function ChatWindow() {
  const [input, setInput] = useState('');
  const {
    sessions, currentSessionId, setCurrentSessionId,
    loadHistory, loadSession, deleteSessionById, newSession,
  } = useSession();

  const {
    messages, loading, symptoms, needMoreInfo,
    messagesEndRef, sendMessage, resetChat, loadMessages,
  } = useChat(currentSessionId, (id) => setCurrentSessionId(id));

  const handleSend = () => {
    if (!input.trim()) return;
    sendMessage(input);
    setInput('');
  };

  const handleNewSession = () => {
    newSession();
    resetChat();
  };

  const handleSelectSession = async (sessionId: string) => {
    const msgs = await loadSession(sessionId);
    loadMessages(msgs);
  };

  const handleDeleteSession = async (sessionId: string) => {
    try {
      await deleteSessionById(sessionId);
      if (currentSessionId === sessionId) {
        handleNewSession();
      }
    } catch (err) {
      console.error('Failed to delete session:', err);
      alert(err instanceof Error ? err.message : '删除失败');
    }
  };

  return (
    <div className="flex h-screen">
      <Sidebar
        sessions={sessions}
        currentSessionId={currentSessionId}
        onSelectSession={handleSelectSession}
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
          {messages.map((msg) => (
            <MessageBubble key={msg.id} message={msg} />
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
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleSend();
                }
              }}
              rows={2}
              className="flex-1 p-2 border rounded focus:outline-none focus:border-blue-500 resize-none"
              placeholder={needMoreInfo ? '请回答上面的追问...' : '描述您的症状...（Shift+Enter 换行）'}
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
