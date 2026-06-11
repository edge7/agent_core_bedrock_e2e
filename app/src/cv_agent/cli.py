"""Terminal chat with the agent — quick way to test without the web UI."""

import asyncio

from cv_agent.agent import build_agent


async def _chat() -> None:
    agent = build_agent()
    history = []
    print("Chat with the CV agent (type 'exit' to quit)\n")
    while True:
        try:
            user = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not user or user.lower() in {"exit", "quit"}:
            break
        async with agent.run_stream(user, message_history=history) as result:
            async for delta in result.stream_text(delta=True):
                print(delta, end="", flush=True)
            print("\n")
            history = result.all_messages()


def main() -> None:
    asyncio.run(_chat())


if __name__ == "__main__":
    main()
