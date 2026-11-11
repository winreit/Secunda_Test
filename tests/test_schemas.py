from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.db.models.payment import Currency
from app.schemas.payment import PaymentCreate


def test_valid_payment_payload() -> None:
    payload = PaymentCreate(
        amount=Decimal("10.50"),
        currency=Currency.RUB,
        metadata={"order_id": 12},
    )
    assert payload.amount == Decimal("10.50")
    assert payload.currency is Currency.RUB


@pytest.mark.parametrize("amount", ["0", "-1", "0.001"])
def test_invalid_amount(amount: str) -> None:
    with pytest.raises(ValidationError):
        PaymentCreate(amount=amount, currency="RUB")


def test_invalid_currency() -> None:
    with pytest.raises(ValidationError):
        PaymentCreate(amount="1.00", currency="GBP")


def test_webhook_url_validation() -> None:
    with pytest.raises(ValidationError):
        PaymentCreate(amount="1.00", currency="RUB", webhook_url="not-a-url")
