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
--profile product`, `memory_views.py install`, `coverage_views.py install`
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
    loud with `--product-self`;
  * `redistribute.py` never passes that flag, and marks its own child
    processes so one cannot be made to pass it either.

WHAT THIS IS NOT. It is not the five-way `classify_target` in
`redistribute.py`, which answers "what should this target do next" for a Mode
D verb. This answers one question — *is this a product repository, or inside
one* — because that is the only question a write gate has, and two
implementations of one boundary is two places for it to drift.

Usage
    py product_boundary.py check <path> [--product-self]
"""

import argparse
import json
import os
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

# The environment variable a Mode D run sets on every child it spawns. It is
# not a way IN — nothing reads it to grant permission. It is a way of making
# sure a child cannot be handed `--product-self` and believed: while this is
# set, the override is refused no matter who asks.
DELEGATION_MARKER = "ORCHESTRATOR_DESIGN_MODE_D"

STORE_MARKER = "store-role.json"
PRODUCT_ROLE = "product"
CONTAINER_ROLE = "container"

EXIT_REFUSED = 2


class ProductBoundary(Exception):
    """A write was aimed at a product repository. Carries the named exit."""

    def __init__(self, verdict):
        self.verdict = verdict
        super().__init__(verdict["error"])


def store_role(store):
    """The role a store's own marker declares, or None.

    Same two-state reading `container_repo.py` and `redistribute.py` use: a
    store with no marker has no role, and NOBODY guesses one for it.
    """
    marker = Path(store) / STORE_MARKER
    if not marker.is_file():
        return None
    try:
        data = json.loads(marker.read_text(encoding="utf-8", errors="replace"))
    except (ValueError, OSError):
        return None
    role = data.get("role") if isinstance(data, dict) else None
    return role if isinstance(role, str) else None


def enclosing_container(path):
    """The container repository `path` sits inside, or None.

    A repository inside a container is a product of that container whatever
    its own store says — including when it has no store at all, which is the
    state a product is in before anything has been installed for it, and
    precisely the state in which a container's tooling is most tempted to
    reach in.
    """
    path = Path(path).resolve()
    for parent in path.parents:
        if (parent / "design-docs").is_dir() and \
                store_role(parent / "memory") == CONTAINER_ROLE:
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
                "why": "%s declares role `product`"
                       % (repo / "memory" / STORE_MARKER)}

    container = enclosing_container(repo)
    if container is not None:
        return {"product": True, "repo": repo, "container": container,
                "why": "%s is a repository inside the container %s"
                       % (repo, container)}

    return {"product": False, "repo": repo, "container": None,
            "why": "%s is not a product repository (store role: %s)"
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


def guard(verb, path, legitimate=None, product_self=False):
    """Refuse `verb` if `path` is in a product repository.

    Returns the facts when the write may proceed; raises `ProductBoundary`
    otherwise. `product_self` is the product's own tooling saying so — and it
    is ignored while `DELEGATION_MARKER` is set, so a Mode D run cannot reach
    a product through a child process that was handed the flag.
    """
    facts = describe(path)
    if not facts["product"]:
        return facts

    delegated = bool(os.environ.get(DELEGATION_MARKER))
    if product_self and not delegated:
        return facts

    if legitimate is None:
        legitimate = ("run this from the product's OWN orchestration system, "
                      "or pass --product-self to say that is what this is")
    verdict = refusal(verb, path, facts, legitimate)
    if product_self and delegated:
        verdict["error"] += (
            " --product-self was passed by a Mode D child (%s is set), which "
            "is the one caller it can never mean." % DELEGATION_MARKER)
    raise ProductBoundary(verdict)


def enforce(verb, path, legitimate=None, product_self=False):
    """`guard`, printing the named exit instead of raising.

    Returns (facts, None) when the write may proceed and (None, exit_code)
    when it was refused, so a `cmd_*` function reads as one `if`.
    """
    try:
        return guard(verb, path, legitimate, product_self), None
    except ProductBoundary as refused:
        print(json.dumps(refused.verdict, ensure_ascii=False))
        return None, refused.verdict["exit_code"]


def add_product_self_flag(parser):
    """Give a writing verb the one override, worded the same way everywhere."""
    parser.add_argument(
        "--product-self", action="store_true",
        help="this IS the product's own orchestration system acting on its "
             "own repository (refused inside a Mode D run)")


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="product_boundary.py",
        description="Is this path inside a product repository?")
    sub = parser.add_subparsers(dest="verb", required=True)
    check = sub.add_parser("check", help="report the boundary verdict")
    check.add_argument("path", nargs="?", default=".")
    add_product_self_flag(check)
    args = parser.parse_args(argv)

    facts, code = enforce("product_boundary.py check", args.path,
                          product_self=args.product_self)
    if code is not None:
        return code
    print(json.dumps({
        "status": "COMPLETED",
        "target": str(Path(args.path).resolve()),
        "repository": str(facts["repo"]) if facts["repo"] else "",
        "product": facts["product"],
        "why": facts["why"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
