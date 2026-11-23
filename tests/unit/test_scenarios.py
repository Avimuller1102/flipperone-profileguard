import re

from profileguard.scenarios import SCENARIOS, Basis, by_id

FAKE = re.compile(r"\$y\$FAKE-[A-Z0-9-]+\$[a-z-]+placeholder")


def test_ids_unique_and_lookup_case_insensitive() -> None:
    ids = [s.id for s in SCENARIOS]
    assert len(ids) == len(set(ids))
    assert by_id("am-01").id == "AM-01"


def test_every_scenario_states_a_basis_and_has_checks() -> None:
    for s in SCENARIOS:
        assert s.source and s.story and s.checks
        assert s.basis in (Basis.CONTRACT, Basis.PROPOSED)


def test_inputs_hold_only_placeholder_hashes() -> None:
    """No scenario may carry anything that looks like a real crypt(3) hash."""
    for s in SCENARIOS:
        for line in (*s.base.lines, *s.new_base.lines, *s.profile.lines):
            field = line.split(":")[1] if ":" in line else ""
            if field.startswith(("$", "!$")):
                assert FAKE.fullmatch(field.lstrip("!")), (s.id, line)


def test_records_have_the_field_count_migrate_profile_requires() -> None:
    for s in SCENARIOS:
        for line in (*s.base.lines, *s.new_base.lines, *s.profile.lines):
            assert len(line.split(":")) == s.kind.field_count, (s.id, line)
