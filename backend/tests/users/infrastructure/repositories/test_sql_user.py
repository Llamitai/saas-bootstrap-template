from uuid import uuid4

import pytest
from expects import be_none, equal, expect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.common.database.models import EmailAddressORM, PhoneNumberORM, UserORM
from src.common.domain.enums.countries import CountryIsoCode
from src.common.domain.models.phone_number import PhoneNumber
from src.common.domain.models.user import User
from src.common.infrastructure.helpers.database import atomic_transaction
from src.tenants.infrastructure.repositories.sql_tenant_user import SQLTenantUserRepository
from src.users.infrastructure.repositories.sql_user import SQLUserRepository


class OuterBlockError(Exception):
    pass


def _repository(session: AsyncSession) -> SQLUserRepository:
    return SQLUserRepository(session=session, tenant_user_repository=SQLTenantUserRepository(session=session))


def _new_user() -> User:
    return User.from_raw(email=f"user-{uuid4().hex[:12]}@example.com", first_name="Ada")


async def _find_user(session_maker: async_sessionmaker[AsyncSession], user: User) -> UserORM | None:
    async with session_maker() as session:
        return await session.get(UserORM, user.uuid)


async def _find_email(session_maker: async_sessionmaker[AsyncSession], email: str) -> EmailAddressORM | None:
    async with session_maker() as session:
        result = await session.execute(select(EmailAddressORM).where(EmailAddressORM.email == email))
        return result.scalar_one_or_none()


async def test_create_user__is_durable_after_the_session_closes(
    async_session: AsyncSession,
    session_maker: async_sessionmaker[AsyncSession],
):
    user = _new_user()

    await _repository(async_session).create_user(user, password="s3cret-password")
    await async_session.close()

    stored = await _find_user(session_maker, user)
    expect(stored.first_name).to(equal("Ada"))


async def test_create_user__never_stores_the_raw_password(
    async_session: AsyncSession,
    session_maker: async_sessionmaker[AsyncSession],
):
    user = _new_user()
    repository = _repository(async_session)

    await repository.create_user(user, password="s3cret-password")

    stored = await _find_user(session_maker, user)
    expect(stored.password == "s3cret-password").to(equal(False))
    expect(await repository.check_password(user.uuid, "s3cret-password")).to(equal(True))
    expect(await repository.check_password(user.uuid, "wrong-password")).to(equal(False))


def _new_phone_number() -> PhoneNumber:
    return PhoneNumber(uuid=uuid4(), dial_code=51, phone_number=str(uuid4().int)[:9], iso_code=CountryIsoCode.PERU)


async def _find_phone(session_maker: async_sessionmaker[AsyncSession], phone: PhoneNumber) -> PhoneNumberORM | None:
    async with session_maker() as session:
        result = await session.execute(
            select(PhoneNumberORM).where(
                PhoneNumberORM.dial_code == phone.dial_code,
                PhoneNumberORM.phone_number == phone.phone_number,
            )
        )
        return result.scalar_one_or_none()


async def test_persist__outer_failure_rolls_back_user_changes_and_nested_writes(
    async_session: AsyncSession,
    session_maker: async_sessionmaker[AsyncSession],
):
    repository = _repository(async_session)
    user = await repository.create_user(_new_user(), password="s3cret-password")
    phone = _new_phone_number()
    user.phone_number = phone
    user.first_name = "Changed"

    with pytest.raises(OuterBlockError):
        async with atomic_transaction(async_session):
            await repository.persist(user)
            raise OuterBlockError

    expect(await _find_phone(session_maker, phone)).to(be_none)
    expect((await _find_user(session_maker, user)).first_name).to(equal("Ada"))


async def test_persist__stores_the_user_phone_number(
    async_session: AsyncSession,
    session_maker: async_sessionmaker[AsyncSession],
):
    repository = _repository(async_session)
    user = await repository.create_user(_new_user(), password="s3cret-password")
    phone = _new_phone_number()
    user.phone_number = phone

    await repository.persist(user)
    await async_session.close()

    stored_phone = await _find_phone(session_maker, phone)
    expect((await _find_user(session_maker, user)).phone_number_id).to(equal(stored_phone.uuid))


async def test_remove__is_durable_after_the_session_closes(
    async_session: AsyncSession,
    session_maker: async_sessionmaker[AsyncSession],
):
    user = _new_user()
    repository = _repository(async_session)
    await repository.create_user(user, password="s3cret-password")

    await repository.remove(user.uuid)
    await async_session.close()

    expect(await _find_user(session_maker, user)).to(be_none)
