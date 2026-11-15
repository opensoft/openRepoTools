# SPDX-License-Identifier: Apache-2.0
"""Test R, the register's roles: each refused outside its scope (#165, L2-N4).

THE TEST PLAN'S AT-R, ITS SEVEN TESTS, on a real PostgreSQL 16 (phase N, RE: a
fake `psql` cannot enforce a GRANT). The roles are design.md §1.4's:

  * `lanes_register_owner`, which owns `lanes_register` and its functions;
  * REGISTER-WRITER, `lanes_register_writer`, and READER,
    `lanes_register_reader`: groups that cannot log in. Each engineer holds
    them through a writer login and a reader login of their own, and the dump
    job through `lanes_register_dump`, a member of READER alone;
  * the indexer's login, `lanes_indexer`, which owns `lanes_index`.

THE FIXTURE'S LOGINS are section 3.1's: `lanes-index login add fx` and `login
add --dump-job` make `lanes_w_fx`, `lanes_r_fx` and `lanes_register_dump`
once per session (T228), on the session cluster whose template the bootstrap
built (T227). The socket trusts every role, so a test connects by name with
`psql -U <login>` and no password: what is tested is authorization, not
authentication (open point 6). Each group's row of the matrix is read through
its logins, since a group cannot log in.

THE EXPECTED MATRIX is §1.4's GRANT block and its table of roles, written
below by hand, never read from the bootstrap's output, so the test does not
check the bootstrap against itself:

  * REGISTER-WRITER: SELECT on `lanes_register`'s tables and views; EXECUTE
    on `commit_write`, `switch_to_files`, `record_marker`, `find_write` (its
    six-argument form), `record_mirror_state` and `render_file`; no EXECUTE on
    the five scope functions or any other; no INSERT, UPDATE, DELETE, TRUNCATE
    or CREATE anywhere; no SELECT on a sequence; nothing in `lanes_index`;
  * READER: SELECT on both schemas' tables, views and sequences; EXECUTE on
    `render_file` only; nothing else;
  * the indexer: everything in `lanes_index`, which it owns, and nothing in
    `lanes_register`.

THE OBJECTS are read from the catalog as the superuser: each table, view and
sequence of both schemas, each function of `lanes_register`, and each schema.
The bootstrap leaves `lanes_index` empty, so the matrix's test first makes one
table there AS THE INDEXER, `t216_indexed`, with an identity column: the
reader's default privileges then have a table and a sequence to be checked
on. It lives in the test's own database.

HOW A STATEMENT IS TRIED: one `psql` session per login, with
`VERBOSITY=sqlstate` and `ON_ERROR_STOP` off. Each probe runs as
`BEGIN READ WRITE; <probe>; \\echo R <n> :SQLSTATE` and `ROLLBACK;`, so a
READER's read-only default (25006) never stands in for a refusal (42501), and
nothing a probe does survives it. An allowed probe gives `00000`, a refused
one `42501`, and nothing else passes. The probes touch no row:

  * a relation: `SELECT count(*) … WHERE false`; on a table, and on a view
    that `information_schema.views` reports insertable or updatable,
    `INSERT INTO t (c) SELECT c FROM t WHERE false`, `UPDATE t SET c = c WHERE
    false` and `DELETE FROM t WHERE false`, with `c` a column that is neither
    generated nor an identity `ALWAYS` (either fails with 428C9 before any
    privilege is checked); `TRUNCATE` on a table only, since a view or a
    sequence fails with 42809 first; so no write to `main_slots`, whose window
    function makes a write fail with 55000 first;
  * a sequence: `SELECT count(*) FROM s WHERE false` and `SELECT nextval(…)`;
  * a function: `SELECT f((SELECT NULL::<type>), …) WHERE false`. EXECUTE is
    checked when the expression is initialised, so `WHERE false` keeps an
    allowed call from running. Each argument is a sub-select, not a NULL
    constant: the planner folds a STRICT function called with a constant NULL
    to NULL, and its EXECUTE would never be checked;
  * a schema: `CREATE TABLE <schema>.t216_probe (x integer)`.

Every test here FAILS UNTIL lane 1's T107 and T109 (L1-A6, L1-A7: the schema,
the roles and their GRANTs), T110 (L1-A8: `lanes-index login`) and lane 2's
T227 and T228 (the template and the fixture's logins) land: until then a login
or a group does not exist, and each test says so by an assertion. Without
PostgreSQL 16 each skips, as `tests/pgcluster.py` says.
"""

