from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_api_key
from app.db.database import get_db
from app.db.models.outbox import OutboxMessage
from app.db.models.payment import Payments, StatusEnum
from app.schemas.payment import PaymentCreate, PaymentResponse
from app.services.idempotency import same_idempotent_request
from app.services.payment_service import get_payment as fetch_payment

router = APIRouter(
    prefix="/payments",
    tags=["payments"],
    dependencies=[Depends(verify_api_key)],
)


@router.post(
    "",
    response_model=PaymentResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_payment(
    payload: PaymentCreate,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)],
    db: AsyncSession = Depends(get_db),
) -> Payments:
    existing = await db.scalar(
        select(Payments).where(Payments.idempotency_key == idempotency_key)
    )
    if existing is not None:
        if not same_idempotent_request(existing, payload):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Idempotency-Key was already used with a different request",
            )
        return existing

    payment = Payments(
        amount=payload.amount,
        currency=payload.currency,
        description=payload.description,
        payment_metadata=payload.metadata,
        webhook_url=str(payload.webhook_url) if payload.webhook_url else None,
        idempotency_key=idempotency_key,
        status=StatusEnum.pending,
    )
    db.add(payment)
    try:
        await db.flush()
        db.add(
            OutboxMessage(
                event_type="payment.created",
                payload={"payment_id": payment.id},
            )
        )
        await db.commit()
        await db.refresh(payment)
        return payment
    except IntegrityError:
        await db.rollback()
        existing = await db.scalar(
            select(Payments).where(Payments.idempotency_key == idempotency_key)
        )
        if existing is not None:
            if same_idempotent_request(existing, payload):
                return existing
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Idempotency-Key was already used with a different request",
            )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Payment conflicts with an existing record",
        )


@router.get("/{payment_id}", response_model=PaymentResponse)
async def get_payment(
    payment_id: int,
    db: AsyncSession = Depends(get_db),
) -> Payments:
    payment = await fetch_payment(db, payment_id)
    if payment is None:
        raise HTTPException(status_code=404, detail="Payment not found")
    return payment
