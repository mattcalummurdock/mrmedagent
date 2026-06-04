"""Exotel Connect API client for outbound dial-out."""

from __future__ import annotations

import asyncio
import json
import os
from typing import Optional

import aiohttp
from dotenv import load_dotenv
from loguru import logger

load_dotenv(override=True)

DEFAULT_CONNECT_BASE = "https://api.exotel.com"


class ExotelService:
    """Singleton Exotel service with managed aiohttp session."""

    _instance: Optional["ExotelService"] = None
    _lock = asyncio.Lock()

    def __init__(self) -> None:
        self._session: aiohttp.ClientSession | None = None
        self._api_key = os.getenv("EXOTEL_API_KEY", "").strip()
        self._api_token = os.getenv("EXOTEL_API_TOKEN", "").strip()
        self._account_sid = (
            os.getenv("EXOTEL_SID", "").strip()
            or os.getenv("EXOTEL_ACCOUNT_SID", "").strip()
        )
        self._app_id = os.getenv("EXOTEL_APP_ID", "").strip()
        self._from_number = os.getenv("EXOTEL_PHONE_NUMBER", "").strip()
        self._base_url = os.getenv(
            "EXOTEL_CONNECT_API_BASE_URL", DEFAULT_CONNECT_BASE
        ).strip()

    @classmethod
    async def get_instance(cls) -> "ExotelService":
        if cls._instance is None:
            async with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
                    await cls._instance._init_session()
        return cls._instance

    async def _init_session(self) -> None:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30),
                connector=aiohttp.TCPConnector(limit=20, limit_per_host=10),
            )
            logger.info("Exotel service session initialized")

    async def _ensure_session(self) -> None:
        if self._session is None or self._session.closed:
            await self._init_session()

    def _validate_credentials(self) -> bool:
        if not all([self._api_key, self._api_token, self._account_sid]):
            logger.error(
                "Missing Exotel credentials: EXOTEL_API_KEY, EXOTEL_API_TOKEN, EXOTEL_SID"
            )
            return False
        return True

    async def call(
        self,
        to_number: str,
        from_number: str | None = None,
        custom_field: dict | str | None = None,
    ) -> dict:
        """Initiate outbound call via Exotel Connect API."""
        if not self._validate_credentials():
            raise ValueError("Missing Exotel credentials")
        if not self._app_id:
            raise ValueError(
                "Missing EXOTEL_APP_ID — required for voice applet / ExoML flow"
            )

        caller_id = from_number or self._from_number
        if not caller_id:
            raise ValueError(
                "No from_number provided and EXOTEL_PHONE_NUMBER not set"
            )

        await self._ensure_session()

        url = f"{self._base_url}/v1/Accounts/{self._account_sid}/Calls/connect"
        data = {
            "From": to_number,
            "CallerId": caller_id,
            "Url": f"http://my.exotel.com/{self._account_sid}/exoml/start_voice/{self._app_id}",
            "CallType": "trans",
        }
        if custom_field is not None:
            data["CustomField"] = (
                json.dumps(custom_field)
                if isinstance(custom_field, dict)
                else custom_field
            )

        auth = aiohttp.BasicAuth(self._api_key, self._api_token)
        assert self._session is not None
        async with self._session.post(url, data=data, auth=auth) as response:
            if response.status != 200:
                error_text = await response.text()
                raise RuntimeError(
                    f"Exotel API error ({response.status}): {error_text}"
                )
            result_text = await response.text()

        call_sid = "unknown"
        if "<Sid>" in result_text:
            start = result_text.find("<Sid>") + 5
            end = result_text.find("</Sid>")
            if end > start:
                call_sid = result_text[start:end]

        logger.info(f"Exotel call initiated: SID={call_sid}, to={to_number}")
        return {"status": "call_initiated", "call_sid": call_sid}

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
            logger.info("Exotel service session closed")

    @classmethod
    async def shutdown(cls) -> None:
        if cls._instance:
            await cls._instance.close()
            cls._instance = None