from __future__ import annotations

import re
import time
from typing import List, Sequence, Tuple

import pytest

from pgcluster import SUPERUSER

#: THE LANDING GATE'S TABLE (T280's `SQL_REGISTER_GATE_TABLE`; task sets
#: version 12b's rule 11, lane 3, opensoft/openRepoTools#165 6877673742):
#: the 007 tasks each id waits for. T216's Order (tasks:2028 at `204145ae`)
#: says "Its tests fail until L1-A6, L1-A7, L1-A8 and T228 land": L1-A6 is
#: T107 and T108, L1-A7 is T109 and L1-A8 is T110, so every id shares one
#: row. The table is lane 2's GP-24 plan's (`GP-24-gate-tables-plan.md`,
#: sha256 `16d738b9`). Only where the gate is active
#: (`tests/sql_register_gate.py`) does it skip an id until all its tasks
#: have landed; elsewhere it changes nothing.
SQL_REGISTER_GATE_TABLE = {
    "*": ("T107", "T108", "T109", "T110", "T228"),  # every id: the tasks all its rows share
}

#: The register's schema and #160's, as §1.4 names them.
REGISTER, INDEX = "lanes_register", "lanes_index"

#: §1.4's roles: the owner, the two groups and the indexer's login.
OWNER = "lanes_register_owner"
WRITER_GROUP = "lanes_register_writer"
READER_GROUP = "lanes_register_reader"
INDEXER = "lanes_indexer"
BOOTSTRAP_ROLES = (OWNER, WRITER_GROUP, READER_GROUP, INDEXER)

#: Section 3.1's logins, by the ids the test plan gives each one.
LOGINS = {"writer-login": "lanes_w_fx", "reader-login": "lanes_r_fx",
          "dump-login": "lanes_register_dump", "indexer": INDEXER}
FIXTURE_LOGINS = ("lanes_w_fx", "lanes_r_fx", "lanes_register_dump")

#: The group each login holds, as §1.4's login step grants it.
GROUP_OF = {"writer-login": WRITER_GROUP, "reader-login": READER_GROUP,
            "dump-login": READER_GROUP}

#: §1.4's GRANT EXECUTEs, by exact signature, the argument types as
#: `format_type` prints them: a grant left on an older signature fails.
WRITER_EXECUTES = frozenset({
    "commit_write(bigint,uuid,integer,uuid,jsonb)",
    "switch_to_files(integer,bigint,text,text)",
    "record_marker(integer,bigint,text,text)",
    "find_write(uuid,timestamp with time zone,uuid,text,text,text)",
    "record_mirror_state(text,text,text)",
    "render_file(text)",
})
READER_EXECUTES = frozenset({"render_file(text)"})

#: The five scope functions no role may execute (AT-R's objects).
SCOPE_FUNCTIONS = frozenset({
    "line_scopes(text,text)",
    "doc_line_scopes(bigint,text)",
    "entry_new_keys(bigint)",
    "scope_fault(text)",
    "scope_checked(text,integer,text)",
})

#: The tables AT-R names among the objects: the journal and the switch row.
NAMED_TABLES = ("journal", "register_switch", "register_head")

#: The floors of §1.4's login step (D9), each login's own `rolconfig`, and the
#: same values as `pg_settings` gives them in their base units.
WRITER_FLOORS = {"lock_timeout": "2000ms", "statement_timeout": "5s",
                 "idle_in_transaction_session_timeout": "5s"}
READER_FLOORS = {"default_transaction_read_only": "on", "lock_timeout": "1000ms",
                 "statement_timeout": "1500ms"}
FLOORS = {"writer-login": WRITER_FLOORS, "reader-login": READER_FLOORS,
          "dump-login": READER_FLOORS}
