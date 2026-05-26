import { Message } from '@/types';

interface Props {
  message: Message;
}

const STAGE_META: Record<string, { label: string; badgeClass: string; borderClass: string }> = {
  questioning: {
    label: '追问',
    badgeClass: 'bg-blue-50 text-blue-600 border border-blue-200',
    borderClass: 'border-l-4 border-blue-400',
  },
  completed: {
    label: '诊断与建议',
    badgeClass: 'bg-green-50 text-green-700 border border-green-200',
    borderClass: 'border-l-4 border-green-500',
  },
};

export default function MessageBubble({ message }: Props) {
  const isUser = message.role === 'user';
  const stageInfo = !isUser && message.stage ? STAGE_META[message.stage] : undefined;

  const bubbleBase = isUser
    ? 'bg-blue-500 text-white rounded-br-none'
    : 'bg-gray-200 text-gray-800 rounded-bl-none';

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4`}>
      <div
        className={`max-w-[70%] p-3 rounded-lg ${bubbleBase} ${stageInfo?.borderClass ?? ''}`}
      >
        {stageInfo && (
          <span
            className={`inline-block text-xs px-2 py-0.5 rounded mb-1 ${stageInfo.badgeClass}`}
          >
            {stageInfo.label}
          </span>
        )}
        <p className="whitespace-pre-wrap">{message.content}</p>
      </div>
    </div>
  );
}
