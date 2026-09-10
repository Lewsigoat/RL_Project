from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd


def synthetic_source_frames(
    *,
    event_count: int = 60,
    contracts_per_event: int = 1,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    markets: list[dict[str, object]] = []
    prices: list[dict[str, object]] = []
    first_event = datetime(2024, 3, 1, 12, tzinfo=UTC)
    offsets_days = [38, 31, 30, 29, 14, 8, 7, 6, 2, 1, 0.5]

    for event_index in range(event_count):
        event_time = first_event + timedelta(days=14 * event_index)
        for contract_index in range(contracts_per_event):
            market_id = f"market-{event_index:03d}-{contract_index}"
            label = int((event_index + contract_index) % 3 == 0)
            category = ["politics", "crypto", "sports"][event_index % 3]
            markets.append(
                {
                    "market_id": market_id,
                    "event_id": f"event-{event_index:03d}",
                    "condition_id": f"condition-{market_id}",
                    "question_id": f"question-{market_id}",
                    "slug": market_id,
                    "question": f"Will synthetic event {event_index} happen?",
                    "description": f"Resolved from the official {category} source.",
                    "category": category,
                    "yes_token_id": f"yes-{market_id}",
                    "no_token_id": f"no-{market_id}",
                    "created_at": event_time - timedelta(days=90),
                    "event_time": event_time,
                    "end_date": event_time,
                    "closed_time": event_time + timedelta(days=1),
                    "source_updated_at": event_time + timedelta(days=1),
                    "label": label,
                    "label_source": "clob_winner_crosschecked_gamma",
                    "neg_risk": event_index % 4 == 0,
                    "final_volume": 1000.0,
                    "final_liquidity": 100.0,
                    "raw_sha256": "0" * 64,
                }
            )
            anchor = 0.62 if label else 0.38
            for point_index, offset in enumerate(offsets_days):
                wave = 0.035 * np.sin(event_index + point_index)
                price = float(np.clip(anchor + wave, 0.02, 0.98))
                prices.append(
                    {
                        "market_id": market_id,
                        "token_id": f"yes-{market_id}",
                        "timestamp": event_time - timedelta(days=offset) - timedelta(minutes=30),
                        "price": price,
                        "source": "synthetic_test",
                    }
                )
    return pd.DataFrame(markets), pd.DataFrame(prices)
