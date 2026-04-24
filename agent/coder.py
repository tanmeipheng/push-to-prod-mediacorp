"""
Coder Node — Generates the fixed code + test file using an LLM.
"""

import json
from agent.prompts import CODER_SYSTEM_PROMPT, CODER_USER_PROMPT
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage


def generate_fix(source_code: str, fault_type: str, action: str, summary: str) -> dict:
    """Generate resilient code + pytest test for the given fault."""
    llm = ChatAnthropic(
        model="claude-sonnet-4-6",
        temperature=0,
        max_tokens=4096,
    )

    messages = [
        SystemMessage(content=CODER_SYSTEM_PROMPT),
        HumanMessage(
            content=CODER_USER_PROMPT.format(
                fault_type=fault_type,
                action=action,
                summary=summary,
                source_code=source_code,
            )
        ),
    ]

    response = llm.invoke(messages)

    # Strip markdown fences if present
    text = response.content.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]  # remove opening fence line
        text = text.rsplit("```", 1)[0]  # remove closing fence

    result = json.loads(text)

    # LLMs sometimes double-escape newlines in JSON code strings.
    # If the code has no real newlines but has literal \n sequences, fix it.
    for key in ("fixed_code", "test_code"):
        val = result.get(key, "")
        if "\n" not in val and "\\n" in val:
            result[key] = val.replace("\\n", "\n").replace("\\t", "\t")

    return result
