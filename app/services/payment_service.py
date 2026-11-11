from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.payment import Payments


async def get_payment(db: AsyncSession, payment_id: int) -> Payments | None:
    return await db.scalar(select(Payments).where(Payments.id == payment_id))
