import asyncpg
import pytest


async def test_duplicate_source_external_ref_does_not_create_a_second_ticket(pool):
    await pool.execute(
        "INSERT INTO tickets (source, external_ref, body) VALUES ('telegram', 'ext-1', 'hello')"
    )

    with pytest.raises(asyncpg.UniqueViolationError):
        await pool.execute(
            "INSERT INTO tickets (source, external_ref, body) "
            "VALUES ('telegram', 'ext-1', 'hello again')"
        )

    count = await pool.fetchval(
        "SELECT COUNT(*) FROM tickets WHERE source = 'telegram' AND external_ref = 'ext-1'"
    )
    assert count == 1
