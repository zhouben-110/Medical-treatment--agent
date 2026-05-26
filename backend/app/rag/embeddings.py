"""DashScope 嵌入模型封装"""

import dashscope
from typing import List


class DashScopeEmbeddings:
    """使用 DashScope API 的嵌入模型"""

    def __init__(self, api_key: str, model: str = "text-embedding-v3"):
        dashscope.api_key = api_key
        self.model = model

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """批量嵌入文档"""
        if not texts:
            return []

        from dashscope import TextEmbedding
        result = TextEmbedding.call(
            model=self.model,
            input=texts,
        )

        if result.output and 'embeddings' in result.output:
            sorted_embs = sorted(result.output['embeddings'], key=lambda x: x['text_index'])
            return [item['embedding'] for item in sorted_embs]

        raise ValueError(f"DashScope embedding failed: {result}")

    def embed_query(self, text: str) -> List[float]:
        """嵌入单条查询"""
        return self.embed_documents([text])[0]
