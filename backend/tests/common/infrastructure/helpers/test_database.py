from uuid import uuid4

import pytest
from expects import be_none, equal, expect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.common.database.models import EmailAddressORM
from src.common.infrastructure.helpers.database import atomic_transaction


class OuterBlockError(Exception):
    pass


def _unique_email() -> str:
    return f"tx-{uuid4().hex[:12]}@example.com"


async def _find_email(session_maker: async_sessionmaker[AsyncSession], email: str) -> EmailAddressORM | None:
    async with session_maker() as session:
        result = await session.execute(select(EmailAddressORM).where(EmailAddressORM.email == email))
        return result.scalar_one_or_none()


async def test_atomic_transaction__commits_when_the_block_succeeds(
    async_session: AsyncSession,
    session_maker: async_sessionmaker[AsyncSession],
):
    email = _unique_email()

    async with atomic_transaction(async_session):
        async_session.add(EmailAddressORM(email=email))
    await async_session.close()

    expect((await _find_email(session_maker, email)).email).to(equal(email))


async def test_atomic_transaction__outer_failure_rolls_back_inner_writes(
    async_session: AsyncSession,
    session_maker: async_sessionmaker[AsyncSession],
):
    inner_email = _unique_email()
    outer_email = _unique_email()

    with pytest.raises(OuterBlockError):
        async with atomic_transaction(async_session):
            async_session.add(EmailAddressORM(email=outer_email))
            async with atomic_transaction(async_session):
                async_session.add(EmailAddressORM(email=inner_email))
                await async_session.flush()
            raise OuterBlockError

    expect(await _find_email(session_maker, inner_email)).to(be_none)
    expect(await _find_email(session_maker, outer_email)).to(be_none)


async def test_atomic_transaction__inner_block_does_not_commit_the_outer_one(
    async_session: AsyncSession,
    session_maker: async_sessionmaker[AsyncSession],
):
    email = _unique_email()

    async with atomic_transaction(async_session):
        async with atomic_transaction(async_session):
            async_session.add(EmailAddressORM(email=email))
            await async_session.flush()

        expect(await _find_email(session_maker, email)).to(be_none)

    expect((await _find_email(session_maker, email)).email).to(equal(email))


async def test_atomic_transaction__inner_failure_rolls_back_only_its_savepoint(
    async_session: AsyncSession,
    session_maker: async_sessionmaker[AsyncSession],
):
    kept_email = _unique_email()
    discarded_email = _unique_email()

    async with atomic_transaction(async_session):
        async_session.add(EmailAddressORM(email=kept_email))
        await async_session.flush()
        with pytest.raises(OuterBlockError):
            async with atomic_transaction(async_session):
                async_session.add(EmailAddressORM(email=discarded_email))
                await async_session.flush()
                raise OuterBlockError

    expect((await _find_email(session_maker, kept_email)).email).to(equal(kept_email))
    expect(await _find_email(session_maker, discarded_email)).to(be_none)


async def test_atomic_transaction__a_new_block_after_a_failure_commits_again(
    async_session: AsyncSession,
    session_maker: async_sessionmaker[AsyncSession],
):
    email = _unique_email()
    with pytest.raises(OuterBlockError):
        async with atomic_transaction(async_session):
            raise OuterBlockError

    async with atomic_transaction(async_session):
        async_session.add(EmailAddressORM(email=email))

    expect((await _find_email(session_maker, email)).email).to(equal(email))
