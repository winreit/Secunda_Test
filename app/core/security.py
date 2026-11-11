from hmac import compare_digest
from typing import Annotated

from fastapi import Header, HTTPException, status

from app.core.config import settings


async def verify_api_key(
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> None:
    expected = settings.API_KEY.get_secret_value()
    if x_api_key is None or not compare_digest(x_api_key, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
