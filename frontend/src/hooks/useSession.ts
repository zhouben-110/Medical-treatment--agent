'use client';

import { useState, useEffect } from 'react';
import { Session } from '@/types';
import { getHistory, getSessionDetail, deleteSession } from '@/api/client';

export function useSession() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string>();

  useEffect(() => {
    loadHistory();
  }, []);

  const loadHistory = async () => {
    const data = await getHistory();
    setSessions(data);
  };

  const loadSession = async (sessionId: string) => {
    const data = await getSessionDetail(sessionId);
    setCurrentSessionId(sessionId);
    return data.messages;
  };

  const deleteSessionById = async (sessionId: string) => {
    await deleteSession(sessionId);
    setSessions((prev) => prev.filter((s) => s.id !== sessionId));
  };

  const newSession = () => {
    setCurrentSessionId(undefined);
  };

  return {
    sessions,
    currentSessionId,
    setCurrentSessionId,
    loadHistory,
    loadSession,
    deleteSessionById,
    newSession,
  };
}