BASE_UNITS = {"2000ms": "2000", "1000ms": "1000", "1500ms": "1500", "5s": "5000", "on": "on"}

#: The table the matrix's test makes in `lanes_index`, as the indexer.
INDEXED = "t216_indexed"

OK, DENIED, READ_ONLY = "00000", "42501", "25006"

#: The session's settings: no stop on an error, the SQLSTATE alone, and every
#: result row thrown away (`\echo` still writes to stdout).
PREAMBLE = "\\set ON_ERROR_STOP 0\n\\set VERBOSITY sqlstate\n\\o /dev/null\n"

RESULT_LINE = re.compile(r"^R (\d+) (\S+)$", re.M)


# ------------------------------------------------------------ helpers
def ident(name: str) -> str:
    """A name as SQL quotes it."""
    return '"' + name.replace('"', '""') + '"'


def rows(db, sql: str) -> List[List[str]]:
    """The superuser's answer to `sql`, one list of `|`-separated fields per row."""
    out = db.psql(sql).stdout
    return [line.split("|") for line in out.splitlines() if line]


def require_roles(db, *roles: str) -> None:
    """Fail, by an assertion, where a role the test reads does not exist yet."""
    present = {r[0] for r in rows(db, "SELECT rolname FROM pg_roles;")}
    missing = [r for r in roles if r not in present]
    assert not missing, (
        f"no role {', '.join(missing)} on this cluster: the bootstrap's roles come from lane 1's "
        f"T109 through lane 2's T227, and the fixture's logins from T110's `login add` through T228")


def tried(db, user: str, probes: Sequence[str], *, bare: Sequence[str] = ()) -> Tuple[List[str], List[str], str]:
    """Run `probes` as `user`, one session, each in `BEGIN READ WRITE … ROLLBACK`,
    then `bare`, each on its own after `SET default_transaction_read_only = off`.
    Returns the SQLSTATE of each, in order, and psql's stderr."""
    script = [PREAMBLE]
    for n, probe in enumerate(probes):
        script.append(f"BEGIN READ WRITE;\n{probe};\n\\echo R {n} :SQLSTATE\nROLLBACK;\n")
    if bare:
        script.append("SET default_transaction_read_only = off;\n")
    for n, statement in enumerate(bare, start=len(probes)):
        script.append(f"{statement};\n\\echo R {n} :SQLSTATE\n")
    proc = db.psql("".join(script), user=user, check=False)
    assert proc.returncode == 0, (
        f"psql as {user} exited {proc.returncode}, so the login could not run its session "
        f"(it is made by T228, through lane 1's T110): {proc.stderr.strip()[-600:]}")
    said = {int(n): state for n, state in RESULT_LINE.findall(proc.stdout)}
    assert sorted(said) == list(range(len(probes) + len(bare))), (
        f"the session as {user} reported {len(said)} of {len(probes) + len(bare)} statements: "
        f"{proc.stderr.strip()[-600:]}")
    states = [said[n] for n in range(len(probes) + len(bare))]
    return states[:len(probes)], states[len(probes):], proc.stderr


def can_connect(cluster, dbname: str, user: str):
    """`SELECT current_user` as `user` on `dbname`: the completed psql."""
    return cluster.psql("SELECT current_user;", dbname=dbname, user=user, check=False)


# ------------------------------------------------------------ the catalog
RELATIONS_SQL = f"""
SELECT n.nspname, c.relname, c.relkind,
       coalesce((SELECT a.attname FROM pg_attribute a
                  WHERE a.attrelid = c.oid AND a.attnum > 0 AND NOT a.attisdropped
                    AND a.attgenerated = '' AND a.attidentity <> 'a'
                    AND (c.relkind <> 'v' OR EXISTS (
                         SELECT 1 FROM information_schema.columns ic
                          WHERE ic.table_schema = n.nspname AND ic.table_name = c.relname
                            AND ic.column_name = a.attname AND ic.is_updatable = 'YES'))
                  ORDER BY a.attnum LIMIT 1), ''),
       coalesce((SELECT v.is_insertable_into FROM information_schema.views v
                  WHERE v.table_schema = n.nspname AND v.table_name = c.relname), ''),
       coalesce((SELECT v.is_updatable FROM information_schema.views v
                  WHERE v.table_schema = n.nspname AND v.table_name = c.relname), '')
  FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE n.nspname IN ('{REGISTER}', '{INDEX}') AND c.relkind IN ('r', 'p', 'v', 'S')
 ORDER BY 1, 2;
"""

