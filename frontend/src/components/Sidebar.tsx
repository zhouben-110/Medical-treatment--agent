import { Session } from '@/types';

interface Props {
  sessions: Session[];
  currentSessionId?: string;
  onSelectSession: (id: string) => void;
  onNewSession: () => void;
  onDeleteSession: (id: string) => void;
}

export default function Sidebar({
  sessions,
  currentSessionId,
  onSelectSession,
  onNewSession,
  onDeleteSession,
}: Props) {
  const handleDelete = (e: React.MouseEvent, session: Session) => {
    e.stopPropagation();
    const ok = window.confirm(`确定删除会话「${session.title}」吗？此操作不可恢复。`);
    if (ok) onDeleteSession(session.id);
  };

  return (
    <div className="w-64 bg-gray-100 p-4 flex flex-col">
      <button
        onClick={onNewSession}
        className="w-full mb-4 px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
      >
        + 新对话
      </button>
      <h3 className="text-sm font-semibold text-gray-500 mb-2">历史记录</h3>
      <div className="flex-1 overflow-y-auto">
        {sessions.map((session) => (
          <div
            key={session.id}
            onClick={() => onSelectSession(session.id)}
            className={`group relative p-3 mb-2 rounded cursor-pointer ${
              currentSessionId === session.id
                ? 'bg-blue-100 border-blue-300'
                : 'bg-white hover:bg-gray-50'
            }`}
          >
            <p className="text-sm font-medium truncate pr-7">{session.title}</p>
            <p className="text-xs text-gray-500">{session.message_count} 条消息</p>
            <button
              onClick={(e) => handleDelete(e, session)}
              title="删除会话"
              aria-label="删除会话"
              className="absolute top-2 right-2 w-6 h-6 flex items-center justify-center rounded text-gray-400 opacity-0 group-hover:opacity-100 hover:bg-red-100 hover:text-red-600 transition"
            >
              ×
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
