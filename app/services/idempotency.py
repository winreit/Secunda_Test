from app.db.models.payment import Payments
from app.schemas.payment import PaymentCreate


def same_idempotent_request(payment: Payments, payload: PaymentCreate) -> bool:
    return (
        payment.amount == payload.amount
        and payment.currency == payload.currency
        and payment.description == payload.description
        and payment.payment_metadata == payload.metadata
        and payment.webhook_url == (str(payload.webhook_url) if payload.webhook_url else None)
    )
