"""Deterministic command runner used by the Dependabot skill tests."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Sequence


@dataclass(frozen=True)
class RecordedCall:
    """One invocation observed by :class:`FakeRunner`."""

    args: tuple[str, ...]
    cwd: Path | None
    env: dict[str, str] | None
    mutating: bool


@dataclass
class _Expectation:
    predicate: Callable[[RecordedCall], bool]
    responder: Callable[[RecordedCall], object]
    description: str
    remaining: int | None


class FakeRunner:
    """Strict, stateful fake for the executor's ``Runner`` seam.

    Responses are matched in registration order. By default every expectation is
    consumed once, which makes accidental duplicate mutations visible. Pass
    ``times=None`` for a reusable handler such as a read-only status query.
    """

    def __init__(self, result_type: type[object]) -> None:
        self._result_type = result_type
        self._expectations: list[_Expectation] = []
        self.calls: list[RecordedCall] = []
        self.sleeps: list[float] = []

    def expect(
        self,
        args: Sequence[str],
        *,
        stdout: str = "",
        stderr: str = "",
        returncode: int = 0,
        mutating: bool | None = None,
        times: int | None = 1,
    ) -> None:
        expected = tuple(args)

        def matches(call: RecordedCall) -> bool:
            return call.args == expected and (
                mutating is None or call.mutating is mutating
            )

        self.when(
            matches,
            lambda _call: self.result(
                returncode=returncode,
                stdout=stdout,
                stderr=stderr,
            ),
            description=" ".join(expected),
            times=times,
        )

    def when(
        self,
        predicate: Callable[[RecordedCall], bool],
        responder: Callable[[RecordedCall], object],
        *,
        description: str,
        times: int | None = 1,
    ) -> None:
        if times is not None and times < 1:
            raise ValueError("times must be positive or None")
        self._expectations.append(
            _Expectation(
                predicate=predicate,
                responder=responder,
                description=description,
                remaining=times,
            )
        )

    def result(
        self,
        returncode: int = 0,
        stdout: str = "",
        stderr: str = "",
    ) -> object:
        return self._result_type(returncode, stdout, stderr)

    def run(
        self,
        args: Sequence[str],
        cwd: str | Path | None = None,
        env: Mapping[str, str] | None = None,
        mutating: bool = False,
    ) -> object:
        call = RecordedCall(
            args=tuple(str(arg) for arg in args),
            cwd=Path(cwd) if cwd is not None else None,
            env=dict(env) if env is not None else None,
            mutating=mutating,
        )
        self.calls.append(call)

        for expectation in self._expectations:
            if expectation.remaining == 0 or not expectation.predicate(call):
                continue
            if expectation.remaining is not None:
                expectation.remaining -= 1
            return expectation.responder(call)

        rendered = " ".join(call.args)
        raise AssertionError(f"Unexpected command: {rendered}")

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)

    @property
    def mutating_calls(self) -> list[RecordedCall]:
        return [call for call in self.calls if call.mutating]

    def assert_exhausted(self) -> None:
        pending = [
            expectation.description
            for expectation in self._expectations
            if expectation.remaining not in (None, 0)
        ]
        if pending:
            raise AssertionError(f"Expected commands were not called: {pending}")
