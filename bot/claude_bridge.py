"""Bridge between Python Telegram bot and Claude Code CLI."""

import asyncio
import logging
import subprocess

from config import (
    CLAUDE_PATH, CLAUDE_DEFAULT_MODEL, CLAUDE_AGENT_MODELS,
    CLAUDE_MAX_CONCURRENT, CLAUDE_SUBPROCESS_TIMEOUT,
)

logger = logging.getLogger(__name__)

# Semaphore to limit concurrent Claude Code invocations
_semaphore = asyncio.Semaphore(CLAUDE_MAX_CONCURRENT)


def call_claude(prompt: str, model: str = CLAUDE_DEFAULT_MODEL,
                allowed_tools: str = "mcp__fin-invest__*,WebSearch,WebFetch",
                agent: str = "") -> str:
    """
    Call Claude Code CLI as a subprocess.
    Returns the text output.
    """
    # Override model for specific agents
    if agent and agent in CLAUDE_AGENT_MODELS:
        model = CLAUDE_AGENT_MODELS[agent]

    cmd = [CLAUDE_PATH, "-p", prompt, "--model", model,
           "--allowedTools", allowed_tools]
    if agent:
        cmd += ["--agent", agent]

    logger.info("Claude call: model=%s, agent=%s, prompt_len=%d",
                model, agent or "none", len(prompt))

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=CLAUDE_SUBPROCESS_TIMEOUT,
            cwd="/home/bravopotato/Spaces/finspace/invest",
        )

        if result.returncode != 0:
            logger.error("Claude returned code %d: %s",
                         result.returncode, result.stderr[:500])
            return f"분석 중 오류가 발생했습니다. (code: {result.returncode})"

        output = result.stdout.strip()
        logger.info("Claude response: %d chars", len(output))
        return output

    except subprocess.TimeoutExpired:
        logger.error("Claude subprocess timed out after %ds",
                     CLAUDE_SUBPROCESS_TIMEOUT)
        return "분석 시간이 초과되었습니다. 다시 시도해주세요."
    except FileNotFoundError:
        logger.error("Claude CLI not found at: %s", CLAUDE_PATH)
        return "Claude Code가 설치되어 있지 않습니다."
    except Exception as e:
        logger.error("Claude subprocess error: %s", e)
        return f"오류: {e}"


async def call_claude_async(prompt: str, **kwargs) -> str:
    """Async wrapper with concurrency limit."""
    async with _semaphore:
        return await asyncio.to_thread(call_claude, prompt, **kwargs)