FUNCTIONS_SQL = f"""
SELECT p.proname,
       coalesce((SELECT string_agg(format_type(t.typ, NULL), ';' ORDER BY t.ord)
                   FROM unnest(p.proargtypes::oid[]) WITH ORDINALITY AS t(typ, ord)), '')
  FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
 WHERE n.nspname = '{REGISTER}' AND p.prokind = 'f'
 ORDER BY 1, 2;
"""


class Probe:
    """One statement of the matrix: what it tries, on which object."""

    def __init__(self, schema: str, kind: str, name: str, privilege: str, sql: str) -> None:
        self.schema, self.kind, self.name, self.privilege, self.sql = schema, kind, name, privilege, sql

    def label(self) -> str:
        return f"{self.privilege} on {self.kind} {self.schema}.{self.name}"


def signature(name: str, types: str) -> str:
    return f"{name}({types.replace(';', ',')})"


def matrix_probes(db) -> List[Probe]:
    """Every role × object × privilege the plan names, from the catalog."""
    probes: List[Probe] = []
    for schema, rel, kind, column, insertable, updatable in rows(db, RELATIONS_SQL):
        q = f"{ident(schema)}.{ident(rel)}"
        if kind == "S":
            probes.append(Probe(schema, "sequence", rel, "SELECT", f"SELECT count(*) FROM {q} WHERE false"))
            probes.append(Probe(schema, "sequence", rel, "nextval",
                                f"SELECT nextval({_literal(schema + '.' + rel)}::regclass)"))
            continue
        what = "view" if kind == "v" else "table"
        probes.append(Probe(schema, what, rel, "SELECT", f"SELECT count(*) FROM {q} WHERE false"))
        writable = kind != "v" or "YES" in (insertable, updatable)
        if not writable:
            continue
        assert column, f"{schema}.{rel} has no column a probe can write without 428C9"
        c = ident(column)
        if kind != "v" or insertable == "YES":
            probes.append(Probe(schema, what, rel, "INSERT",
                                f"INSERT INTO {q} ({c}) SELECT {c} FROM {q} WHERE false"))
        if kind != "v" or updatable == "YES":
            probes.append(Probe(schema, what, rel, "UPDATE", f"UPDATE {q} SET {c} = {c} WHERE false"))
            probes.append(Probe(schema, what, rel, "DELETE", f"DELETE FROM {q} WHERE false"))
        if kind != "v":
            probes.append(Probe(schema, what, rel, "TRUNCATE", f"TRUNCATE {q}"))
    for name, types in rows(db, FUNCTIONS_SQL):
        args = ", ".join(f"(SELECT NULL::{t})" for t in types.split(";") if t)
        probes.append(Probe(REGISTER, "function", signature(name, types), "EXECUTE",
                            f"SELECT {ident(REGISTER)}.{ident(name)}({args}) WHERE false"))
    for schema in (REGISTER, INDEX):
        probes.append(Probe(schema, "schema", schema, "CREATE",
                            f"CREATE TABLE {ident(schema)}.t216_probe (x integer)"))
    return probes


def _literal(text: str) -> str:
    return "'" + text.replace("'", "''") + "'"


def expected(role: str, probe: Probe) -> str:
    """§1.4's answer for `role` (an id of `LOGINS`) and `probe`: OK or DENIED."""
    if role == "indexer":
        return OK if probe.schema == INDEX else DENIED
    if probe.schema == INDEX:
        if role == "writer-login":
            return DENIED
        return OK if probe.privilege == "SELECT" else DENIED
    if probe.kind == "function":
        granted = WRITER_EXECUTES if role == "writer-login" else READER_EXECUTES
        return OK if probe.name in granted else DENIED
    if probe.privilege == "SELECT":
        if probe.kind == "sequence":
            return DENIED if role == "writer-login" else OK
        return OK
    return DENIED


