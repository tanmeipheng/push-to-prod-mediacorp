"""
Router Node — Classifies a crash log into a fault category using an LLM.
"""

import json
import re
from agent.prompts import ROUTER_SYSTEM_PROMPT, ROUTER_USER_PROMPT
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage


def _parse_llm_json(text: str) -> dict:
    """Parse JSON from LLM output, handling markdown fences and control chars."""
    text = text.strip()
    # Strip markdown fences
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        text = text.rsplit("```", 1)[0]
        text = text.strip()
    try:
        return json.loads(text, strict=False)
    except json.JSONDecodeError:
        # Fallback: extract JSON object by finding outermost braces
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            return json.loads(match.group(), strict=False)
        raise


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

    # Retry up to 2 times on JSON parse failures
    last_err = None
    for attempt in range(3):
        response = llm.invoke(messages)
        try:
            result = _parse_llm_json(response.content)
            return result
        except (json.JSONDecodeError, ValueError) as e:
            last_err = e
            if attempt < 2:
                continue
            raise last_err
