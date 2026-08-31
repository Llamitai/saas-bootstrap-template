from dataclasses import dataclass
from typing import Any

from expects import equal, expect

from src.common.domain.entities.common.pagination import Page
from src.common.domain.interfaces.presenter import Presenter


@dataclass
class _IntegerPresenter(Presenter[int]):
    instance: int

    @property
    def to_dict(self) -> dict[str, Any]:
        return {"value": self.instance}


def test_apply_presenter__returns_a_presented_page_without_mutating_the_source():
    source = Page[int](next_cursor="next", items=[1, 2], limit=2)

    presented = source.apply_presenter(_IntegerPresenter)

    expect(presented.items).to(equal([{"value": 1}, {"value": 2}]))
    expect(presented.next_cursor).to(equal("next"))
    expect(presented.limit).to(equal(2))
    expect(source.items).to(equal([1, 2]))
