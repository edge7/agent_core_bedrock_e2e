"""AgentCore Runtime entrypoint.

Wraps the PydanticAI agent with the AgentCore runtime contract
(POST /invocations + GET /ping on port 8080). This is the only
AgentCore-aware module — agent.py stays platform-agnostic.
"""

import logging

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from pydantic_ai import Agent, AgentRunResultEvent
from pydantic_ai.messages import (
    ModelMessage,
    PartDeltaEvent,
    PartStartEvent,
    TextPart,
    TextPartDelta,
)

from cv_agent.agent import build_agent

logging.basicConfig(
    level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
)

app = BedrockAgentCoreApp()

# Built lazily on the first invocation: runtime initialization has a strict
# 30s budget, and building the agent pulls the CV from Secrets Manager —
# better to spend that time inside the first request than during init.
_agent: Agent | None = None


def get_or_create_agent() -> Agent:
    global _agent
    if _agent is None:
        _agent = build_agent()
    return _agent


# Conversation history lives in process memory. Each AgentCore session runs in
# its own isolated microVM whose process persists between invocations until
# the session times out, so this survives across turns within a session — but
# not beyond. AgentCore Memory is the durable replacement.
histories: dict[str, list[ModelMessage]] = {}


@app.entrypoint
async def invoke(payload, context):
    prompt = payload.get("prompt", "")
    if not prompt:
        yield "Please send a JSON payload like {\"prompt\": \"your question\"}."
        return

    agent = get_or_create_agent()
    session_id = context.session_id or "local-dev"
    history = histories.get(session_id, [])

    # run_stream_events runs the full agent graph (run_stream would stop at
    # the first text output and skip tool calls the model emits after it),
    # while still streaming text deltas as they are produced.
    emitted = False
    async with agent.run_stream_events(prompt, message_history=history) as stream:
        async for event in stream:
            if isinstance(event, PartStartEvent) and isinstance(event.part, TextPart):
                if emitted:
                    yield "\n\n"  # separate text written before/after a tool call
                if event.part.content:
                    emitted = True
                    yield event.part.content
            elif isinstance(event, PartDeltaEvent) and isinstance(event.delta, TextPartDelta):
                if event.delta.content_delta:
                    emitted = True
                    yield event.delta.content_delta
            elif isinstance(event, AgentRunResultEvent):
                histories[session_id] = event.result.all_messages()


if __name__ == "__main__":
    app.run()
