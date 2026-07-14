import uuid
from unittest.mock import AsyncMock

import pytest

from app.services.repository import upsert_lead_fields


@pytest.mark.asyncio
async def test_no_lead_field_is_written_without_prior_consent() -> None:
    db = AsyncMock()
    db.scalar.return_value = None
    result = await upsert_lead_fields(
        db,
        uuid.uuid4(),
        {"name": "Sensitive Name", "email": "private@example.com"},
    )
    assert result.consented is False
    assert result.lead is None
    db.add.assert_not_called()
    db.flush.assert_not_awaited()
