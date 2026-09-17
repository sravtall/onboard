"""Async top-level functions and an async method."""

import asyncio


async def fetch_data(url: str) -> str:
    """Simulate an async network fetch."""
    await asyncio.sleep(0)
    return f"data from {url}"


class Client:
    async def connect(self) -> None:
        await asyncio.sleep(0)
