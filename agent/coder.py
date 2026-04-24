"""
Coder Node — Generates the fixed code + test file using an LLM.
"""

import json
import re
from agent.prompts import CODER_SYSTEM_PROMPT, CODER_USER_PROMPT
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

    # Retry up to 2 times on JSON parse failures
    last_err = None
    for attempt in range(3):
        response = llm.invoke(messages)
        try:
            result = _parse_llm_json(response.content)
            break
        except (json.JSONDecodeError, ValueError) as e:
            last_err = e
            if attempt < 2:
                continue
            raise last_err

    # LLMs sometimes double-escape newlines in JSON code strings.
    # If the code has no real newlines but has literal \n sequences, fix it.
    for key in ("fixed_code", "test_code"):
        val = result.get(key, "")
        if "\n" not in val and "\\n" in val:
            result[key] = val.replace("\\n", "\n").replace("\\t", "\t")

    return result
