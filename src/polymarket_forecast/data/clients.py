"""Rate-conscious clients for public Polymarket APIs."""

from __future__ import annotations

import asyncio
import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

import httpx

from polymarket_forecast.config import ApiConfig

RETRYABLE_STATUS = {408, 425, 429, 500, 502, 503, 504}


def _next_month(value: datetime) -> datetime:
    if value.month == 12:
        return value.replace(year=value.year + 1, month=1, day=1)
    return value.replace(month=value.month + 1, day=1)


def _month_strata(start: datetime, end: datetime) -> list[tuple[datetime, datetime]]:
    cursor = start.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    strata: list[tuple[datetime, datetime]] = []
    while cursor <= end:
        following = _next_month(cursor)
        strata.append((max(start, cursor), min(end, following - timedelta(microseconds=1))))
        cursor = following
    return strata


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
        accepted_error_statuses: frozenset[int] = frozenset(),
    ) -> SourceResponse:
        parameters = dict(params or {})
        last_error: Exception | None = None
        for attempt in range(self.config.max_retries + 1):
            try:
                response = await client.get(url, params=parameters, headers=self._headers)
                retrieved_at = datetime.now(UTC)
                if response.status_code in accepted_error_statuses:
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
        """Collect deterministic keyset pages, optionally stratified by month."""
        responses: list[SourceResponse] = []
        strata = (
            _month_strata(end_date_min, end_date_max)
            if self.config.monthly_stratified_sampling
            else [(end_date_min, end_date_max)]
        )
        maximum = self.config.max_markets
        per_stratum = math.ceil(maximum / len(strata)) if maximum is not None else None
        total_rows = 0
        timeout = httpx.Timeout(self.config.request_timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            for stratum_start, stratum_end in strata:
                stratum_rows = 0
                after_cursor: str | None = None
                while per_stratum is None or stratum_rows < per_stratum:
                    if maximum is not None and total_rows >= maximum:
                        break
                    remaining_stratum = (
                        self.config.page_size if per_stratum is None else per_stratum - stratum_rows
                    )
                    remaining_total = (
                        self.config.page_size if maximum is None else maximum - total_rows
                    )
                    limit = min(
                        self.config.page_size,
                        remaining_stratum,
                        remaining_total,
                    )
                    params: dict[str, Any] = {
                        "closed": "true",
                        "uma_resolution_status": "resolved",
                        "end_date_min": stratum_start.isoformat(),
                        "end_date_max": stratum_end.isoformat(),
                        "limit": limit,
                        "order": self.config.sampling_order,
                        "ascending": "false",
                    }
                    if after_cursor:
                        params["after_cursor"] = after_cursor
                    response = await self._request(
                        client,
                        f"{self.config.gamma_base_url}/markets/keyset",
                        params,
                    )
                    payload = response.json()
                    if not isinstance(payload, dict) or not isinstance(
                        payload.get("markets"), list
                    ):
                        raise TypeError("Gamma /markets/keyset response must contain markets")
                    markets = payload["markets"]
                    responses.append(response)
                    stratum_rows += len(markets)
                    total_rows += len(markets)
                    after_cursor_value = payload.get("next_cursor")
                    after_cursor = str(after_cursor_value) if after_cursor_value else None
                    if len(markets) < limit or not after_cursor:
                        break
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
                        accepted_error_statuses=frozenset({404}),
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
                del start_ts, end_ts
                params = {
                    "market": token_id,
                    "interval": "max",
                    "fidelity": self.config.price_fidelity_minutes,
                }
                async with semaphore:
                    results[market_id] = await self._request(
                        client,
                        f"{self.config.clob_base_url}/prices-history",
                        params,
                        accepted_error_statuses=frozenset({400, 404}),
                    )

            await asyncio.gather(
                *(
                    fetch(market_id, token_id, start_ts, end_ts)
                    for market_id, (token_id, start_ts, end_ts) in requests.items()
                )
            )
        return results
