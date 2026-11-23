from profileguard.accountdb import AccountDb
from profileguard.checks import Absent, LineIs, MembersAre, WellFormed


def test_line_is() -> None:
    db = AccountDb.of("root:x", "user:y")
    assert LineIs("user", "user:y").evaluate(db) is None
    assert LineIs("user", "user:z").evaluate(db) == "'user' is: user:y"
    assert LineIs("bob", "bob:z").evaluate(db) == "'bob' is: (absent)"


def test_absent() -> None:
    db = AccountDb.of("root:x", "user:y")
    assert Absent("bob").evaluate(db) is None
    assert Absent("user").evaluate(db) == "'user' is present: user:y"


def test_members_are_order_insensitive() -> None:
    db = AccountDb.of("video:x:44:b,a")
    assert MembersAre("video", 4, frozenset({"a", "b"})).evaluate(db) is None
    assert MembersAre("video", 4, frozenset({"a"})).evaluate(db) is not None
    assert MembersAre("audio", 4, frozenset()).evaluate(db) == "'audio' is absent"


def test_well_formed_reports_every_problem() -> None:
    assert WellFormed().evaluate(AccountDb.of("root:x", "a:1")) is None
    bad = WellFormed().evaluate(AccountDb.of("a:1", "a:2"))
    assert bad == "no root entry; duplicate keys: a"
