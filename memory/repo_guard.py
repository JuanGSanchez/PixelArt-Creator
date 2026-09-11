#!/usr/bin/env python3
"""The one line the container's tooling may not cross.

A container repository IS the orchestration system: its scripts, its gates,
its store, its `design-docs/`. A product repository is a different thing with
a different owner — it carries its OWN orchestration furniture, installed and
maintained by its OWN system — and the container's Mode D has no authority
inside it.

WHAT THIS WAS WRITTEN FOR, AND WHAT IT COST TO LEARN IT. `redistribute.py
apply` already refused a product target and said so in its named exit. The
verbs it would have called did not: `container_repo.py install-hooks
--profile repository`, `memory_views.py install`, `coverage_views.py install`
and the memory engine's writing verbs classified nothing and wrote wherever
they were pointed. So a redistribution that hit `apply`'s refusal was
finished BY HAND from inside the container's session, verb by verb, against
the product — and the two commits it left in that product repository are the
whole reason this file exists. The prohibition was real, it was written down,
and it was reachable by anyone who read the refusal as a routing hint rather
than as a boundary.

A rule only a person can keep is a rule with an exception in it. So:

  * the boundary is asked programmatically, by every verb that WRITES;
  * a refusal is exit 2 with the command that IS legitimate;
  * the product's own tooling may still act on the product, and says so out
    loud with `--repository-self`;
  * `redistribute.py` never passes that flag, and marks its own child
    processes so one cannot be made to pass it either.

THE THIRD QUESTION. `guard()` asks "is this a product?"; `--repository-self`
answers "yes, and I am its own system, let me write"; nothing asked "yes —
but not onto its `main`". So every one of those verbs could be aimed at a
product's `main` worktree and its output committed there, and the product's
own generated gate admitted the commit (measured in PixelArt-Creator: 33
commits reached `main` that way). `protected_branch()` asks the third
question — a PRODUCT repository, on `main`/`master`, with a HEAD commit —
and `refuse_protected_branch()` is the named exit. It is evaluated AFTER
`enforce()`, never folded into it: folding it in would make `--repository-self`
an answer to it too, which is exactly the bypass being closed.

WHAT THIS IS NOT. It is not the five-way `classify_target` in
`redistribute.py`, which answers "what should this target do next" for a Mode
D verb. This answers one question — *is this a product repository, or inside
one* — because that is the only question a write gate has, and two
implementations of one boundary is two places for it to drift.

Usage
    py repo_guard.py check <path> [--repository-self]

`check` also reports `protected_branch`: the branch a write would land on
when the third question refuses, or null.
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

# The environment variable a Mode D run sets on every child it spawns. It is
# not a way IN — nothing reads it to grant permission. It is a way of making
# sure a child cannot be handed `--repository-self` and believed: while this is
# set, the override is refused no matter who asks.
DELEGATION_MARKER = "WORKSPACE_DELEGATED_RUN"   # 4.0.0: was ORCHESTRATOR_DESIGN_MODE_D

STORE_MARKER = "store.json"
LEGACY_STORE_MARKER = "store-role.json"
WORKSPACE_SCOPE = "workspace"
REPOSITORY_SCOPE = "repository"
# Retired names, kept for one release so every caller still resolves.
CONTAINER_ROLE = WORKSPACE_SCOPE
PRODUCT_ROLE = REPOSITORY_SCOPE
# Mirrored here rather than imported: this module is vendored into every
# store and must answer with no sibling present.
_LEGACY_SCOPE_OF = {"container": WORKSPACE_SCOPE, "product": REPOSITORY_SCOPE}

EXIT_REFUSED = 2


class ProductBoundary(Exception):
    """A write was aimed at a product repository. Carries the named exit."""

    def __init__(self, verdict):
        self.verdict = verdict
        super().__init__(verdict["error"])


def _marker_value(store, name, key):
    marker = Path(store) / name
    if not marker.is_file():
        return None
    try:
        data = json.loads(marker.read_text(encoding="utf-8", errors="replace"))
    except (ValueError, OSError):
        return None
    value = data.get(key) if isinstance(data, dict) else None
    return value if isinstance(value, str) else None


def store_scope(store):
    """The scope a store's own marker declares, or None.

    Same two-state reading `container_repo.py` and `redistribute.py` use: a
    store with no marker has no scope, and NOBODY guesses one for it. Both
    spellings are read — `store.json` / `scope` first, then the retired
    `store-role.json` / `role` with its values mapped — because the day the
    marker was renamed with only ONE reader updated, every store answered
    "no scope" and this boundary refused nothing while reporting COMPLETED.
    """
    scope = _marker_value(store, STORE_MARKER, "scope")
    if scope in (WORKSPACE_SCOPE, REPOSITORY_SCOPE):
        return scope
    return _LEGACY_SCOPE_OF.get(_marker_value(store, LEGACY_STORE_MARKER, "role"))


store_role = store_scope   # retired alias, kept for one release


def enclosing_container(path):
    """The container repository `path` sits inside, or None.

    A repository inside a container is a product of that container whatever
    its own store says — including when it has no store at all, which is the
    state a product is in before anything has been installed for it, and
    precisely the state in which a container's tooling is most tempted to
    reach in.

    THE MARKER ALONE, since 4.0.0. The test used to be a `design-docs/`
    directory AND a workspace-scoped store, and the directory is the half
    that had to go for two reasons that point the same way. This module is
    VENDORED into every store — the ones inside a product repository
    included — and a vendored file that names the container's own layout is
    exactly what `check_product_purity` forbids a product to carry: the
    furniture exemption is what keeps that quiet today, and it is removed in
    a later minor (`redistribution.md`, the divergence review). And a marker
    is a DECLARATION while a directory name is a convention: `store.json`
    says what this tree is, and anybody can create a folder called
    `design-docs`.

    The price is stated rather than hidden: a container built before 4.0.0
    that never ran the migration carries no store marker, so it no longer
    shields the repositories inside it. That tree is a `legacy-workspace`
    the audit names and `apply` offers to migrate — a state somebody is told
    about — where the old reading made it a shield that worked by accident.
    """
    path = Path(path).resolve()
    for parent in path.parents:
        if store_scope(parent / "memory") == WORKSPACE_SCOPE:
            return parent
    return None


def repository_root(path):
    """The nearest ancestor (or `path` itself) holding a `.git`, or None.

    Read off the filesystem, never by running git: this is a guard on the
    write path of every viewer and every installer, and it must give the same
    answer where git is absent, where it is a stub, and where it hangs.
    """
    path = Path(path).resolve()
    for candidate in (path,) + tuple(path.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


# --------------------------------------------------------------------------
# where a product root is
# --------------------------------------------------------------------------
#
# ONE resolver, here rather than in the structure gate, for the reason this
# module exists at all: it is the STDLIB file vendored into every store, so
# a hook, an installer, a builder and a migration all reach it with nothing
# else beside them. Before 4.0.0 the descent was re-derived at each of those
# sites and each site got it wrong differently.
#
# `codebase/` is the tier's one home (project-structure.md invariant 11a).
# The two retired shapes are still ANSWERED, tagged `legacy`: the migration
# has to find a root before it can move it, and a container that never
# migrated must not read as conforming.

CODEBASE_DIR = "codebase"
PRODUCT_ROOT_LEAF = "main"
# Container furniture: never a product, never a grouping directory, and
# walking into it finds a `.git` that belongs to something else (the
# container's own worktrees live under `design-docs/worktrees/`).
FURNITURE_DIRS = frozenset((
    ".claude", ".git", ".githooks", "design-docs", "memory", "scripts",
    "testing", "node_modules", "__pycache__", ".venv", "venv",
))


def _is_repo_folder(path):
    """A repository home or one of its branch worktrees: `.git` as a
    directory (the home) or as a file (git's own worktree pointer)."""
    return path.is_dir() and (path / ".git").exists()


def product_root(container, name=None):
    """WHERE the product root of `container` is — the one resolver.

    `name` is the PRODUCT (flat, as `codebase/` names it) or None for a
    single-product container. Returns

        {"container", "name", "root", "branch", "layout", "exists"}

    `layout` is `codebase` for the 4.0.0 tier and `legacy` for the shapes it
    replaced, and it is not decoration: a caller that writes into a legacy
    root without saying so is a caller that has silently declined to migrate.

        codebase   <container>/codebase/main/          (name None)
                   <container>/codebase/<name>/main/
        legacy     <container>/main/                   (name None)
                   <container>/<group>/<name>/main/    (name <group>-<name>)

    A legacy answer is given only for a root that is ON DISK. When neither
    shape is there the canonical path is returned with `exists` False —
    that is the answer a builder needs, and re-deriving it at the build site
    is exactly how the two halves drift apart.
    """
    container = Path(container).resolve()
    canonical = container / CODEBASE_DIR
    if name:
        canonical = canonical / name
    canonical = canonical / PRODUCT_ROOT_LEAF
    if _is_repo_folder(canonical):
        return {"container": str(container), "name": name,
                "root": str(canonical), "branch": PRODUCT_ROOT_LEAF,
                "layout": "codebase", "exists": True}
    for entry in legacy_product_roots(container):
        if entry["name"] == name:
            return entry
    return {"container": str(container), "name": name,
            "root": str(canonical), "branch": PRODUCT_ROOT_LEAF,
            "layout": "codebase", "exists": False}


def legacy_product_roots(container):
    """Every pre-4.0.0 product root on disk, with the flat name it will take.

    This is the migration's input, and it is a WALK rather than a
    declaration on purpose: the grouping directories a container declared
    are exactly what 4.0.0 stops recording, so after the declaration is
    rewritten the only place the old tree is still described is the tree.

    `<group>/<name>` becomes `<group>-<name>` (the rule stated in
    `project-structure.md` invariant 11a): the group survives in the name,
    so two groups holding a product of the same name do not collide.
    """
    container = Path(container).resolve()
    found = []
    root = container / PRODUCT_ROOT_LEAF
    if _is_repo_folder(root):
        found.append({"container": str(container), "name": None,
                      "root": str(root), "branch": PRODUCT_ROOT_LEAF,
                      "layout": "legacy", "exists": True})
    try:
        groups = sorted(p for p in container.iterdir() if p.is_dir())
    except OSError:
        return found
    for group in groups:
        if group.name in FURNITURE_DIRS or group.name == CODEBASE_DIR \
                or group.name.startswith("."):
            continue
        if _is_repo_folder(group):
            continue                    # a branch folder, not a group
        try:
            children = sorted(p for p in group.iterdir() if p.is_dir())
        except OSError:
            continue
        for child in children:
            branch = child / PRODUCT_ROOT_LEAF
            # `<group>/<name>/main/` first, then the shape that never grew
            # its branch tier — both are legacy, and naming the second one
            # is what lets the migration convert it instead of condemning it.
            if _is_repo_folder(branch):
                place, leaf = branch, PRODUCT_ROOT_LEAF
            elif _is_repo_folder(child) and (child / ".git").is_dir():
                place, leaf = child, None
            else:
                continue
            found.append({"container": str(container),
                          "name": "%s-%s" % (group.name, child.name),
                          "root": str(place), "branch": leaf,
                          "layout": "legacy", "exists": True})
    return found


# --------------------------------------------------------------------------
# where the Phase-1 declaration is
# --------------------------------------------------------------------------
#
# ONE resolver, here for the same reason `product_root` is: this is the
# stdlib module vendored into every store, so the topology reader, the
# classifier, the canary, the session gate and the migration all reach it
# with nothing else beside them.
#
# `design-docs/flows/design.json` is the 4.0.0 home (OQ25: `flows/` is the
# map, and OF4 puts `flows/<activity>/design.json` beside it additively).
# The pre-4.0.0 `design-docs/design.json` is still ANSWERED, tagged
# `legacy` — a container mid-migration must still raise its viewer and
# answer its gates — and never WRITTEN.

DESIGN_DOCS_DIR = "design-docs"
FLOWS_DIR = "flows"
DESIGN_DATA_NAME = "design.json"


def design_path(container):
    """WHERE the Phase-1 declaration of `container` is — the one resolver.

    Returns

        {"container", "path", "layout": "flows" | "legacy", "exists"}

    `layout` is not decoration: a caller that reads a legacy file without
    saying so is a caller that has silently declined to migrate, and the
    reports of every consumer here carry the word.

        flows    <container>/design-docs/flows/design.json
        legacy   <container>/design-docs/design.json

    A legacy answer is given only for a file that is ON DISK. When neither
    is there the CANONICAL path comes back with `exists` False — the answer
    a writer needs, and re-deriving it at the write site is exactly how the
    two halves drift apart.
    """
    container = Path(container).resolve()
    docs = container / DESIGN_DOCS_DIR
    canonical = docs / FLOWS_DIR / DESIGN_DATA_NAME
    if canonical.is_file():
        return {"container": str(container), "path": str(canonical),
                "layout": "flows", "exists": True}
    legacy = docs / DESIGN_DATA_NAME
    if legacy.is_file():
        return {"container": str(container), "path": str(legacy),
                "layout": "legacy", "exists": True}
    return {"container": str(container), "path": str(canonical),
            "layout": "flows", "exists": False}


CONSTITUTION_DIR = "constitution"
CONSTITUTION_NAME = "constitution.md"


def constitution_path(container):
    """WHERE the constitution SLOT of `container` is — the one resolver.

    Same two-step, same reporting, as `design_path()`:

        constitution  <container>/design-docs/constitution/constitution.md
        legacy        <container>/constitution.md

    4.0.0 moved it off the container root. It is the one artifact every later
    phase defers to (`spec-driven-development.md` §2a), and a root file is a
    file two different classes of thing sit beside — the container map, the
    deployment note, and until now the rule nothing may contradict. OF4 puts
    `bias.md` and `manifesto.md` in the same folder, which is the other half
    of the reason it needed one.
    """
    container = Path(container).resolve()
    canonical = container / DESIGN_DOCS_DIR / CONSTITUTION_DIR / \
        CONSTITUTION_NAME
    if canonical.is_file():
        return {"container": str(container), "path": str(canonical),
                "layout": CONSTITUTION_DIR, "exists": True}
    legacy = container / CONSTITUTION_NAME
    if legacy.is_file():
        return {"container": str(container), "path": str(legacy),
                "layout": "legacy", "exists": True}
    return {"container": str(container), "path": str(canonical),
            "layout": CONSTITUTION_DIR, "exists": False}


# --------------------------------------------------------------------------
# which job is open, and where its artefacts go
# --------------------------------------------------------------------------
#
# ONE resolver, here for the reason `product_root` and `design_path` are: it
# is the stdlib module vendored into every store, so the checkpoint hook, the
# Gleaner, the Recaller, the sweep and the migration all reach it with
# nothing else beside them.
#
# 4.0.0 gives every workflow a folder holding what it produces, and deletes
# the folder with the workflow (Q33/Q34/Q39/Q40). So a writer's question is
# no longer "where do checkpoints go" but WHICH JOB IS OPEN, and that has to
# have exactly one answer: two answers scatter one workflow's artefacts
# across two folders, which is the state the top-level `design-docs/reports/`
# and `design-docs/checkpoints/` were retired for leaving behind.
#
# The answer is read from IGNORED state (`design-docs/state/` is excluded by
# the container allowlist), written by `container_repo.py job open` and
# cleared by `job close`. Nothing is open at the start of a session, and the
# artefacts of no workflow are the workflow numbered zero (OQ3).

STATE_DIR = "state"
JOBS_DIR = "jobs"
BUGS_DIR = "bugs"
CURRENT_JOB_STATE = "current-job.json"
JOB_SUBFOLDERS = ("checkpoint", "report", "tmp")
SESSION_JOB_FOLDER = "OF0-session"
JOB_KINDS = ("job", "bug")
# The two ids a job folder may carry, and they are ids rather than slugs:
# `asset-templates.md` §2a.4 declares `OF<n>` for a workflow and `DEF-nn` for
# a defect, and the folder is named by the id so every later reference to the
# work can cite it. `check_structure.py` states the same two patterns as the
# gate that CHECKS them; `test_scripts_repo_guard_06` joins the two spellings so they cannot
# become two standards.
JOB_ID_RE = re.compile(r"^OF\d+-[a-z0-9][a-z0-9-]*$")
BUG_ID_RE = re.compile(r"^DEF-\d\d-[a-z0-9][a-z0-9-]*$")
# The two tracked registers under `jobs/` (OQ11): the REQUEST that opened a
# workflow and the RECORD that closed it. They are the only entries under
# `jobs/` a container repository versions, because they are the only two that
# survive the folder.
JOB_REGISTERS = ("requests", "records")
RECORDS_DIR = "records"
REQUESTS_DIR = "requests"
# The id inside the folder name. The record is named by the ID, never by the
# slug: the slug names the FOLDER, and the folder is the thing that goes away
# (Q12) - a survivor named after it would be a survivor nothing could cite.
_RECORD_ID_OF = {"job": re.compile(r"^(OF\d+)-"),
                 "bug": re.compile(r"^(DEF-\d\d)-")}


def record_id(ident, kind="job"):
    """`OF2` from `OF2-structure-4-0-0`, `DEF-03` from `DEF-03-sweep-blind`.

    None when the folder name carries no id, which is what a pre-4.0.0
    `jobs/<job-slug>/` looks like: there is no record to write for a folder
    the standard cannot name, and inventing one would put a row in the
    permanent register under a name nothing else uses.
    """
    match = _RECORD_ID_OF.get(kind, _RECORD_ID_OF["job"]).match(ident or "")
    return match.group(1) if match else None


def job_record_path(container, ident, kind="job"):
    """WHERE the record of this workflow goes, or None when it has no id."""
    rid = record_id(ident, kind)
    if rid is None:
        return None
    return Path(container).resolve() / DESIGN_DOCS_DIR / JOBS_DIR / \
        RECORDS_DIR / ("%s.json" % rid)


def current_job_state(container):
    """WHERE the marker naming the open job is. Ignored state, never tracked."""
    return Path(container).resolve() / DESIGN_DOCS_DIR / STATE_DIR / \
        CURRENT_JOB_STATE


def current_job(container, create=False):
    """WHICH job is open in `container`, and where its artefacts go.

    Returns

        {"container", "id", "kind": "job" | "bug", "folder", "open",
         "exists", "checkpoint", "report", "tmp"}

    The three subfolders are answered BY NAME rather than left to the caller
    to join: a writer that joins its own path is a writer that can join a
    different one, and the drift is invisible until two folders hold half a
    workflow each.

    `open` is False when no marker names a job — the answer is then the
    workflow numbered zero, `jobs/OF0-session/` (OQ3), created ON DEMAND by
    `create=True` because a folder that is always there says nothing about
    whether a session produced anything.

    A marker that is missing, truncated, not JSON, not an object or carries
    no `id` degrades to that same answer and never raises. This function is
    on the write path of the checkpoint hook, and an exception here is an
    exception where a checkpoint was supposed to be.

    A marker naming a folder that is NOT THERE still answers that folder,
    with `exists` False. Quietly answering `OF0-session` instead would
    scatter a live workflow's artefacts the moment its directory was removed
    by hand, and it would do it silently; `job close` clears the marker, so a
    marker with no folder is a crash artefact and recreating the folder is
    the honest repair.
    """
    container = Path(container).resolve()
    ident, kind, opened = None, "job", False
    marker = current_job_state(container)
    if marker.is_file():
        try:
            data = json.loads(marker.read_text(encoding="utf-8",
                                               errors="replace"))
        except (ValueError, OSError):
            data = None
        if isinstance(data, dict):
            value = data.get("id")
            if isinstance(value, str) and value.strip():
                ident, opened = value.strip(), True
                if data.get("kind") == "bug":
                    kind = "bug"
    if not opened:
        ident, kind = SESSION_JOB_FOLDER, "job"
    parent = BUGS_DIR if kind == "bug" else JOBS_DIR
    folder = container / DESIGN_DOCS_DIR / parent / ident
    if create:
        try:
            for part in JOB_SUBFOLDERS:
                (folder / part).mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
    answer = {"container": str(container), "id": ident, "kind": kind,
              "folder": str(folder), "open": opened,
              "exists": folder.is_dir()}
    for part in JOB_SUBFOLDERS:
        answer[part] = str(folder / part)
    return answer


def design_docs_of(data_path):
    """The `design-docs/` directory that owns a design.json at `data_path`.

    The inverse question, and it has to have an answer because the artifacts
    that live BESIDE the design data did not move with it: the viewer inbox,
    the mailboxes and the handoff artifacts stay at `design-docs/` top level
    (`project-structure-retention.md` §3). A consumer handed only the data
    path — the viewer is handed exactly that — must be able to walk back out
    of `flows/` instead of writing the inbox next to the file it was pointed
    at.
    """
    parent = Path(data_path).resolve().parent
    return parent.parent if parent.name == FLOWS_DIR else parent


def describe(path):
    """What `path` is, as far as this boundary is concerned.

    Returns {"product": bool, "repo", "why", "container"}. `repo` is the
    repository the path belongs to (the thing that would be written), `why`
    is the evidence in one phrase, and `container` names the container above
    it when there is one.
    """
    target = Path(path).resolve()
    repo = repository_root(target)
    if repo is None:
        return {"product": False, "repo": None, "container": None,
                "why": "no repository at or above %s" % target}

    role = store_role(repo / "memory")
    if role == PRODUCT_ROLE:
        return {"product": True, "repo": repo,
                "container": enclosing_container(repo),
                "why": "%s declares scope `repository`"
                       % (repo / "memory" / STORE_MARKER)}

    container = enclosing_container(repo)
    if container is not None:
        return {"product": True, "repo": repo, "container": container,
                "why": "%s is a repository inside the container %s"
                       % (repo, container)}

    return {"product": False, "repo": repo, "container": None,
            "why": "%s is not a product repository (store scope: %s)"
                   % (repo, role or "undeclared")}


def refusal(verb, path, facts, legitimate):
    """The named exit a refused write prints (P-01).

    It says what was refused, on what evidence, and the ONE command that is
    allowed — because "forbidden" without that is a verdict the reader still
    has to translate into an action, and translating it by hand is exactly
    how the boundary was crossed the first time.
    """
    return {
        "status": "REFUSED",
        "verb": verb,
        "target": str(Path(path).resolve()),
        "repository": str(facts["repo"]) if facts["repo"] else "",
        "container": str(facts["container"]) if facts["container"] else "",
        "error": "%s would write into a PRODUCT repository — %s. The "
                 "container's tooling has no authority inside a product; the "
                 "product's own orchestration system installs and maintains "
                 "its furniture (repository-policy.md §2.2)."
                 % (verb, facts["why"]),
        "legitimate": legitimate,
        "exit_code": EXIT_REFUSED,
    }


def guard(verb, path, legitimate=None, repository_self=False):
    """Refuse `verb` if `path` is in a product repository.

    Returns the facts when the write may proceed; raises `ProductBoundary`
    otherwise. `repository_self` is the product's own tooling saying so — and it
    is ignored while `DELEGATION_MARKER` is set, so a Mode D run cannot reach
    a product through a child process that was handed the flag.
    """
    facts = describe(path)
    if not facts["product"]:
        return facts

    delegated = bool(os.environ.get(DELEGATION_MARKER))
    if repository_self and not delegated:
        return facts

    if legitimate is None:
        legitimate = ("run this from the product's OWN orchestration system, "
                      "or pass --repository-self to say that is what this is")
    verdict = refusal(verb, path, facts, legitimate)
    if repository_self and delegated:
        verdict["error"] += (
            " --repository-self was passed by a Mode D child (%s is set), which "
            "is the one caller it can never mean." % DELEGATION_MARKER)
    raise ProductBoundary(verdict)


def enforce(verb, path, legitimate=None, repository_self=False):
    """`guard`, printing the named exit instead of raising.

    Returns (facts, None) when the write may proceed and (None, exit_code)
    when it was refused, so a `cmd_*` function reads as one `if`.
    """
    try:
        return guard(verb, path, legitimate, repository_self), None
    except ProductBoundary as refused:
        print(json.dumps(refused.verdict, ensure_ascii=False))
        return None, refused.verdict["exit_code"]


# --------------------------------------------------------------------------
# the branch a write would land on
# --------------------------------------------------------------------------
#
# A THREE-TERM CONJUNCTION, and the first term is the one that is easy to
# omit: the target is a PRODUCT repository, AND its checked-out branch is
# `main`/`master`, AND that branch has a commit. A container is itself a git
# repository on `main`, maintained that way on purpose — `install-hooks .
# --profile workspace` and `memory_views.py install --store memory` against
# the container's own tree are the ordinary, correct calls — so a refusal
# keyed on the branch name alone would make the container unconfigurable,
# a worse defect than the one being closed. Whether a repository is a
# product is `describe()`'s question and it is asked here rather than
# re-answered: one boundary, one implementation.
#
# IT READS GIT'S FILES, IT DOES NOT RUN GIT — the reason `repository_root`
# gives: this is on the write path of every installer, and it must answer
# the same way where git is absent, where it is a stub, and where it hangs.
# A linked worktree (which is exactly how a `fix-…` branch is checked out
# beside `main/`) carries a `.git` FILE naming its git directory, and its
# refs live in the primary repository's directory named by `commondir`; a
# reader that handled only the folder case would see no branch at all and
# let every worktree through.

PROTECTED_BRANCHES = ("main", "master")


def git_dir(repo):
    """`repo`'s git directory: a `.git` folder, or the one a worktree names.

    A linked worktree's `.git` is a file reading `gitdir: <path>`; its HEAD
    lives at that path, and HEAD is the whole question.
    """
    dot = Path(repo) / ".git"
    if dot.is_dir():
        return dot
    if dot.is_file():
        try:
            text = dot.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None
        for line in text.splitlines():
            if line.startswith("gitdir:"):
                target = Path(line.split(":", 1)[1].strip())
                if not target.is_absolute():
                    target = Path(repo) / target
                return target if target.is_dir() else None
    return None


def common_dir(gitdir):
    """Where the refs live — which is not always where HEAD does.

    A linked worktree's git directory holds its own HEAD but shares the
    primary repository's refs, and names that shared directory in
    `commondir`. Looking for `refs/heads/<branch>` in the worktree's own
    directory would find nothing and read as "no commit yet".
    """
    marker = Path(gitdir) / "commondir"
    if marker.is_file():
        try:
            rel = marker.read_text(encoding="utf-8", errors="replace").strip()
        except OSError:
            return Path(gitdir)
        if rel:
            candidate = Path(rel)
            if not candidate.is_absolute():
                candidate = Path(gitdir) / candidate
            return candidate
    return Path(gitdir)


def current_branch(gitdir):
    """The branch HEAD is on, or None when it is not on one.

    A DETACHED HEAD is not `main` even when it points at `main`'s commit: a
    write there lands on no branch, so it is not the thing this gate exists
    to stop, and it is let through.
    """
    try:
        head = (Path(gitdir) / "HEAD").read_text(
            encoding="utf-8", errors="replace").strip()
    except OSError:
        return None
    if not head.startswith("ref:"):
        return None
    ref = head.split(":", 1)[1].strip()
    prefix = "refs/heads/"
    return ref[len(prefix):] if ref.startswith(prefix) else None


def branch_has_commit(gitdir, branch):
    """Does `branch` name a commit yet?

    A repository freshly `git init`-ed is ON `main` with nothing on it, and
    installing furniture into one is how a product is set up in the first
    place — the creation commit takes it. Refusing there would break the
    ordinary case to protect a branch that does not exist, so an unborn
    branch is not protected.
    """
    common = common_dir(gitdir)
    loose = common.joinpath("refs", "heads", *branch.split("/"))
    try:
        if loose.is_file() and loose.read_text(
                encoding="utf-8", errors="replace").strip():
            return True
    except OSError:
        pass
    ref = "refs/heads/%s" % branch
    try:
        for line in (common / "packed-refs").read_text(
                encoding="utf-8", errors="replace").splitlines():
            parts = line.split()
            if len(parts) == 2 and parts[1] == ref:
                return True
    except OSError:
        pass
    return False


def protected_branch(path):
    """(repo, branch) when a write to `path` would land on a PRODUCT
    repository's protected branch; None whenever the write may proceed —
    not a product, no repository, no git directory, a detached HEAD, a
    branch nobody protects, or a branch with nothing on it yet.
    """
    facts = describe(path)
    if not facts["product"] or facts["repo"] is None:
        return None
    repo = facts["repo"]
    gitdir = git_dir(repo)
    if gitdir is None:
        return None
    branch = current_branch(gitdir)
    if branch not in PROTECTED_BRANCHES:
        return None
    if not branch_has_commit(gitdir, branch):
        return None
    return repo, branch


def refuse_protected_branch(verb, path, legitimate=None):
    """The named exit for a write aimed at a protected branch, or None.

    `refusal()`'s shape — the same keys, the same `exit_code`, the same
    "here is the ONE command that IS legitimate" ending, plus `branch`, the
    evidence here — but NOT `refusal()` itself: its `error` sentence states
    a different finding ("would write into a PRODUCT repository"), and a
    gate that reports the wrong reason sends its reader to fix the wrong
    thing. The legitimate route is the branch one: hook, store and viewer
    CHANGES travel by pull request (repository-policy.md §2.2).
    """
    protected = protected_branch(path)
    if protected is None:
        return None
    repo, branch = protected
    if legitimate is None:
        legitimate = ("container_repo.py start-branch %s --name fix-<slug>, "
                      "then run this verb against the worktree it creates, "
                      "commit there and open the pull request" % repo)
    container = enclosing_container(repo)
    return {
        "status": "REFUSED",
        "verb": verb,
        "target": str(Path(path).resolve()),
        "repository": str(repo),
        "container": str(container) if container else "",
        "branch": branch,
        "error": "%s writes TRACKED files, and %s is checked out on `%s` — "
                 "a protected branch with a HEAD commit. Committing them "
                 "there puts them in the repository without a pull request, "
                 "which is the review that branch exists to require "
                 "(repository-policy.md §2.2)." % (verb, repo, branch),
        "legitimate": legitimate,
        "exit_code": EXIT_REFUSED,
    }


def enforce_protected_branch(verb, path, legitimate=None):
    """`refuse_protected_branch`, printing the named exit.

    Returns None when the write may proceed and the exit code when it was
    refused, so a `cmd_*` function reads as one `if` — placed AFTER its
    `enforce()`, so a container reaching into a product still gets the
    boundary's own refusal, which names the right remedy for that different
    mistake.
    """
    verdict = refuse_protected_branch(verb, path, legitimate)
    if verdict is None:
        return None
    print(json.dumps(verdict, ensure_ascii=False))
    return verdict["exit_code"]


def add_repository_self_flag(parser):
    """Give a writing verb the one override, worded the same way everywhere."""
    parser.add_argument(
        "--repository-self", action="store_true",
        help="this IS the product's own orchestration system acting on its "
             "own repository (refused inside a Mode D run)")


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="repo_guard.py",
        description="Is this path inside a product repository?")
    sub = parser.add_subparsers(dest="verb", required=True)
    check = sub.add_parser("check", help="report the boundary verdict")
    check.add_argument("path", nargs="?", default=".")
    add_repository_self_flag(check)
    args = parser.parse_args(argv)

    facts, code = enforce("repo_guard.py check", args.path,
                          repository_self=args.repository_self)
    if code is not None:
        return code
    protected = protected_branch(args.path)
    print(json.dumps({
        "status": "COMPLETED",
        "target": str(Path(args.path).resolve()),
        "repository": str(facts["repo"]) if facts["repo"] else "",
        "product": facts["product"],
        "why": facts["why"],
        "protected_branch": protected[1] if protected else None,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
