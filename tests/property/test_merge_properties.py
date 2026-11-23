"""Properties of the real upstream merge over generated account databases.

Each property restates a sentence of the script's header (libs/flipper-accountdb.awk:3-5).
Every file always holds a root entry, which keeps the dev snapshot clear of the empty-file bug
that PR #4 fixes; scenario AM-10 covers that case on its own.
"""

from __future__ import annotations

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from profileguard.accountdb import AccountDb, DbKind, members
from profileguard.merger import run_merge
from profileguard.targets import Target
from tests.conftest import primary_awk

AWK = primary_awk()
KEYS = ("daemon", "user", "alice", "bob", "svc")
SETTINGS = settings(
    max_examples=150, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)

value = st.sampled_from(["v1", "v2", "v3"])
side = st.dictionaries(st.sampled_from(KEYS), value)


def shadow_db(d: dict[str, str]) -> AccountDb:
    return AccountDb.of("root:*:1:0:99999:7:::", *(f"{k}:{v}:1:0:99999:7:::" for k, v in d.items()))


def merged(target: Target, b: dict[str, str], o: dict[str, str], t: dict[str, str]) -> AccountDb:
    return run_merge(AWK, target.script, DbKind.SHADOW, shadow_db(b), shadow_db(o), shadow_db(t))


def check_header_contract(
    b: dict[str, str], o: dict[str, str], t: dict[str, str], out: AccountDb
) -> None:
    assert out.duplicate_keys() == []
    got = out.as_dict()
    line = lambda d, k: f"{k}:{d[k]}:1:0:99999:7:::"  # noqa: E731
    for k in KEYS:
        if k in t and (k not in b or t[k] != b[k]) and (k in b or k not in o):
            assert got.get(k) == line(t, k), f"{k}: profile's change must ride along"
        elif k in t and k in b and t[k] == b[k]:
            assert got.get(k) == (line(o, k) if k in o else None), f"{k}: must follow new base"
        elif k not in t and k in b and k in o and o[k] == b[k]:
            assert k not in got, f"{k}: deletion in the profile must hold"
        elif k not in t and k not in b and k in o:
            assert got.get(k) == line(o, k), f"{k}: new base's addition must appear"
        elif k not in t and k not in o:
            assert k not in got


def _props(target_fixture: str) -> None:
    @SETTINGS
    @given(b=side, o=side, t=side)
    def contract(request, b, o, t):  # type: ignore[no-untyped-def]
        target = request.getfixturevalue(target_fixture)
        check_header_contract(b, o, t, merged(target, b, o, t))

    globals()[f"test_header_contract_{target_fixture}"] = contract


_props("snapshot")
_props("pr4")


@SETTINGS
@given(b=side, o=side, t=side)
def test_reapplying_the_same_update_changes_nothing(snapshot: Target, b, o, t) -> None:  # type: ignore[no-untyped-def]
    """update-profile run twice onto one build: the second merge's base is the first's new base."""
    first = merged(snapshot, b, o, t)
    second = run_merge(AWK, snapshot.script, DbKind.SHADOW, shadow_db(o), shadow_db(o), first)
    assert sorted(second.lines) == sorted(first.lines)


members_st = st.frozensets(st.sampled_from(["user", "alice", "bob", "svc"]))


@SETTINGS
@given(mb=members_st, mo=members_st, mt=members_st)
def test_group_members_are_three_way_set_merged(snapshot: Target, mb, mo, mt) -> None:  # type: ignore[no-untyped-def]
    def db(m: frozenset[str]) -> AccountDb:
        return AccountDb.of("root:x:0:", f"video:x:44:{','.join(sorted(m))}")

    out = run_merge(AWK, snapshot.script, DbKind.GROUP, db(mb), db(mo), db(mt))
    line = out.get("video")
    assert line is not None
    removed = {m for m in mb if m not in mo or m not in mt}
    assert members(line, 4) == (mo | mt) - removed
