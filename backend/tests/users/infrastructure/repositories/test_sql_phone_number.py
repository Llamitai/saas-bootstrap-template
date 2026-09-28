from uuid import uuid4

from expects import equal, expect
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.common.database.models import PhoneNumberORM
from src.common.domain.entities.phone_number import RawPhoneNumber
from src.common.domain.enums.countries import CountryIsoCode
from src.users.infrastructure.repositories.sql_phone_number import SQLPhoneNumberRepository


def _raw_phone_number() -> RawPhoneNumber:
    return RawPhoneNumber(dial_code=51, phone_number=str(uuid4().int)[:9], iso_code=CountryIsoCode.PERU)


async def test_get_or_create__is_durable_after_the_session_closes(
    async_session: AsyncSession,
    session_maker: async_sessionmaker[AsyncSession],
):
    raw = _raw_phone_number()

    created = await SQLPhoneNumberRepository(session=async_session).get_or_create(raw)
    await async_session.close()

    async with session_maker() as session:
        stored = await session.get(PhoneNumberORM, created.uuid)
    expect(stored.phone_number).to(equal(raw.phone_number))


async def test_get_or_create__returns_the_existing_number(
    async_session: AsyncSession,
    session_maker: async_sessionmaker[AsyncSession],
):
    raw = _raw_phone_number()
    created = await SQLPhoneNumberRepository(session=async_session).get_or_create(raw)

    async with session_maker() as other_session:
        found = await SQLPhoneNumberRepository(session=other_session).get_or_create(raw)

    expect(found.uuid).to(equal(created.uuid))
