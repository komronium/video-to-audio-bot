"""Limited-time promo store.

A promo is a JSON blob in Redis under key `promo:active`, with TTL set to
its remaining lifetime. When it expires, the key disappears — no GC needed.

Promo schema:
    {
      "type": "2x_diamonds" | "monthly_discount" | "lifetime_discount",
      "value": 30,              # percent (discounts) or multiplier (bonuses)
      "expires_at": "2026-06-22T18:00:00",
      "label": "🔥 30% off Lifetime — 24h only",
      "created_by": <admin_id>
    }

Callers:
- diamonds menu: get_active_promo() → render banner
- successful_payment: get_active_promo() → adjust diamonds/expiry granted
- admin /promo: set_promo() / clear_promo()
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from redis.exceptions import RedisError

from services.redis_client import redis_client

PROMO_KEY = "promo:active"

PROMO_TYPES = {
    "2x_diamonds",         # Diamond packs grant N * value
    "monthly_discount",    # Monthly premium price *= (100 - value) / 100
    "lifetime_discount",   # Lifetime price *= (100 - value) / 100
}


@dataclass
class Promo:
    type: str
    value: int
    expires_at: datetime
    label: str
    created_by: int | None = None

    def seconds_left(self) -> int:
        return max(int((self.expires_at - datetime.now()).total_seconds()), 0)

    def to_json(self) -> str:
        return json.dumps(
            {
                "type": self.type,
                "value": self.value,
                "expires_at": self.expires_at.isoformat(),
                "label": self.label,
                "created_by": self.created_by,
            }
        )

    @classmethod
    def from_json(cls, raw: str) -> "Promo | None":
        try:
            data = json.loads(raw)
            return cls(
                type=data["type"],
                value=int(data["value"]),
                expires_at=datetime.fromisoformat(data["expires_at"]),
                label=data["label"],
                created_by=data.get("created_by"),
            )
        except (json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
            logging.warning(f"Bad promo blob in Redis: {e}")
            return None


async def get_active_promo() -> Promo | None:
    try:
        raw = await redis_client.get(PROMO_KEY)
    except RedisError:
        return None
    if not raw:
        return None
    promo = Promo.from_json(raw)
    if promo and promo.seconds_left() <= 0:
        return None
    return promo


async def set_promo(promo: Promo) -> bool:
    ttl = promo.seconds_left()
    if ttl <= 0:
        return False
    try:
        await redis_client.set(PROMO_KEY, promo.to_json(), ex=ttl)
        return True
    except RedisError:
        return False


async def clear_promo() -> None:
    try:
        await redis_client.delete(PROMO_KEY)
    except RedisError:
        pass


def apply_diamond_bonus(diamonds: int, promo: Promo | None) -> tuple[int, int]:
    """Return (final_diamonds, bonus_diamonds). Bonus is the extra on top
    of the purchased amount when a 2x promo is active."""
    if promo and promo.type == "2x_diamonds":
        bonus = diamonds * (promo.value - 1)
        return diamonds + bonus, bonus
    return diamonds, 0


def apply_price_discount(price: int, promo: Promo | None, kind: str) -> tuple[int, int]:
    """Return (final_price, original_price) — original equals final when no
    promo applies. `kind` is 'monthly' or 'lifetime' to match promo.type."""
    if not promo:
        return price, price
    if kind == "monthly" and promo.type == "monthly_discount":
        return max(1, price * (100 - promo.value) // 100), price
    if kind == "lifetime" and promo.type == "lifetime_discount":
        return max(1, price * (100 - promo.value) // 100), price
    return price, price


def fmt_countdown(seconds: int) -> str:
    """Human-friendly countdown — picks the largest meaningful unit."""
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m"
    if seconds < 86400:
        h, m = seconds // 3600, (seconds % 3600) // 60
        return f"{h}h {m}m" if m else f"{h}h"
    d, h = seconds // 86400, (seconds % 86400) // 3600
    return f"{d}d {h}h" if h else f"{d}d"


__all__ = [
    "Promo",
    "PROMO_TYPES",
    "apply_diamond_bonus",
    "apply_price_discount",
    "clear_promo",
    "fmt_countdown",
    "get_active_promo",
    "set_promo",
]
