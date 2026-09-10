"""Rate-conscious clients for public Polymarket APIs."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Mapping
from urllib.parse import urlencode

import httpx

from polymarket_forecast.config import ApiConfig

RETRYABLE_STATUS = {408, 425, 429, 500, 502, 503, 504}


@dataclass(frozen=True)
class SourceResponse:
    url: str
    parameters: Mapping[str, Any]
    status_code: int
    retrieved_at: datetime
    body: bytes

    def json(self) -> Any:
        return json.loads(self.body)

    @property
    def request_url(self) -> str:
        if not self.parameters:
            return self.url
        return f"{self.url}?{urlencode(self.parameters)}"


class PolymarketClient:
    """Minimal public-read client with bounded retries and concurrency."""

    def __init__(self, config: ApiConfig) -> None:
        self.config = config
        self._headers = {
            "Accept": "application/json",
            "User-Agent": config.user_agent,
        }

    async def _request(
        self,
        client: httpx.AsyncClient,
        url: str,
        params: Mapping[str, Any] | None = None,
        *,
        allow_not_found: bool = False,
    ) -> SourceResponse:
        parameters = dict(params or {})
        last_error: Exception | None = None
        for attempt in range(self.config.max_retries + 1):
            try:
                response = await client.get(url, params=parameters, headers=self._headers)
                retrieved_at = datetime.now(UTC)
                if allow_not_found and response.status_code == 404:
                    return SourceResponse(
                        url=url,
                        parameters=parameters,
                        status_code=response.status_code,
                        retrieved_at=retrieved_at,
                        body=response.content,
                    )
                if response.status_code not in RETRYABLE_STATUS:
                    response.raise_for_status()
                    return SourceResponse(
                        url=url,
                        parameters=parameters,
                        status_code=response.status_code,
                        retrieved_at=retrieved_at,
                        body=response.content,
                    )
                last_error = httpx.HTTPStatusError(
                    f"Retryable HTTP status {response.status_code}",
                    request=response.request,
                    response=response,
                )
            except (httpx.TransportError, httpx.TimeoutException) as exc:
                last_error = exc
            if attempt < self.config.max_retries:
                await asyncio.sleep(min(2**attempt, 8))
        raise RuntimeError(f"Request failed after retries: {url}") from last_error

    async def list_closed_markets(
        self,
        *,
        end_date_min: datetime,
        end_date_max: datetime,
    ) -> list[SourceResponse]:
        """Page over recently closed Gamma markets in deterministic order."""
        responses: list[SourceResponse] = []
        offset = 0
        timeout = httpx.Timeout(self.config.request_timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            while offset < self.config.max_markets:
                limit = min(self.config.page_size, self.config.max_markets - offset)
                params = {
                    "closed": "true",
                    "uma_resolution_status": "resolved",
                    "end_date_min": end_date_min.isoformat(),
                    "end_date_max": end_date_max.isoformat(),
                    "limit": limit,
                    "offset": offset,
                    "order": "endDate",
                    "ascending": "false",
                }
                response = await self._request(
                    client,
                    f"{self.config.gamma_base_url}/markets",
                    params,
                )
                payload = response.json()
                if not isinstance(payload, list):
                    raise TypeError("Gamma /markets response must be a JSON array")
                responses.append(response)
                if len(payload) < limit:
                    break
                offset += len(payload)
        return responses

    async def get_clob_markets(
        self,
        condition_ids: list[str],
    ) -> dict[str, SourceResponse]:
        semaphore = asyncio.Semaphore(self.config.concurrency)
        timeout = httpx.Timeout(self.config.request_timeout_seconds)
        results: dict[str, SourceResponse] = {}

        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:

            async def fetch(condition_id: str) -> None:
                async with semaphore:
                    response = await self._request(
                        client,
                        f"{self.config.clob_base_url}/markets/{condition_id}",
                        allow_not_found=True,
                    )
                    results[condition_id] = response

            await asyncio.gather(*(fetch(condition_id) for condition_id in condition_ids))
        return results

    async def get_price_histories(
        self,
        requests: Mapping[str, tuple[str, int, int]],
    ) -> dict[str, SourceResponse]:
        """Retrieve bounded price histories.

        Args:
            requests: Mapping from market ID to ``(token_id, start_ts, end_ts)``.
        """
        semaphore = asyncio.Semaphore(self.config.concurrency)
        timeout = httpx.Timeout(self.config.request_timeout_seconds)
        results: dict[str, SourceResponse] = {}

        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:

            async def fetch(
                market_id: str,
                token_id: str,
                start_ts: int,
                end_ts: int,
            ) -> None:
                params = {
                    "market": token_id,
                    "startTs": start_ts,
                    "endTs": end_ts,
                    "fidelity": self.config.price_fidelity_minutes,
                }
                async with semaphore:
                    results[market_id] = await self._request(
                        client,
                        f"{self.config.clob_base_url}/prices-history",
                        params,
                    )

            await asyncio.gather(
                *(
                    fetch(market_id, token_id, start_ts, end_ts)
                    for market_id, (token_id, start_ts, end_ts) in requests.items()
                )
            )
        return results
