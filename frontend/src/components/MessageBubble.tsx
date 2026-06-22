import { Message } from '@/types';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface Props {
  message: Message;
}

const STAGE_META: Record<string, { label: string; badgeClass: string; borderClass: string }> = {
  questioning: {
    label: '追问',
    badgeClass: 'bg-blue-50 text-blue-600 border border-blue-200 dark:bg-blue-900/30 dark:text-blue-400 dark:border-blue-700',
    borderClass: 'border-l-4 border-blue-400',
  },
  completed: {
    label: '诊断与建议',
    badgeClass: 'bg-green-50 text-green-700 border border-green-200 dark:bg-green-900/30 dark:text-green-400 dark:border-green-700',
    borderClass: 'border-l-4 border-green-500',
  },
};

export default function MessageBubble({ message }: Props) {
  const isUser = message.role === 'user';
  const stageInfo = !isUser && message.stage ? STAGE_META[message.stage] : undefined;

  const bubbleBase = isUser
    ? 'bg-blue-500 text-white rounded-br-none'
    : 'bg-gray-200 text-gray-800 rounded-bl-none dark:bg-gray-700 dark:text-gray-200';

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
        {isUser ? (
          <p className="whitespace-pre-wrap">{message.content}</p>
        ) : (
          <div className="prose prose-sm dark:prose-invert max-w-none prose-p:my-1 prose-headings:my-2 prose-ul:my-1 prose-ol:my-1 prose-li:my-0">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {message.content}
            </ReactMarkdown>
          </div>
        )}
      </div>
    </div>
  );
}