def make_indexed_table(db) -> None:
    """`lanes_index.t216_indexed`, made by the indexer in the test's own database."""
    db.psql(f"SET ROLE {INDEXER};\n"
            f"CREATE TABLE {INDEX}.{INDEXED} (id bigint GENERATED BY DEFAULT AS IDENTITY "
            f"PRIMARY KEY, note text);\n")


#: What a session must not change: the ACLs of both schemas' objects, the
#: schemas and this database, the default privileges, every membership and
#: every role's flags. Read as the superuser before and after.
FINGERPRINT_SQL = f"""
SELECT concat_ws(E'\\n',
  (SELECT string_agg(format('%s.%s %s', n.nspname, c.relname, c.relacl), ' ' ORDER BY n.nspname, c.relname)
     FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname IN ('{REGISTER}', '{INDEX}')),
  (SELECT string_agg(format('%s %s', p.oid::regprocedure, p.proacl), ' ' ORDER BY p.oid::regprocedure::text)
     FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
    WHERE n.nspname IN ('{REGISTER}', '{INDEX}')),
  (SELECT string_agg(format('%s %s %s', nspname, nspowner::regrole, nspacl), ' ' ORDER BY nspname)
     FROM pg_namespace),
  (SELECT format('%s %s', datname, datacl) FROM pg_database WHERE datname = current_database()),
  (SELECT string_agg(format('%s %s %s %s', defaclrole::regrole, defaclnamespace, defaclobjtype, defaclacl),
                     ' ' ORDER BY defaclrole::regrole::text, defaclnamespace, defaclobjtype)
     FROM pg_default_acl),
  (SELECT string_agg(format('%s>%s by %s %s %s %s', roleid::regrole, member::regrole, grantor::regrole,
                            admin_option, inherit_option, set_option),
                     ' ' ORDER BY roleid::regrole::text, member::regrole::text, grantor::regrole::text)
     FROM pg_auth_members),
  (SELECT string_agg(format('%s %s %s %s %s %s %s %s', rolname, rolsuper, rolinherit, rolcreaterole,
                            rolcreatedb, rolcanlogin, rolreplication, rolbypassrls), ' ' ORDER BY rolname)
     FROM pg_roles));
"""


def fingerprint(db) -> str:
    return db.psql(FINGERPRINT_SQL).stdout


# ------------------------------------------------------------ AT-R
@pytest.mark.parametrize("role", list(LOGINS))
def test_each_role_is_refused_outside_its_scope(pg, role):
    """One session per login checks its group's whole row of §1.4's matrix:
    each allowed statement gives 00000, each refused one 42501, and nothing
    else passes."""
    require_roles(pg, *BOOTSTRAP_ROLES, *FIXTURE_LOGINS)
    make_indexed_table(pg)
    probes = matrix_probes(pg)
    functions = {p.name for p in probes if p.kind == "function"}
    missing = sorted((WRITER_EXECUTES | SCOPE_FUNCTIONS) - functions)
    assert not missing, f"{REGISTER} holds no function {', '.join(missing)} (lane 1's T107)"
    tables = {p.name for p in probes if p.schema == REGISTER and p.kind == "table"}
    assert set(NAMED_TABLES) <= tables, f"{REGISTER} lacks {sorted(set(NAMED_TABLES) - tables)}"
    assert any(p.schema == INDEX and p.kind == "sequence" for p in probes), \
        f"{INDEX}.{INDEXED} has no identity sequence to check"
    assert not any(p.kind == "view" and p.name == "main_slots" and p.privilege != "SELECT"
                   for p in probes), "main_slots is reported updatable, which §1.4's window forbids"

    login = LOGINS[role]
    states, _, _ = tried(pg, login, [p.sql for p in probes])
    wrong = [f"{p.label()}: {state}, expected {expected(role, p)}"
             for p, state in zip(probes, states) if state != expected(role, p)]
    assert not wrong, f"{login} ({role}), {len(wrong)} of {len(probes)} wrong:\n  " + "\n  ".join(wrong)


