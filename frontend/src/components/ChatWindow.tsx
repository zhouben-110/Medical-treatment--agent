'use client';

import { useState, useEffect, useCallback } from 'react';
import { useChat } from '@/hooks/useChat';
import { useSession } from '@/hooks/useSession';
import { useToast } from '@/contexts/ToastContext';
import { getSymptoms } from '@/api/client';
import { SymptomCategory } from '@/types';
import MessageBubble from './MessageBubble';
import SymptomTags from './SymptomTags';
import Sidebar from './Sidebar';

export default function ChatWindow() {
  const [input, setInput] = useState('');
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [symptomCategories, setSymptomCategories] = useState<SymptomCategory[]>([]);
  const { showToast, confirm } = useToast();

  const {
    sessions, currentSessionId, setCurrentSessionId,
    loadHistory, loadSession, deleteSessionById, newSession,
  } = useSession();

  const {
    messages, loading, symptoms, needMoreInfo,
    messagesEndRef, sendMessage, resetChat, loadMessages,
  } = useChat(currentSessionId, (id) => setCurrentSessionId(id));

  // 加载症状分类
  useEffect(() => {
    getSymptoms()
      .then((data) => setSymptomCategories(data.categories))
      .catch(() => {}); // 静默失败
  }, []);

  const handleSend = useCallback(() => {
    if (!input.trim()) return;
    sendMessage(input);
    setInput('');
    setSidebarOpen(false);
  }, [input, sendMessage]);

  const handleNewSession = () => {
    newSession();
    resetChat();
    setSidebarOpen(false);
  };

  const handleSelectSession = async (sessionId: string) => {
    const msgs = await loadSession(sessionId);
    loadMessages(msgs);
    setSidebarOpen(false);
  };

  const handleDeleteSession = async (sessionId: string) => {
    const ok = await confirm('确定删除该会话吗？此操作不可恢复。');
    if (!ok) return;
    try {
      await deleteSessionById(sessionId);
      if (currentSessionId === sessionId) {
        handleNewSession();
      }
      showToast('会话已删除', 'success');
    } catch (err) {
      showToast(err instanceof Error ? err.message : '删除失败', 'error');
    }
  };

  const handleSymptomClick = (symptom: string) => {
    setInput((prev) => (prev ? prev + '，' + symptom : symptom));
  };

  return (
    <div className="flex h-screen relative">
      {/* 移动端遮罩 */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-30 md:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* 侧边栏 */}
      <div className={`
        fixed md:static inset-y-0 left-0 z-40 transform transition-transform duration-200
        ${sidebarOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}
      `}>
        <Sidebar
          sessions={sessions}
          currentSessionId={currentSessionId}
          onSelectSession={handleSelectSession}
          onNewSession={handleNewSession}
          onDeleteSession={handleDeleteSession}
        />
      </div>

      <div className="flex-1 flex flex-col min-w-0">
        {/* 移动端顶栏 */}
        <div className="md:hidden flex items-center gap-2 p-2 border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800">
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="p-2 text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg"
            aria-label="切换侧边栏"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>
          <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
            {currentSessionId ? '当前对话' : '新对话'}
          </span>
        </div>

        <div className="flex-1 overflow-y-auto p-4">
          {messages.length === 0 && (
            <div className="text-center text-gray-500 dark:text-gray-400 mt-20">
              <h2 className="text-2xl font-bold mb-2 text-gray-900 dark:text-gray-100">医疗健康助手</h2>
              <p className="mb-8">描述您的症状，AI将为您提供初步建议</p>

              {/* 症状快捷选择 */}
              {symptomCategories.length > 0 && (
                <div className="max-w-2xl mx-auto text-left">
                  <p className="text-sm font-medium text-gray-600 dark:text-gray-400 mb-3">常见症状分类：</p>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    {symptomCategories.map((category) => (
                      <div
                        key={category.name}
                        className="p-3 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 hover:border-blue-300 dark:hover:border-blue-600 transition"
                      >
                        <p className="text-sm font-semibold text-gray-800 dark:text-gray-200 mb-2">{category.name}</p>
                        <div className="flex flex-wrap gap-1.5">
                          {category.symptoms.map((symptom) => (
                            <button
                              key={symptom}
                              onClick={() => handleSymptomClick(symptom)}
                              className="px-2 py-0.5 text-xs bg-blue-50 text-blue-600 rounded-full hover:bg-blue-100 dark:bg-blue-900/30 dark:text-blue-400 dark:hover:bg-blue-900/50 transition"
                            >
                              {symptom}
                            </button>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
          {messages.map((msg) => (
            <MessageBubble key={msg.id} message={msg} />
          ))}
          {symptoms.length > 0 && <SymptomTags symptoms={symptoms} />}
          {loading && (
            <div className="flex justify-start mb-4">
              <div className="bg-gray-200 dark:bg-gray-700 p-3 rounded-lg rounded-bl-none">
                <div className="flex space-x-2">
                  <div className="w-2 h-2 bg-gray-500 dark:bg-gray-400 rounded-full animate-bounce" />
                  <div className="w-2 h-2 bg-gray-500 dark:bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }} />
                  <div className="w-2 h-2 bg-gray-500 dark:bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }} />
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>
        <div className="p-4 border-t border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800">
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
              className="flex-1 p-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:border-blue-500 dark:focus:border-blue-400 resize-none bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 placeholder-gray-400 dark:placeholder-gray-500"
              placeholder={needMoreInfo ? '请回答上面的追问...' : '描述您的症状...（Shift+Enter 换行）'}
              disabled={loading}
            />
            <button
              onClick={handleSend}
              disabled={loading}
              className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:bg-gray-400 dark:disabled:bg-gray-600 transition"
            >
              发送
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
