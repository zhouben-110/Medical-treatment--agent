export default function Home() {
  return (
    <main className="flex min-h-screen">
      <div className="w-64 bg-gray-100 p-4">
        <h2 className="text-lg font-bold mb-4">历史记录</h2>
      </div>
      <div className="flex-1 flex flex-col">
        <div className="flex-1 p-4">
          <h1 className="text-2xl font-bold">医疗健康助手</h1>
          <p className="text-gray-600 mt-2">描述您的症状，AI将为您提供初步建议</p>
        </div>
        <div className="p-4 border-t">
          <div className="flex gap-2">
            <input
              className="flex-1 p-2 border rounded"
              placeholder="描述您的症状..."
            />
            <button className="px-4 py-2 bg-blue-500 text-white rounded">
              发送
            </button>
          </div>
        </div>
      </div>
    </main>
  );
}
