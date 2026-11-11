import pytest
from fastapi import HTTPException

from app.core.security import verify_api_key


@pytest.mark.asyncio
async def test_valid_api_key_is_accepted() -> None:
    assert await verify_api_key("test-api-key") is None


@pytest.mark.asyncio
async def test_missing_api_key_is_rejected() -> None:
    with pytest.raises(HTTPException) as exc_info:
        await verify_api_key(None)
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_invalid_api_key_is_rejected() -> None:
    with pytest.raises(HTTPException) as exc_info:
        await verify_api_key("wrong-key")
    assert exc_info.value.status_code == 401
