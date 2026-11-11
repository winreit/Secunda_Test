import asyncio
import logging
import random
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

import httpx
from sqlalchemy import select

from app.core.config import settings
from app.db.database import SessionLocal
from app.db.models.payment import Payments, StatusEnum
from app.db.models.dead_letter import DeadLetterMessage
from app.messaging.broker import broker

logger = logging.getLogger(__name__)


async def send_webhook_with_retry(webhook_url: str, payload: dict[str, Any]) -> None:
    if not webhook_url:
        return

    timeout = settings.WEBHOOK_TIMEOUT_SECONDS
    attempts = settings.WEBHOOK_MAX_ATTEMPTS
    async with httpx.AsyncClient(timeout=timeout) as client:
        for attempt in range(1, attempts + 1):
            try:
                response = await client.post(
                    webhook_url,
                    json=payload,
                    headers={"Idempotency-Key": str(payload["payment_id"])},
                )
                response.raise_for_status()
                return
            except (httpx.HTTPError, httpx.TimeoutException) as exc:
                logger.warning("Webhook attempt %s/%s failed: %s", attempt, attempts, exc)
                if attempt == attempts:
                    raise
                await asyncio.sleep(2 ** attempt)


async def process_payment_message(msg: dict[str, Any]) -> None:
    payment_id = int(msg["payment_id"])

    async with SessionLocal() as db:
        async with db.begin():
            payment = await db.scalar(
                select(Payments)
                .where(Payments.id == payment_id)
                .with_for_update()
            )
            if payment is None:
                logger.warning("Payment %s not found", payment_id)
                return
            if payment.status is not StatusEnum.pending:
                logger.info("Payment %s already processed with status %s", payment_id, payment.status.value)
                return

            await asyncio.sleep(random.uniform(2.0, 5.0))
            new_status = StatusEnum.succeeded if random.random() < 0.9 else StatusEnum.failed
            payment.status = new_status
            payment.processed_at = datetime.now(timezone.utc)
            amount = payment.amount
            currency = payment.currency
            webhook_url = payment.webhook_url

    webhook_payload = {
        "payment_id": payment_id,
        "status": new_status.value,
        "amount": format(Decimal(amount), "f"),
        "currency": currency.value,
    }
    if webhook_url:
        try:
            await send_webhook_with_retry(webhook_url, webhook_payload)
        except Exception as exc:
            logger.exception("Webhook failed for payment %s; sending to DLQ", payment_id)
            await broker.publish(
                message={
                    "payment_id": payment_id,
                    "webhook_url": webhook_url,
                    "payload": webhook_payload,
                    "error": str(exc),
                    "failed_at": datetime.now(timezone.utc).isoformat(),
                },
                queue="payments.dlq",
                persist=True,
            )


@broker.subscriber("payments.new")
async def payment_created_subscriber(msg: dict[str, Any]) -> None:
    await process_payment_message(msg)


@broker.subscriber("payments.dlq")
async def webhook_dlq_subscriber(msg: dict[str, Any]) -> None:
    failed_at_raw = msg.get("failed_at")
    failed_at = (
        datetime.fromisoformat(failed_at_raw)
        if isinstance(failed_at_raw, str)
        else datetime.now(timezone.utc)
    )
    async with SessionLocal() as db:
        db.add(
            DeadLetterMessage(
                payment_id=msg.get("payment_id"),
                payload={**(msg.get("payload") or {}), "webhook_url": msg.get("webhook_url")},
                error=str(msg.get("error", "Unknown webhook delivery error")),
                failed_at=failed_at,
            )
        )
        await db.commit()
    logger.error("Webhook delivery for payment %s persisted to DLQ storage", msg.get("payment_id"))
