"""Account database records as migrate-profile sees them: one line per account, keyed by field 1."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class DbKind(StrEnum):
    PASSWD = "passwd"
    SHADOW = "shadow"
    GROUP = "group"
    GSHADOW = "gshadow"

    @property
    def list_fields(self) -> tuple[int, ...]:
        """1-based fields holding comma-separated member lists, as migrate-profile passes them."""
        return {
            DbKind.PASSWD: (),
            DbKind.SHADOW: (),
            DbKind.GROUP: (4,),
            DbKind.GSHADOW: (3, 4),
        }[self]

    @property
    def lf_arg(self) -> str:
        """The value migrate-profile gives the awk script as ``-v LF=``."""
        return ",".join(str(f) for f in self.list_fields)

    @property
    def field_count(self) -> int:
        return {DbKind.PASSWD: 7, DbKind.SHADOW: 9, DbKind.GROUP: 4, DbKind.GSHADOW: 4}[self]


@dataclass(frozen=True)
class AccountDb:
    """An ordered account database. Keeps raw lines so byte-exact comparisons stay possible."""

    lines: tuple[str, ...]

    @classmethod
    def parse(cls, text: str) -> AccountDb:
        return cls(tuple(line for line in text.splitlines() if line != ""))

    @classmethod
    def of(cls, *lines: str) -> AccountDb:
        return cls(tuple(lines))

    def render(self) -> str:
        return "".join(f"{line}\n" for line in self.lines)

    def keys(self) -> list[str]:
        return [line.split(":", 1)[0] for line in self.lines]

    def duplicate_keys(self) -> list[str]:
        seen: set[str] = set()
        dups: list[str] = []
        for key in self.keys():
            if key in seen and key not in dups:
                dups.append(key)
            seen.add(key)
        return dups

    def get(self, key: str) -> str | None:
        for line in self.lines:
            if line.split(":", 1)[0] == key:
                return line
        return None

    def as_dict(self) -> dict[str, str]:
        """Key to line. Later duplicates win; callers that care check duplicate_keys() first."""
        return {line.split(":", 1)[0]: line for line in self.lines}


def members(line: str, field: int) -> frozenset[str]:
    """The member set held in 1-based ``field`` of a group or gshadow line."""
    parts = line.split(":")
    if field > len(parts):
        return frozenset()
    return frozenset(m for m in parts[field - 1].split(",") if m)
