import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select

from app.core.config import settings
from app.db.database import SessionLocal
from app.db.models.outbox import OutboxMessage
from app.messaging.broker import broker

logger = logging.getLogger(__name__)


async def publish_pending_batch() -> int:
    now = datetime.now(timezone.utc)
    lock_until = now + timedelta(seconds=settings.OUTBOX_LOCK_SECONDS)

    # Claim rows in a short transaction. SKIP LOCKED allows multiple workers.
    async with SessionLocal() as db:
        result = await db.execute(
            select(OutboxMessage)
            .where(
                OutboxMessage.published_at.is_(None),
                or_(OutboxMessage.locked_until.is_(None), OutboxMessage.locked_until < now),
                or_(OutboxMessage.next_attempt_at.is_(None), OutboxMessage.next_attempt_at <= now),
            )
            .order_by(OutboxMessage.id)
            .limit(settings.OUTBOX_BATCH_SIZE)
            .with_for_update(skip_locked=True)
        )
        messages = list(result.scalars().all())
        for message in messages:
            message.locked_until = lock_until
            message.attempts += 1
        await db.commit()
        claimed = [(m.id, m.event_type, dict(m.payload)) for m in messages]

    published = 0
    for message_id, event_type, payload in claimed:
        try:
            await broker.publish(
                message=payload,
                queue="payments.new",
                message_id=str(message_id),
                headers={"event_type": event_type, "outbox_id": str(message_id)},
                persist=True,
            )
            async with SessionLocal() as db:
                message = await db.get(OutboxMessage, message_id)
                if message and message.published_at is None:
                    message.published_at = datetime.now(timezone.utc)
                    message.locked_until = None
                    message.last_error = None
                    await db.commit()
            published += 1
        except Exception as exc:
            logger.exception("Failed to publish outbox message %s", message_id)
            async with SessionLocal() as db:
                message = await db.get(OutboxMessage, message_id)
                if message and message.published_at is None:
                    delay = min(2 ** min(message.attempts, 8), 300)
                    message.locked_until = None
                    message.next_attempt_at = datetime.now(timezone.utc) + timedelta(seconds=delay)
                    message.last_error = str(exc)[:4000]
                    await db.commit()
    return published


async def run_outbox_worker() -> None:
    await broker.start()
    logger.info("Outbox worker started")
    try:
        while True:
            await publish_pending_batch()
            await asyncio.sleep(settings.OUTBOX_POLL_INTERVAL)
    finally:
        await broker.stop()


if __name__ == "__main__":
    asyncio.run(run_outbox_worker())
