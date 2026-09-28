from uuid import uuid4

from expects import equal, expect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.common.database.models import EmailAddressORM
from src.users.infrastructure.repositories.sql_email_address import SQLEmailAddressRepository


async def test_get_or_create__is_durable_after_the_session_closes(
    async_session: AsyncSession,
    session_maker: async_sessionmaker[AsyncSession],
):
    email = f"email-{uuid4().hex[:12]}@example.com"

    created = await SQLEmailAddressRepository(session=async_session).get_or_create(email)
    await async_session.close()

    async with session_maker() as session:
        stored = (await session.execute(select(EmailAddressORM).where(EmailAddressORM.email == email))).scalar_one()
    expect(stored.uuid).to(equal(created.uuid))


async def test_get_or_create__returns_the_existing_address(
    async_session: AsyncSession,
    session_maker: async_sessionmaker[AsyncSession],
):
    email = f"email-{uuid4().hex[:12]}@example.com"
    created = await SQLEmailAddressRepository(session=async_session).get_or_create(email)

    async with session_maker() as other_session:
        found = await SQLEmailAddressRepository(session=other_session).get_or_create(email)

    expect(found.uuid).to(equal(created.uuid))
