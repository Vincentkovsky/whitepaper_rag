from __future__ import annotations

import logging
from dataclasses import dataclass, field
import hashlib
import secrets
import uuid
from datetime import datetime, timezone
from functools import lru_cache
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

SUBSCRIPTION_PLANS: Dict[str, Dict] = {
    "free": {
        "price": 0,
        "monthly_credits": 100,
        "features": ["basic_qa", "simple_analysis"],
    },
    "basic": {
        "price": 29,
        "monthly_credits": 1500,
        "features": ["basic_qa", "full_analysis", "export_pdf"],
    },
    "pro": {
        "price": 99,
        "monthly_credits": 6000,
        "features": [
            "basic_qa",
            "full_analysis",
            "export_pdf",
            "api_access",
            "batch_analysis",
            "priority_queue",
        ],
    },
    "enterprise": {
        "price": "custom",
        "monthly_credits": "custom",
        "features": ["all", "priority_support", "custom_deployment", "dedicated_resources"],
    },
}

CREDIT_PRICING: Dict[str, Dict] = {
    "document_upload_pdf": {"credits": 2, "description": "Upload + vectorize PDF"},
    "document_upload_url": {"credits": 2, "description": "Fetch + vectorize webpage"},
    "qa_mini": {"credits": 0.1, "description": "Mini model QA"},
    "qa_turbo": {"credits": 2, "description": "Turbo model QA"},
    "analysis_report": {"credits": 50, "description": "Full LangGraph analysis"},
}


@dataclass
class SubscriptionLedger:
    plan: str = "free"
    consumed: float = 0.0
    history: List[Dict[str, str]] = field(default_factory=list)


@dataclass
class ApiKeyEntry:
    id: str
    name: Optional[str]
    key_hash: str
    created_at: str
    last_used_at: Optional[str] = None


