"""Deterministic scenarios for migrate-profile's account merge (libs/flipper-accountdb.awk).

Vocabulary, matching what migrate-profile passes to the script (migrate-profile:399-436):

* ``base``      the _stock the user's profile was created from
* ``new_base``  the newer build's copy the profile is being moved onto (dst; the script's "ours")
* ``profile``   the user's profile as it is now (src; the script's "theirs")

Every password hash below is a made-up placeholder string, not a crypt(3) hash of anything.

Each scenario states the basis of its expectation:

* ``contract`` - written down upstream (the script's header comment, migrate-profile's own checks,
  or the test a PR ships). A failure here is a regression against what upstream says it does.
* ``proposed`` - a security property this project suggests but upstream has not decided. A failure
  is a *finding* to discuss with maintainers, not a bug report.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from profileguard.accountdb import AccountDb, DbKind
from profileguard.checks import Absent, Check, LineIs, MembersAre, WellFormed

ACCOUNTDB = "libs/flipper-accountdb.awk"


class Basis(StrEnum):
    CONTRACT = "contract"
    PROPOSED = "proposed"


@dataclass(frozen=True)
class Scenario:
    id: str
    title: str
    kind: DbKind
    basis: Basis
    source: str
    story: str
    base: AccountDb
    new_base: AccountDb
    profile: AccountDb
    checks: tuple[Check, ...]
    refs: tuple[str, ...] = field(default=())


def shadow(name: str, hash_: str, lastchg: int) -> str:
    return f"{name}:{hash_}:{lastchg}:0:99999:7:::"


# Factory hashes from two builds. The image build runs `echo "user:user" | chpasswd`
# (flipperone-linux-build-scripts debian-rk3576-ospack.yaml:161-162), so each build salts anew and
# the factory record differs between any two _stock builds even though the password does not.
FACTORY_B1 = "$y$FAKE-SALT-BUILD-1$factory-placeholder"
FACTORY_B2 = "$y$FAKE-SALT-BUILD-2$factory-placeholder"
OWNER = "$y$FAKE-SALT-OWNER$owner-placeholder"

ROOT_B1 = shadow("root", "*", 20300)
ROOT_B2 = shadow("root", "*", 20350)
USER_B1 = shadow("user", FACTORY_B1, 20300)
USER_B2 = shadow("user", FACTORY_B2, 20350)
USER_OWNER = shadow("user", OWNER, 20310)
USER_LOCKED = shadow("user", "!" + FACTORY_B1, 20310)

PASSWD_ROOT = "root:x:0:0:root:/root:/bin/bash"
PASSWD_USER = "user:x:1000:1000::/home/user:/bin/bash"

HEADER = f"{ACCOUNTDB}:3-5"

SCENARIOS: tuple[Scenario, ...] = (
    Scenario(
        id="AM-01",
        title="Owner password survives a rebuilt base",
        kind=DbKind.SHADOW,
        basis=Basis.CONTRACT,
        source=f"{HEADER}: 'user-added or changed ones ride along from src'",
        story="The owner changed the factory password; the new build re-salted the factory hash. "
        "update-profile must keep the owner's password, not hand back the factory one.",
        base=AccountDb.of(ROOT_B1, USER_B1),
        new_base=AccountDb.of(ROOT_B2, USER_B2),
        profile=AccountDb.of(ROOT_B1, USER_OWNER),
        checks=(
            LineIs("user", USER_OWNER, "owner's credential"),
            LineIs("root", ROOT_B2, "untouched entry follows the new base"),
            WellFormed(),
        ),
        refs=("flipperone-linux-build-scripts#140",),
    ),
    Scenario(
        id="AM-02",
        title="Owner password survives an unchanged base",
        kind=DbKind.SHADOW,
        basis=Basis.CONTRACT,
        source=f"{HEADER}",
        story="Same as AM-01 but the new base carries the very same factory record.",
        base=AccountDb.of(ROOT_B1, USER_B1),
        new_base=AccountDb.of(ROOT_B1, USER_B1),
        profile=AccountDb.of(ROOT_B1, USER_OWNER),
        checks=(LineIs("user", USER_OWNER, "owner's credential"), WellFormed()),
    ),
    Scenario(
        id="AM-03",
        title="Never-customized account follows the new base",
        kind=DbKind.SHADOW,
        basis=Basis.CONTRACT,
        source=f"{HEADER}: 'untouched accounts follow the new base'",
        story="A profile nobody onboarded keeps the factory record, so it takes the new build's "
        "factory record. This is the documented behaviour; whether a never-onboarded profile may "
        "keep factory credentials at all is decision 4 of issue #140, still open.",
        base=AccountDb.of(ROOT_B1, USER_B1),
        new_base=AccountDb.of(ROOT_B2, USER_B2),
        profile=AccountDb.of(ROOT_B1, USER_B1),
        checks=(LineIs("user", USER_B2), WellFormed()),
        refs=("flipperone-linux-build-scripts#140",),
    ),
    Scenario(
        id="AM-04",
        title="Locked account stays locked",
        kind=DbKind.SHADOW,
        basis=Basis.CONTRACT,
        source=f"{HEADER}: locking is a change made in src",
        story="The owner ran `passwd -l user`. The lock must survive a rebuilt base.",
        base=AccountDb.of(ROOT_B1, USER_B1),
        new_base=AccountDb.of(ROOT_B2, USER_B2),
        profile=AccountDb.of(ROOT_B1, USER_LOCKED),
        checks=(LineIs("user", USER_LOCKED, "still locked"), WellFormed()),
    ),
    Scenario(
        id="AM-05",
        title="Owner-created account is carried",
        kind=DbKind.SHADOW,
        basis=Basis.CONTRACT,
        source=f"{HEADER}: 'user-added ... ride along from src'",
        story="The owner added an account 'alice'. It must exist after the update.",
        base=AccountDb.of(ROOT_B1, USER_B1),
        new_base=AccountDb.of(ROOT_B2, USER_B2),
        profile=AccountDb.of(ROOT_B1, USER_B1, shadow("alice", OWNER, 20310)),
        checks=(LineIs("alice", shadow("alice", OWNER, 20310)), WellFormed()),
    ),
    Scenario(
        id="AM-06",
        title="System account added by the new build appears",
        kind=DbKind.PASSWD,
        basis=Basis.CONTRACT,
        source=f"{HEADER}: 'untouched accounts follow the new base'",
        story="The new build adds a service account the profile never had.",
        base=AccountDb.of(PASSWD_ROOT, PASSWD_USER),
        new_base=AccountDb.of(
            PASSWD_ROOT, PASSWD_USER, "flipctl:x:999:999::/var/lib/flipctl:/usr/sbin/nologin"
        ),
        profile=AccountDb.of(PASSWD_ROOT, PASSWD_USER),
        checks=(
            LineIs("flipctl", "flipctl:x:999:999::/var/lib/flipctl:/usr/sbin/nologin"),
            WellFormed(),
        ),
    ),
    Scenario(
        id="AM-07",
        title="Membership the owner removed stays removed",
        kind=DbKind.GROUP,
        basis=Basis.CONTRACT,
        source=f"{HEADER}: 'memberships are set-merged' (3-way: a removal on either side holds)",
        story="The owner took 'user' out of the sudo group as hardening. The update must not "
        "quietly give it back.",
        base=AccountDb.of("root:x:0:", "sudo:x:27:user"),
        new_base=AccountDb.of("root:x:0:", "sudo:x:27:user"),
        profile=AccountDb.of("root:x:0:", "sudo:x:27:"),
        checks=(MembersAre("sudo", 4, frozenset(), "removal kept"), WellFormed()),
    ),
    Scenario(
        id="AM-08",
        title="Memberships added on both sides are united",
        kind=DbKind.GROUP,
        basis=Basis.CONTRACT,
        source=f"{HEADER}: 'memberships are set-merged'",
        story="The owner added 'alice' to video; the new build added 'flipctl'. Both stay.",
        base=AccountDb.of("root:x:0:", "video:x:44:user"),
        new_base=AccountDb.of("root:x:0:", "video:x:44:user,flipctl"),
        profile=AccountDb.of("root:x:0:", "video:x:44:user,alice"),
        checks=(
            MembersAre("video", 4, frozenset({"user", "flipctl", "alice"})),
            WellFormed(),
        ),
    ),
    Scenario(
        id="AM-09",
        title="gshadow administrators and members are both set-merged",
        kind=DbKind.GSHADOW,
        basis=Basis.CONTRACT,
        source=f"{HEADER}: 'LF = ... gshadow=3,4'",
        story="The owner made 'alice' a group admin and dropped 'user' as a member of netdev.",
        base=AccountDb.of("root:*::", "netdev:!::user"),
        new_base=AccountDb.of("root:*::", "netdev:!::user"),
        profile=AccountDb.of("root:*::", "netdev:!:alice:"),
        checks=(
            MembersAre("netdev", 3, frozenset({"alice"})),
            MembersAre("netdev", 4, frozenset()),
            WellFormed(),
        ),
    ),
    Scenario(
        id="AM-10",
        title="Empty base file keeps the other files in their roles",
        kind=DbKind.PASSWD,
        basis=Basis.CONTRACT,
        source=f"{ACCOUNTDB}:2 (positional roles); migrate-profile:401 passes an empty file when "
        "the base lacks the database; behaviour fixed in flipperos-btrfs-tools PR #4",
        story="With an empty base, an account identical in the new base and the profile must "
        "survive. If awk counts files by their first line, an empty file shifts every role.",
        base=AccountDb.of(),
        new_base=AccountDb.of(PASSWD_ROOT, PASSWD_USER),
        profile=AccountDb.of(PASSWD_ROOT, PASSWD_USER),
        checks=(LineIs("user", PASSWD_USER), WellFormed()),
        refs=("flipperos-btrfs-tools#4",),
    ),
    Scenario(
        id="AM-11",
        title="Account the owner deleted is not revived by a rebuilt base",
        kind=DbKind.SHADOW,
        basis=Basis.PROPOSED,
        source=f"{ACCOUNTDB}:23 returns the new base's record when the base changed it",
        story="The owner deleted the factory 'user' account. Because every build re-salts the "
        "factory hash, the new base's record differs from the old base's and the merge brings "
        "the factory shadow record back. passwd/group lines for 'user' do not change between "
        "builds, so they stay deleted and migrate-profile's check_db_pair warns about the orphan.",
        base=AccountDb.of(ROOT_B1, USER_B1),
        new_base=AccountDb.of(ROOT_B2, USER_B2),
        profile=AccountDb.of(ROOT_B1),
        checks=(Absent("user", "owner deleted it"), WellFormed()),
        refs=("flipperone-linux-build-scripts#140",),
    ),
    Scenario(
        id="AM-12",
        title="Owner password survives when the base lacks the database",
        kind=DbKind.SHADOW,
        basis=Basis.PROPOSED,
        source=f"{ACCOUNTDB}:27 'if (!ib) return Ol[k]' - with no base record the new base wins",
        story="With no base record to compare against, the merge cannot tell who changed what. "
        "Siding with the new base means a factory credential replaces the owner's. Only "
        "reachable when the old _stock lacks the file (migrate-profile:401, :220 requires the "
        "_stock itself), so this is an edge case.",
        base=AccountDb.of(),
        new_base=AccountDb.of(ROOT_B2, USER_B2),
        profile=AccountDb.of(ROOT_B1, USER_OWNER),
        checks=(LineIs("user", USER_OWNER, "owner's credential"),),
        refs=("flipperos-btrfs-tools#4",),
    ),
    Scenario(
        id="AM-13",
        title="Group password the owner set survives an unchanged base",
        kind=DbKind.GSHADOW,
        basis=Basis.PROPOSED,
        source=f"{HEADER} says changed records ride along, but mergerec ({ACCOUNTDB}:32-38) "
        "takes every non-list field from the new base",
        story="The owner set a group password on 'wheel' in gshadow; the new build did not "
        "touch that record. For group databases the merge keeps member lists from both sides "
        "but takes the other fields from the new base, so the owner's change is dropped.",
        base=AccountDb.of("root:*::", "wheel:!::user"),
        new_base=AccountDb.of("root:*::", "wheel:!::user"),
        profile=AccountDb.of("root:*::", "wheel:$y$FAKE-SALT-GROUP$group-placeholder::user"),
        checks=(LineIs("wheel", "wheel:$y$FAKE-SALT-GROUP$group-placeholder::user"),),
    ),
)


def by_id(scenario_id: str) -> Scenario:
    for s in SCENARIOS:
        if s.id == scenario_id.upper():
            return s
    raise KeyError(scenario_id)
