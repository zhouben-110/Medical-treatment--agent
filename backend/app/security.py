"""安全与防护模块：Prompt 注入防护、敏感词过滤"""

import re
import logging
from fastapi import HTTPException, status

logger = logging.getLogger(__name__)

# 常见 Prompt 注入和越狱攻击关键词（支持正则）
PROMPT_INJECTION_PATTERNS = [
    r"忽略(之前|上述|所有)?(的)?(指令|设定|规则|提示|对话)",
    r"ignore (previous|above|all)?( )?(instructions|rules|prompts|conversation)",
    r"你(现在|将)?扮演",
    r"you are now",
    r"act as",
    r"开发者模式",
    r"developer mode",
    r"系统提示词",
    r"system prompt",
    r"绕过(安全)?限制",
    r"bypass (security)? restriction",
    r"jailbreak",
    r"越狱",
]

# 编译为不区分大小写的正则表达式对象
_compiled_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in PROMPT_INJECTION_PATTERNS]


def check_prompt_injection(message: str) -> None:
    """检查输入是否包含 Prompt 注入/越狱攻击痕迹。
    如果检测到注入尝试，直接抛出 HTTPException 拒绝处理。
    """
    if not message:
        return

    for pattern in _compiled_patterns:
        if pattern.search(message):
            logger.warning("检测到潜在的 Prompt 注入攻击，输入内容为: %s", message[:100])
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="您的输入包含不合规指令或非正常症状描述，请重新输入真实的症状描述。"
            )
