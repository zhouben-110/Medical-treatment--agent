import type { Metadata } from 'next';
import { AuthProvider } from '@/contexts/AuthContext';
import UserNav from '@/components/UserNav';
import './globals.css';

export const metadata: Metadata = {
  title: '医疗健康助手',
  description: 'AI驱动的症状分析与治疗建议',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-CN">
      <body>
        <AuthProvider>
          <div className="min-h-screen flex flex-col">
            <header className="bg-white border-b border-gray-200 px-4 py-3">
              <div className="max-w-7xl mx-auto flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="w-8 h-8 bg-blue-100 rounded-lg flex items-center justify-center">
                    <svg className="w-5 h-5 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" />
                    </svg>
                  </div>
                  <h1 className="text-lg font-semibold text-gray-900">医疗健康助手</h1>
                </div>
                <UserNav />
              </div>
            </header>
            <main className="flex-1">
              {children}
            </main>
          </div>
        </AuthProvider>
      </body>
    </html>
  );
}
