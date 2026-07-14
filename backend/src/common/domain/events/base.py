"""Base class for domain events."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class Event(BaseModel):
    """Generic envelope. Concrete subclasses set `channel` and add fields."""

    seq: int
    ts: datetime
    payload: dict

    model_config = ConfigDict(extra="forbid")

    @property
    def channel(self) -> str:
        raise NotImplementedError("Event subclasses must override the `channel` property")
