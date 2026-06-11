"""FastAPI server: streaming chat over SSE.

Sessions are kept in process memory — fine for a local dev harness.
"""

import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from pydantic_ai.messages import ModelMessage

from cv_agent.agent import build_agent

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="CV Agent")
agent = build_agent()
sessions: dict[str, list[ModelMessage]] = {}


class ChatRequest(BaseModel):
    session_id: str
    message: str


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/api/chat")
async def chat(req: ChatRequest) -> StreamingResponse:
    history = sessions.get(req.session_id, [])

    async def event_stream():
        try:
            async with agent.run_stream(req.message, message_history=history) as result:
                async for delta in result.stream_text(delta=True):
                    yield f"data: {json.dumps({'text': delta})}\n\n"
                sessions[req.session_id] = result.all_messages()
        except Exception as exc:  # surface errors in the chat instead of a dead stream
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def main() -> None:
    import uvicorn

    from cv_agent.settings import settings

    uvicorn.run(app, host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
