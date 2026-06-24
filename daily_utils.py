"""Daily.co room creation for browser voice sessions."""

import os
import time

import aiohttp
from loguru import logger

DAILY_API_KEY = os.getenv("DAILY_API_KEY", "").strip()


async def create_daily_room() -> tuple[str, str]:
    """Create a Daily room and owner token for the voice bot."""
    if not DAILY_API_KEY:
        raise ValueError("DAILY_API_KEY is not set")

    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://api.daily.co/v1/rooms",
            headers={
                "Authorization": f"Bearer {DAILY_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "properties": {
                    "exp": int(time.time()) + 3600,
                    "enable_chat": False,
                    "enable_emoji_reactions": False,
                }
            },
        ) as response:
            if response.status != 200:
                error_text = await response.text()
                logger.error(f"Failed to create Daily room: {response.status} - {error_text}")
                raise RuntimeError(f"Failed to create Daily room: {response.status}")

            room_data = await response.json()
            room_url = room_data.get("url")
            room_name = room_data.get("name")
            if not room_url or not room_name:
                raise RuntimeError("Invalid room data from Daily API")

        async with session.post(
            "https://api.daily.co/v1/meeting-tokens",
            headers={
                "Authorization": f"Bearer {DAILY_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "properties": {
                    "room_name": room_name,
                    "is_owner": True,
                }
            },
        ) as response:
            if response.status != 200:
                error_text = await response.text()
                logger.error(f"Failed to create Daily token: {response.status} - {error_text}")
                raise RuntimeError(f"Failed to create Daily token: {response.status}")

            token_data = await response.json()
            token = token_data.get("token")
            if not token:
                raise RuntimeError("Invalid token data from Daily API")

    logger.info(f"Created Daily room: {room_url}")
    return room_url, token
