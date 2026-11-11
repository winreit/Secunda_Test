from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from app.db.models.payment import Currency, StatusEnum


class PaymentCreate(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    currency: Currency
    description: str | None = Field(default=None, max_length=2000)
    metadata: dict[str, Any] | None = None
    webhook_url: HttpUrl | None = None


class PaymentResponse(BaseModel):
    id: int
    amount: Decimal
    currency: Currency
    description: str | None
    metadata: dict[str, Any] | None = Field(validation_alias="payment_metadata")
    status: StatusEnum
    created_at: datetime
    processed_at: datetime | None

    model_config = ConfigDict(from_attributes=True)