#: What each login tries in its own session, each refused 42501.
ESCALATIONS = (
    "CREATE ROLE t216_made",
    "CREATE SCHEMA t216_made",
    f"GRANT {WRITER_GROUP} TO lanes_register_dump",
    f"GRANT {OWNER} TO CURRENT_USER",
    f"SET ROLE {SUPERUSER}",
    f"SET ROLE {OWNER}",
    f"SET SESSION AUTHORIZATION {SUPERUSER}",
    "ALTER ROLE CURRENT_USER SUPERUSER",
    "ALTER ROLE CURRENT_USER CREATEROLE",
    "ALTER ROLE CURRENT_USER CREATEDB",
)

#: Object GRANTs only warn (01007) where the grantor lacks the grant option,
#: so their oracle is the fingerprint, unchanged after the session.
OBJECT_GRANTS = (
    f"GRANT ALL ON ALL TABLES IN SCHEMA {REGISTER} TO PUBLIC",
    f"GRANT ALL ON ALL SEQUENCES IN SCHEMA {REGISTER} TO PUBLIC",
    f"GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA {REGISTER} TO PUBLIC",
    f"GRANT USAGE, CREATE ON SCHEMA {REGISTER} TO PUBLIC",
    f"GRANT ALL ON DATABASE {{db}} TO PUBLIC",
)


@pytest.mark.parametrize("role", list(LOGINS))
def test_no_register_role_can_grant_create_or_act_as_superuser(pg, role):
    """`pg_roles` gives the login, the owner and the two groups no SUPERUSER,
    CREATEROLE or CREATEDB; in the login's own session each escalation is
    refused 42501, `CREATE DATABASE` too, and its object GRANTs change no
    ACL, membership or flag."""
    login = LOGINS[role]
    require_roles(pg, *BOOTSTRAP_ROLES, login)
    flags = {r[0]: r[1:] for r in rows(pg, (
        "SELECT rolname, rolsuper, rolcreaterole, rolcreatedb, rolcanlogin FROM pg_roles "
        f"WHERE rolname IN ({', '.join(_literal(n) for n in (login, *BOOTSTRAP_ROLES))});"))}
    for name, (superuser, createrole, createdb, canlogin) in sorted(flags.items()):
        assert (superuser, createrole, createdb) == ("f", "f", "f"), \
            f"{name}: rolsuper {superuser}, rolcreaterole {createrole}, rolcreatedb {createdb}"
        logs_in = name in (login, INDEXER)
        assert canlogin == ("t" if logs_in else "f"), f"{name}: rolcanlogin {canlogin}"

    made_db = f"t216_made_by_{login}"
    before = fingerprint(pg)
    try:
        states, bare, _ = tried(pg, login, ESCALATIONS,
                                bare=(f"CREATE DATABASE {made_db}",
                                      *(g.format(db=ident(pg.name)) for g in OBJECT_GRANTS)))
        exists = rows(pg, f"SELECT count(*) FROM pg_database WHERE datname = {_literal(made_db)};")
    finally:
        pg.psql(f"DROP DATABASE IF EXISTS {made_db} WITH (FORCE);")
    after = fingerprint(pg)

    wrong = [f"{s}: {state}" for s, state in zip(ESCALATIONS, states) if state != DENIED]
    assert not wrong, f"{login} was not refused 42501:\n  " + "\n  ".join(wrong)
    assert bare[0] == DENIED and exists == [["0"]], f"{login}'s CREATE DATABASE gave {bare[0]}"
    assert all(state in (OK, DENIED) for state in bare[1:]), f"{login}'s object GRANTs gave {bare[1:]}"
    assert after == before, f"{login}'s session changed an ACL, a membership or a role's flags"


