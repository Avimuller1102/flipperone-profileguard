from profileguard.accountdb import AccountDb, DbKind, members


def test_parse_drops_blank_lines_and_roundtrips() -> None:
    db = AccountDb.parse("root:x:0:\n\nuser:x:1000:\n")
    assert db.lines == ("root:x:0:", "user:x:1000:")
    assert db.render() == "root:x:0:\nuser:x:1000:\n"


def test_empty_database_renders_as_empty_file() -> None:
    assert AccountDb.of().render() == ""


def test_duplicate_keys_reported_once_each() -> None:
    db = AccountDb.of("a:1", "b:1", "a:2", "a:3")
    assert db.duplicate_keys() == ["a"]


def test_get_matches_whole_key_not_prefix() -> None:
    db = AccountDb.of("user:x", "username:y")
    assert db.get("user") == "user:x"
    assert db.get("use") is None


def test_members_ignores_empty_entries() -> None:
    assert members("sudo:x:27:a,,b", 4) == {"a", "b"}
    assert members("sudo:x:27:", 4) == frozenset()
    assert members("short", 4) == frozenset()


def test_list_fields_match_migrate_profile() -> None:
    # scripts/migrate-profile:405-408 at bb92d87
    assert DbKind.GROUP.lf_arg == "4"
    assert DbKind.GSHADOW.lf_arg == "3,4"
    assert DbKind.SHADOW.lf_arg == ""
    assert DbKind.PASSWD.lf_arg == ""
    assert (DbKind.PASSWD.field_count, DbKind.SHADOW.field_count) == (7, 9)
