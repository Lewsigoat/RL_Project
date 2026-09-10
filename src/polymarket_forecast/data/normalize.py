"""Normalize mutable API payloads into explicit research records."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any, Mapping, Sequence

from polymarket_forecast.data.schemas import Exclusion, MarketRecord, PricePoint


def _json_array(value: Any, field: str) -> list[Any]:
    if isinstance(value, str):
        value = json.loads(value)
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a JSON array")
    return value


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _parse_time(value: Any, field: str, *, required: bool = True) -> datetime | None:
    if value in {None, ""}:
        if required:
            raise ValueError(f"Missing timestamp {field}")
        return None
    normalized = str(value).strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _float_or_none(value: Any) -> float | None:
    if value in {None, ""}:
        return None
    parsed = float(value)
    return parsed if parsed == parsed else None


def _first_event(raw: Mapping[str, Any]) -> Mapping[str, Any]:
    events = raw.get("events")
    if isinstance(events, list) and events and isinstance(events[0], dict):
        return {str(key): value for key, value in events[0].items()}
    return {}


def _event_time(raw: Mapping[str, Any], event: Mapping[str, Any]) -> datetime:
    candidates = (
        raw.get("gameStartTime"),
        event.get("startTime"),
        event.get("eventDate"),
        raw.get("endDate"),
    )
    for value in candidates:
        if value not in {None, ""}:
            text = str(value)
            if len(text) == 10:
                text = f"{text}T00:00:00Z"
            parsed = _parse_time(text, "event_time")
            if parsed is not None:
                return parsed
    raise ValueError("No usable event time")


def _category(raw: Mapping[str, Any], event: Mapping[str, Any], clob: Mapping[str, Any]) -> str:
    tags = clob.get("tags")
    if isinstance(tags, list):
        clean = [_text(item) for item in tags if _text(item)]
        if clean:
            return clean[0].lower()

    for container in (raw, event):
        values = container.get("tags")
        if not isinstance(values, list):
            continue
        for item in values:
            if isinstance(item, dict):
                label = _text(item.get("label") or item.get("name"))
            else:
                label = _text(item)
            if label:
                return label.lower()
    return "unknown"


def _label_from_gamma(outcomes: Sequence[str], raw_prices: Any) -> int | None:
    try:
        prices = [float(value) for value in _json_array(raw_prices, "outcomePrices")]
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    if len(prices) != len(outcomes):
        return None
    winners = [index for index, price in enumerate(prices) if price >= 0.99]
    losers = [index for index, price in enumerate(prices) if price <= 0.01]
    if len(winners) != 1 or len(losers) < 1:
        return None
    return int(outcomes[winners[0]].casefold() == "yes")


def _label_from_clob(clob: Mapping[str, Any]) -> int | None:
    if bool(clob.get("is_50_50_outcome")):
        raise ValueError("CLOB marks market as a 50/50 outcome")
    tokens = clob.get("tokens")
    if not isinstance(tokens, list):
        return None
    winners = [token for token in tokens if isinstance(token, dict) and token.get("winner") is True]
    if len(winners) != 1:
        return None
    outcome = _text(winners[0].get("outcome")).casefold()
    if outcome not in {"yes", "no"}:
        return None
    return int(outcome == "yes")


def normalize_market(
    raw: Mapping[str, Any],
    clob_market: Mapping[str, Any] | None = None,
) -> tuple[MarketRecord | None, Exclusion | None]:
    """Validate and normalize one Gamma market and an optional CLOB cross-check."""
    market_id = _text(raw.get("id")) or "unknown"
    clob = clob_market or {}
    try:
        if _text(raw.get("umaResolutionStatus")).casefold() != "resolved":
            raise ValueError("UMA resolution status is not resolved")

        outcomes = [_text(item) for item in _json_array(raw.get("outcomes"), "outcomes")]
        token_ids = [_text(item) for item in _json_array(raw.get("clobTokenIds"), "clobTokenIds")]
        if len(outcomes) != 2 or len(token_ids) != 2:
            raise ValueError("Market is not binary")
        normalized_outcomes = [item.casefold() for item in outcomes]
        if set(normalized_outcomes) != {"yes", "no"}:
            raise ValueError(f"Unsupported outcomes: {outcomes!r}")
        yes_index = normalized_outcomes.index("yes")
        no_index = normalized_outcomes.index("no")

        gamma_label = _label_from_gamma(outcomes, raw.get("outcomePrices"))
        clob_label = _label_from_clob(clob)
        if gamma_label is not None and clob_label is not None and gamma_label != clob_label:
            raise ValueError("Gamma terminal price conflicts with CLOB winner")
        if clob_label is not None:
            label = clob_label
            label_source = "clob_winner_crosschecked_gamma"
        elif gamma_label is not None:
            label = gamma_label
            label_source = "gamma_terminal_price"
        else:
            raise ValueError("No unambiguous binary winner")

        event = _first_event(raw)
        event_id = _text(event.get("id")) or _text(raw.get("eventId"))
        condition_id = _text(raw.get("conditionId"))
        if not condition_id:
            raise ValueError("Missing conditionId")
        if not event_id:
            event_id = condition_id

        created_at = _parse_time(raw.get("createdAt"), "createdAt")
        end_date = _parse_time(raw.get("endDate"), "endDate")
        closed_time = _parse_time(
            raw.get("closedTime") or raw.get("umaEndDate"),
            "closedTime",
        )
        if created_at is None or end_date is None or closed_time is None:
            raise ValueError("Required timestamp unexpectedly parsed as None")
        event_time = _event_time(raw, event)
        updated_at = _parse_time(raw.get("updatedAt"), "updatedAt", required=False)

        canonical_raw = json.dumps(
            raw,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        record = MarketRecord(
            market_id=market_id,
            event_id=event_id,
            condition_id=condition_id,
            question_id=_text(raw.get("questionID")),
            slug=_text(raw.get("slug")),
            question=_text(raw.get("question")),
            description=_text(raw.get("description")),
            category=_category(raw, event, clob),
            yes_token_id=token_ids[yes_index],
            no_token_id=token_ids[no_index],
            created_at=created_at,
            event_time=event_time,
            end_date=end_date,
            closed_time=closed_time,
            source_updated_at=updated_at,
            label=label,
            label_source=label_source,
            neg_risk=bool(raw.get("negRisk")),
            final_volume=_float_or_none(raw.get("volumeNum") or raw.get("volume")),
            final_liquidity=_float_or_none(raw.get("liquidityNum") or raw.get("liquidity")),
            raw_sha256=hashlib.sha256(canonical_raw).hexdigest(),
        )
        return record, None
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        return None, Exclusion(market_id=market_id, reason="normalization_failed", detail=str(exc))


def normalize_price_history(
    market_id: str,
    token_id: str,
    payload: Mapping[str, Any],
) -> tuple[list[PricePoint], list[Exclusion]]:
    history = payload.get("history")
    if not isinstance(history, list):
        return [], [
            Exclusion(
                market_id=market_id,
                reason="invalid_price_history",
                detail="history is not an array",
            )
        ]
    points: list[PricePoint] = []
    exclusions: list[Exclusion] = []
    seen: set[int] = set()
    for item in history:
        try:
            if not isinstance(item, dict):
                raise ValueError("history item is not an object")
            timestamp_seconds = int(item["t"])
            if timestamp_seconds in seen:
                continue
            seen.add(timestamp_seconds)
            points.append(
                PricePoint(
                    market_id=market_id,
                    token_id=token_id,
                    timestamp=datetime.fromtimestamp(timestamp_seconds, tz=UTC),
                    price=float(item["p"]),
                )
            )
        except (KeyError, TypeError, ValueError) as exc:
            exclusions.append(
                Exclusion(
                    market_id=market_id,
                    reason="invalid_price_point",
                    detail=str(exc),
                )
            )
    points.sort(key=lambda point: point.timestamp)
    return points, exclusions