@pytest.mark.parametrize("group", ["writer", "reader"])
def test_the_writer_and_reader_groups_cannot_log_in(pg, group):
    """A connection as either group is refused, FATAL 28000, and its
    `rolcanlogin` is false."""
    name = {"writer": WRITER_GROUP, "reader": READER_GROUP}[group]
    require_roles(pg, name)
    assert rows(pg, f"SELECT rolcanlogin FROM pg_roles WHERE rolname = {_literal(name)};") == [["f"]]
    proc = can_connect(pg.cluster, pg.name, name)
    assert proc.returncode == 2, f"psql as {name} exited {proc.returncode}: {proc.stdout!r}"
    assert f'role "{name}" is not permitted to log in' in proc.stderr, proc.stderr


@pytest.mark.parametrize("role", ["writer-login", "reader-login", "dump-login"])
def test_a_login_in_a_group_role_keeps_the_floors_of_its_role(pg, role):
    """The login's own `rolconfig` holds its group's floors exactly, its own
    session's `pg_settings` gives them from the role (`source` `user`), and
    the two groups, the owner and the indexer carry none, since a role's
    settings reach no member."""
    login, floors = LOGINS[role], FLOORS[role]
    require_roles(pg, *BOOTSTRAP_ROLES, login)
    config = rows(pg, f"SELECT unnest(rolconfig) FROM pg_roles WHERE rolname = {_literal(login)};")
    assert sorted(c[0] for c in config) == sorted(f"{k}={v}" for k, v in floors.items()), config
    bare = rows(pg, "SELECT rolname FROM pg_roles WHERE rolconfig IS NOT NULL AND rolname IN "
                    f"({', '.join(_literal(n) for n in BOOTSTRAP_ROLES)});")
    assert bare == [], f"{bare} carry settings, which reach no member"

    names = ", ".join(_literal(k) for k in floors)
    proc = pg.psql(f"SELECT name, setting, source FROM pg_settings WHERE name IN ({names}) ORDER BY 1;",
                   user=login, check=False)
    assert proc.returncode == 0, f"psql as {login} exited {proc.returncode}: {proc.stderr.strip()}"
    seen = [line.split("|") for line in proc.stdout.splitlines() if line]
    assert seen == [[k, BASE_UNITS[v], "user"] for k, v in sorted(floors.items())], seen


def test_the_bootstrap_holds_no_admin_session_once_it_exits(stoppable_cluster):
    """The admin is the one member of the owner, holding it and the indexer
    WITH INHERIT TRUE, SET TRUE (§1.4); no client session of it is left
    besides the test's own; and the cluster holds no role the bootstrap and
    the login step did not make.

    On a cluster of the test's own, whose template is bootstrapped and given
    the fixture's logins as every cluster's is (T227, T228): roles are
    cluster-wide, and on the session cluster other modules' cases leave
    logins of their own (render's `ensure_logins` makes
    `t210_register_reader` and `t210_register_writer`), so the role count
    there depends on which cases ran before this one."""
    own = stoppable_cluster
    require_roles(own, *BOOTSTRAP_ROLES, *FIXTURE_LOGINS)
    members = rows(own, (
        "SELECT DISTINCT member::regrole::text FROM pg_auth_members "
        f"WHERE roleid = {_literal(OWNER)}::regrole;"))
    assert len(members) == 1, f"{OWNER}'s members are {members}: §1.4 grants it to the admin alone"
    admin = members[0][0]
    for role in (OWNER, INDEXER):
        held = rows(own, (
            "SELECT count(*) FROM pg_auth_members "
            f"WHERE roleid = {_literal(role)}::regrole AND member = {_literal(admin)}::regrole "
            "AND inherit_option AND set_option;"))
        assert int(held[0][0]) >= 1, f"{admin} holds {role} without INHERIT TRUE, SET TRUE"

    end = time.monotonic() + 3.0
    while True:
        left = rows(own, (
            "SELECT pid, application_name FROM pg_stat_activity "
            f"WHERE usename = {_literal(admin)} AND backend_type = 'client backend' "
            "AND pid <> pg_backend_pid();"))
        if not left or time.monotonic() > end:
            break
        time.sleep(0.1)
    assert left == [], f"{admin} still holds sessions after the bootstrap exited: {left}"

    others = {r[0] for r in rows(own, (
        "SELECT rolname FROM pg_roles WHERE rolname !~ '^pg_' AND oid <> 10 "
        f"AND rolname <> {_literal(admin)};"))}
    assert others == set(BOOTSTRAP_ROLES) | set(FIXTURE_LOGINS), \
        f"roles beyond the bootstrap's and the login step's: {sorted(others)}"


