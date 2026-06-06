"""DashScope 嵌入模型封装"""

import dashscope
from typing import List

BATCH_SIZE = 10


class DashScopeEmbeddings:
    """使用 DashScope API 的嵌入模型"""

    def __init__(self, api_key: str, model: str = "text-embedding-v3"):
        dashscope.api_key = api_key
        self.model = model

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """批量嵌入文档，自动分批（DashScope 限制单次最多 10 条）"""
        if not texts:
            return []

        from dashscope import TextEmbedding

        all_embeddings = []
        for i in range(0, len(texts), BATCH_SIZE):
            batch = texts[i:i + BATCH_SIZE]
            result = TextEmbedding.call(
                model=self.model,
                input=batch,
            )
            if result.output and 'embeddings' in result.output:
                sorted_embs = sorted(result.output['embeddings'], key=lambda x: x['text_index'])
                all_embeddings.extend(item['embedding'] for item in sorted_embs)
            else:
                raise ValueError(f"DashScope embedding failed: {result}")

        return all_embeddings

    def embed_query(self, text: str) -> List[float]:
        """嵌入单条查询"""
        return self.embed_documents([text])[0]
