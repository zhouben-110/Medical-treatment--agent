"""Direct knowledge base service.

Wraps medical_kb_mcp functions for in-process calls, bypassing the MCP transport
(stdio/HTTP) entirely.  The MCP server (medical_kb_mcp.server) is kept for
external integrations such as Claude Desktop.
"""

from medical_kb_mcp.db import (
    search_diseases_by_symptoms,
    get_disease_detail,
    DiseaseMatch,
    DiseaseDetail,
)
from medical_kb_mcp.vectors import (
    search_guidelines,
    GuidelineChunk,
)

__all__ = [
    "search_diseases_by_symptoms",
    "get_disease_detail",
    "search_guidelines",
    "DiseaseMatch",
    "DiseaseDetail",
    "GuidelineChunk",
]
