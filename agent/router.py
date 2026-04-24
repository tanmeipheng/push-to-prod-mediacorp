"""
Router Node — Classifies a crash log into a fault category using an LLM.
"""

import json
from agent.prompts import ROUTER_SYSTEM_PROMPT, ROUTER_USER_PROMPT
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage


def classify_fault(crash_log: str) -> dict:
    """Send the crash log to Claude and return structured classification."""
    llm = ChatAnthropic(
        model="claude-sonnet-4-6",
        temperature=0,
        max_tokens=1024,
    )

    messages = [
        SystemMessage(content=ROUTER_SYSTEM_PROMPT),
        HumanMessage(content=ROUTER_USER_PROMPT.format(crash_log=crash_log)),
    ]

    response = llm.invoke(messages)
    result = json.loads(response.content)
    return result
