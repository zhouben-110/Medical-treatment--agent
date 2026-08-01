"""Medical-KB MCP Server. Run: python -m medical_kb_mcp.server [stdio|http]."""

import sys
from typing import Annotated
from pydantic import Field
from mcp.server.fastmcp import FastMCP
from medical_kb_mcp.config import get_mcp_settings
from medical_kb_mcp.db import (
    search_diseases_by_symptoms, get_disease_detail, DiseaseMatch, DiseaseDetail,
)
from medical_kb_mcp.vectors import search_guidelines, GuidelineChunk

_settings = get_mcp_settings()
mcp = FastMCP(name="medical-kb", host=_settings.mcp_host, port=_settings.mcp_port)

_READONLY = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": False,
}


@mcp.tool(name="search_diseases_by_symptoms", annotations=_READONLY)
async def search_diseases_by_symptoms_tool(
    symptoms: Annotated[list[str], Field(description="症状关键词列表，如 ['发热','咳嗽','流涕']")],
    limit: Annotated[int, Field(description="返回的最大疾病数", ge=1, le=20)] = 5,
) -> list[DiseaseMatch]:
    """根据症状列表匹配可能的疾病，按 Dice 相似度排序返回。

    返回 DiseaseMatch 列表，每项含 name（疾病名）、matched_symptoms（命中的症状）、
    match_score（0-1 的匹配度）、severity（严重程度）、description（简述）。
    无匹配时返回空列表。
    """
    return await search_diseases_by_symptoms(symptoms, limit)


@mcp.tool(name="get_disease_detail", annotations=_READONLY)
async def get_disease_detail_tool(
    name: Annotated[str, Field(description="疾病名称，支持精确名或包含匹配，如 '普通感冒'")],
) -> DiseaseDetail | None:
    """按疾病名查找详情（描述、治疗、就医指征、严重程度、典型症状）。

    返回 DiseaseDetail（name/description/treatment/when_to_see_doctor/severity/symptoms），
    未找到时返回 null。
    """
    return await get_disease_detail(name)


@mcp.tool(name="search_guidelines", annotations=_READONLY)
async def search_guidelines_tool(
    query: Annotated[str, Field(description="自然语言检索词，如 '高血压 用药 注意事项'")],
    k: Annotated[int, Field(description="返回的片段数量", ge=1, le=10)] = 3,
) -> list[GuidelineChunk]:
    """在诊疗指南向量库中按语义检索相关片段。

    返回 GuidelineChunk 列表，每项含 text（指南片段）、score（cosine similarity，0~1 越大越相似）
    与 source（指南来源标题，便于溯源）。向量库不可用时返回空列表（优雅降级）。
    """
    return await search_guidelines(query, k)


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "stdio"
    if mode == "http":
        mcp.run(transport="streamable-http")
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