def test_a_readers_plain_write_fails_25006_and_a_read_write_one_42501(pg):
    """The READER's role default is read-only, so its plain INSERT fails 25006
    before any privilege is checked, and the same INSERT in `BEGIN READ
    WRITE` fails 42501: for the fixture's reader login and the dump job's."""
    require_roles(pg, *BOOTSTRAP_ROLES, "lanes_r_fx", "lanes_register_dump")
    insert = (f"INSERT INTO {REGISTER}.register_head (seq) "
              f"SELECT seq FROM {REGISTER}.register_head WHERE false")
    for login in ("lanes_r_fx", "lanes_register_dump"):
        proc = pg.psql(f"{PREAMBLE}{insert};\n\\echo R 0 :SQLSTATE\n"
                       f"BEGIN READ WRITE;\n{insert};\n\\echo R 1 :SQLSTATE\nROLLBACK;\n",
                       user=login, check=False)
        assert proc.returncode == 0, f"psql as {login} exited {proc.returncode}: {proc.stderr.strip()}"
        said = dict(RESULT_LINE.findall(proc.stdout))
        assert said == {"0": READ_ONLY, "1": DENIED}, f"{login}: {said}, {proc.stderr.strip()}"


def test_each_login_role_connects_only_where_granted_connect(pg, stoppable_cluster):
    """Each login connects to the test's database. On a cluster of the
    test's own, bootstrapped there, a reader login made in READER connects to
    a database granted §1.4's CONNECT and is refused 42501 on one whose
    CONNECT is revoked from PUBLIC and from READER. No role changes on the
    session cluster."""
    require_roles(pg, *BOOTSTRAP_ROLES, *FIXTURE_LOGINS)
    for login in (*FIXTURE_LOGINS, INDEXER):
        proc = can_connect(pg.cluster, pg.name, login)
        assert (proc.returncode, proc.stdout.strip()) == (0, login), \
            f"{login} on {pg.name}: exit {proc.returncode}, {proc.stderr.strip()}"

    own = stoppable_cluster
    present = {line for line in own.psql("SELECT rolname FROM pg_roles;").stdout.split()}
    assert READER_GROUP in present, \
        f"no {READER_GROUP} on the test's own cluster: its template is bootstrapped by T227"
    granted = own.new_database()
    own.psql(f"REVOKE ALL ON DATABASE {granted} FROM PUBLIC;\n"
             f"GRANT CONNECT ON DATABASE {granted} TO {WRITER_GROUP}, {READER_GROUP}, {INDEXER};\n")
    reader = "lanes_r_t216"
    own.psql(f"CREATE ROLE {reader} LOGIN;\nGRANT {READER_GROUP} TO {reader};\n")
    revoked = "t216_no_connect"
    own.psql(f"CREATE DATABASE {revoked};")
    before = own.psql(f"SELECT has_database_privilege({_literal(reader)}, {_literal(revoked)}, 'CONNECT');")
    assert before.stdout.strip() == "t", f"a new database refuses CONNECT before any REVOKE: {before.stdout!r}"
    own.psql(f"REVOKE CONNECT ON DATABASE {revoked} FROM PUBLIC;\n"
             f"REVOKE CONNECT ON DATABASE {revoked} FROM {READER_GROUP};\n")

    there = can_connect(own, granted, reader)
    assert (there.returncode, there.stdout.strip()) == (0, reader), \
        f"{reader} on {granted}: exit {there.returncode}, {there.stderr.strip()}"
    refused = can_connect(own, revoked, reader)
    assert refused.returncode == 2, f"{reader} on {revoked}: exit {refused.returncode}"
    assert f'permission denied for database "{revoked}"' in refused.stderr, refused.stderr
