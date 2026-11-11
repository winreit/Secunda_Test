from decimal import Decimal
from types import SimpleNamespace

from app.schemas.payment import PaymentCreate
from app.services.idempotency import same_idempotent_request


def test_same_idempotency_key_payload_is_compared() -> None:
    payload = PaymentCreate(amount=Decimal("10.00"), currency="RUB", metadata={"x": 1})
    payment = SimpleNamespace(
        amount=Decimal("10.00"),
        currency=payload.currency,
        description=None,
        payment_metadata={"x": 1},
        webhook_url=None,
    )
    assert same_idempotent_request(payment, payload)


def test_different_payload_is_not_same_idempotent_request() -> None:
    payload = PaymentCreate(amount=Decimal("11.00"), currency="RUB")
    payment = SimpleNamespace(
        amount=Decimal("10.00"),
        currency=payload.currency,
        description=None,
        payment_metadata=None,
        webhook_url=None,
    )
    assert not same_idempotent_request(payment, payload)
