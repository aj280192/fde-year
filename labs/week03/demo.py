"""Stream an answer to the terminal: python demo.py BASE_URL MODEL "prompt"."""

import asyncio
import sys

from client import LLMClient


async def main(base_url: str, model: str, prompt: str) -> None:
    async with LLMClient(base_url, model=model) as client:
        async for piece in client.stream(prompt):
            print(piece, end="", flush=True)
    print()


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1], sys.argv[2], sys.argv[3]))
