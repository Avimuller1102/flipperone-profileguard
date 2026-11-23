"""Expectations on a merged account database. Each returns None when met, or what was observed."""

from __future__ import annotations

from dataclasses import dataclass

from profileguard.accountdb import AccountDb, members


@dataclass(frozen=True)
class Check:
    def describe(self) -> str:
        raise NotImplementedError

    def evaluate(self, merged: AccountDb) -> str | None:
        raise NotImplementedError


def _show(line: str | None) -> str:
    return "(absent)" if line is None else line


@dataclass(frozen=True)
class LineIs(Check):
    key: str
    line: str
    why: str = ""

    def describe(self) -> str:
        return f"'{self.key}' is exactly: {self.line}" + (f" ({self.why})" if self.why else "")

    def evaluate(self, merged: AccountDb) -> str | None:
        got = merged.get(self.key)
        return None if got == self.line else f"'{self.key}' is: {_show(got)}"


@dataclass(frozen=True)
class Absent(Check):
    key: str
    why: str = ""

    def describe(self) -> str:
        return f"'{self.key}' is absent" + (f" ({self.why})" if self.why else "")

    def evaluate(self, merged: AccountDb) -> str | None:
        got = merged.get(self.key)
        return None if got is None else f"'{self.key}' is present: {got}"


@dataclass(frozen=True)
class MembersAre(Check):
    key: str
    field: int
    expected: frozenset[str]
    why: str = ""

    def describe(self) -> str:
        want = ",".join(sorted(self.expected)) or "(none)"
        return f"'{self.key}' field {self.field} members are {{{want}}}" + (
            f" ({self.why})" if self.why else ""
        )

    def evaluate(self, merged: AccountDb) -> str | None:
        line = merged.get(self.key)
        if line is None:
            return f"'{self.key}' is absent"
        got = members(line, self.field)
        if got == self.expected:
            return None
        return (
            f"'{self.key}' field {self.field} members are {{{','.join(sorted(got)) or '(none)'}}}"
        )


@dataclass(frozen=True)
class WellFormed(Check):
    """What migrate-profile itself demands before installing a merge (migrate-profile:421-428)."""

    def describe(self) -> str:
        return "a 'root' entry exists and no key appears twice"

    def evaluate(self, merged: AccountDb) -> str | None:
        problems = []
        if merged.get("root") is None:
            problems.append("no root entry")
        dups = merged.duplicate_keys()
        if dups:
            problems.append(f"duplicate keys: {', '.join(dups)}")
        return "; ".join(problems) or None
