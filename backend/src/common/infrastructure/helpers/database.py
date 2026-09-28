from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession

# Marks the session whose transaction an outer atomic_transaction owns. SQLAlchemy
# autobegins on the first statement, so `session.in_transaction()` cannot tell an
# owned transaction from an implicit one opened by a previous read.
_OWNER_KEY = "atomic_transaction_owner"


@asynccontextmanager
async def atomic_transaction(session: AsyncSession) -> AsyncGenerator[AsyncSession]:
    """Commit the block on success and roll it back on error.

    Only the outermost block commits. A nested block runs inside a savepoint: its
    failure rolls back only its own writes, and a failure of the outer block rolls
    back everything, including writes made by nested blocks.
    """
    if session.info.get(_OWNER_KEY):
        async with session.begin_nested():
            yield session
        return

    session.info[_OWNER_KEY] = True
    try:
        yield session
        await session.commit()
    except BaseException:
        await session.rollback()
        raise
    finally:
        session.info.pop(_OWNER_KEY, None)
