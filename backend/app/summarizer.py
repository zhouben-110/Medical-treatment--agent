"""对话摘要机制：当对话轮次过长时自动摘要早期消息"""

from langchain_core.prompts import ChatPromptTemplate
from app.llm import get_llm

SUMMARY_THRESHOLD = 12  # 超过此消息数时触发摘要
SUMMARY_KEEP_RECENT = 4  # 保留最近 N 条消息原文

SUMMARIZE_PROMPT = """请将以下医疗对话历史压缩为简洁的摘要，保留关键信息（症状、诊断结论、建议要点）。

对话历史:
{conversation}

要求:
- 用中文，200字以内
- 保留所有已识别的症状
- 保留诊断结论和关键建议
- 不要丢失重要的时间信息（如症状持续时间）"""


async def maybe_summarize_messages(messages: list[dict]) -> list[dict]:
    """如果消息数超过阈值，摘要早期消息。

    返回处理后的消息列表（可能不变）。
    """
    if len(messages) <= SUMMARY_THRESHOLD:
        return messages

    # 分离：需要摘要的旧消息 + 保留的近期消息
    to_summarize = messages[:-SUMMARY_KEEP_RECENT]
    recent = messages[-SUMMARY_KEEP_RECENT:]

    # 构建对话文本
    lines = []
    for m in to_summarize:
        role = m.get("role", "unknown")
        content = m.get("content", "")
        label = "用户" if role == "user" else "助手"
        lines.append(f"{label}: {content}")
    conversation = "\n".join(lines)

    # 调用 LLM 生成摘要
    try:
        llm = get_llm(temperature=0)
        prompt = ChatPromptTemplate.from_template(SUMMARIZE_PROMPT)
        chain = prompt | llm
        response = await chain.ainvoke({"conversation": conversation})
        summary_text = response.content
    except Exception as e:
        print(f"[Summarizer] failed: {e}")
        return messages  # 摘要失败则返回原消息

    # 用摘要替换旧消息
    summary_msg = {"role": "system", "content": f"[对话摘要] {summary_text}"}
    return [summary_msg] + recent