class SubscriptionService:
    """In-memory subscription + credit ledger for development."""

    def __init__(self) -> None:
        self._ledgers: Dict[str, SubscriptionLedger] = {}
        self._api_keys: Dict[str, List[ApiKeyEntry]] = {}

    # ---- Plan helpers -------------------------------------------------
    def list_plans(self) -> Dict[str, Dict]:
        return SUBSCRIPTION_PLANS

    def get_user_plan(self, user_id: str) -> str:
        return self._ledger(user_id).plan

    def set_user_plan(self, user_id: str, plan: str) -> None:
        if plan not in SUBSCRIPTION_PLANS:
            raise ValueError("Unknown plan")
        ledger = self._ledger(user_id)
        ledger.plan = plan
        ledger.consumed = 0
        logger.info("Plan updated", extra={"user_id": user_id, "plan": plan})

    # ---- Credits ------------------------------------------------------
    def check_and_consume(self, user_id: str, sku: str) -> bool:
        pricing = CREDIT_PRICING.get(sku)
        if not pricing:
            raise ValueError(f"Unknown SKU: {sku}")
        ledger = self._ledger(user_id)
        monthly = self._monthly_quota(ledger.plan)
        if ledger.consumed + pricing["credits"] > monthly:
            return False
        ledger.consumed += pricing["credits"]
        ledger.history.append({"sku": sku, "action": "consume"})
        return True

    def consume_credits(self, user_id: str, sku: str) -> None:
        """Consume credits or raise error if insufficient"""
        if not self.check_and_consume(user_id, sku):
            raise ValueError("Insufficient credits")

    def refund_credits(self, user_id: str, sku: str, reason: str | None = None) -> None:
        pricing = CREDIT_PRICING.get(sku)
        if not pricing:
            logger.warning("Refund for unknown SKU", extra={"user_id": user_id, "sku": sku})
            return
        ledger = self._ledger(user_id)
        ledger.consumed = max(0, ledger.consumed - pricing["credits"])
        ledger.history.append({"sku": sku, "action": "refund", "reason": reason or ""})
        logger.info(
            "Refund credits",
            extra={"user_id": user_id, "sku": sku, "reason": reason},
        )

    def get_usage(self, user_id: str) -> Dict[str, float]:
        ledger = self._ledger(user_id)
        monthly = self._monthly_quota(ledger.plan)
        return {
            "plan": ledger.plan,
            "monthly_credits": monthly,
            "consumed_credits": round(ledger.consumed, 2),
            "remaining_credits": round(max(monthly - ledger.consumed, 0), 2),
        }

    # ---- Checkout / webhook stubs ------------------------------------
    def create_checkout_session(self, user_id: str, plan: str) -> Dict[str, str]:
        if plan not in SUBSCRIPTION_PLANS:
            raise ValueError("Unknown plan")
        checkout_url = f"https://checkout.lemonsqueezy.com/{plan}/{user_id}"
        logger.info("Checkout session created", extra={"user_id": user_id, "plan": plan})
        return {"plan": plan, "checkout_url": checkout_url}

    def handle_webhook(self, payload: Dict) -> Dict[str, str]:
        event = payload.get("meta", {}).get("event_name")
        data = payload.get("data", {}).get("attributes", {})
        user_id = data.get("user_id") or data.get("customer_id")
        plan_variant = data.get("variant_name")
        if event == "subscription_created" and user_id and plan_variant:
            plan_key = self._map_variant_to_plan(plan_variant)
            self.set_user_plan(user_id, plan_key)
            return {"status": "activated", "plan": plan_key}
        if event == "subscription_cancelled" and user_id:
            self.set_user_plan(user_id, "free")
            return {"status": "cancelled", "plan": "free"}
        return {"status": "ignored"}

    # ---- Helpers ------------------------------------------------------
    def reset_monthly_credits(self, user_id: Optional[str] = None) -> None:
        if user_id:
            ledger = self._ledger(user_id)
            ledger.consumed = 0
            ledger.history.append({"action": "reset"})
            return
        for ledger in self._ledgers.values():
            ledger.consumed = 0
            ledger.history.append({"action": "reset"})

    def _ledger(self, user_id: str) -> SubscriptionLedger:
        if user_id not in self._ledgers:
            self._ledgers[user_id] = SubscriptionLedger()
        return self._ledgers[user_id]

    def _monthly_quota(self, plan: str) -> float:
        quota = SUBSCRIPTION_PLANS.get(plan, {}).get("monthly_credits", 0)
        return float(quota) if isinstance(quota, (int, float)) else 0.0

    def _map_variant_to_plan(self, variant: str) -> str:
        variant_lower = variant.lower()
        for plan in SUBSCRIPTION_PLANS:
            if plan in variant_lower:
                return plan
        return "free"

    # ---- API Keys ------------------------------------------------------
    def list_api_keys(self, user_id: str) -> List[Dict[str, Optional[str]]]:
        entries = self._api_keys.get(user_id, [])
        return [
            {
                "id": entry.id,
                "name": entry.name,
                "created_at": entry.created_at,
                "last_used_at": entry.last_used_at,
            }
            for entry in entries
        ]

    def create_api_key(self, user_id: str, name: Optional[str] = None) -> Dict[str, str]:
        self.require_feature(user_id, "api_access")
        plain_key = secrets.token_urlsafe(32)
        entry = ApiKeyEntry(
            id=str(uuid.uuid4()),
            name=name,
            key_hash=self._hash_key(plain_key),
            created_at=_now_iso(),
        )
        self._api_keys.setdefault(user_id, []).append(entry)
        return {"id": entry.id, "api_key": plain_key}

    def delete_api_key(self, user_id: str, key_id: str) -> None:
        entries = self._api_keys.get(user_id, [])
        self._api_keys[user_id] = [entry for entry in entries if entry.id != key_id]

    def mark_api_key_used(self, user_id: str, plain_key: str) -> bool:
        key_hash = self._hash_key(plain_key)
        for entry in self._api_keys.get(user_id, []):
            if entry.key_hash == key_hash:
                entry.last_used_at = _now_iso()
                return True
        return False

    def require_feature(self, user_id: str, feature: str) -> None:
        plan = self.get_user_plan(user_id)
        features = SUBSCRIPTION_PLANS.get(plan, {}).get("features", [])
        if "all" in features:
            return
        if feature not in features:
            raise PermissionError(f"Plan '{plan}' does not include feature '{feature}'")

    def _hash_key(self, plain_key: str) -> str:
        return hashlib.sha256(plain_key.encode("utf-8")).hexdigest()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@lru_cache(maxsize=1)
def get_subscription_service() -> SubscriptionService:
    return SubscriptionService()


__all__ = [
    "SUBSCRIPTION_PLANS",
    "CREDIT_PRICING",
    "SubscriptionService",
    "get_subscription_service",
]

