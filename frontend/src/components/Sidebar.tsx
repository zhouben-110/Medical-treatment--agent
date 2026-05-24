import { Session } from '@/types';

interface Props {
  sessions: Session[];
  currentSessionId?: string;
  onSelectSession: (id: string) => void;
  onNewSession: () => void;
}

export default function Sidebar({ sessions, currentSessionId, onSelectSession, onNewSession }: Props) {
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
            className={`p-3 mb-2 rounded cursor-pointer ${
              currentSessionId === session.id
                ? 'bg-blue-100 border-blue-300'
                : 'bg-white hover:bg-gray-50'
            }`}
          >
            <p className="text-sm font-medium truncate">{session.title}</p>
            <p className="text-xs text-gray-500">{session.message_count} 条消息</p>
          </div>
        ))}
      </div>
    </div>
  );
}
