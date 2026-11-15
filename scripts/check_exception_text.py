#!/usr/bin/env python
# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
# =============================================================================
# SCRIPT: check_exception_text  (standalone script, PixelArt Creator)
# =============================================================================
# PURPOSE: Find every place in the interface layer where the text of a caught
#   exception can reach a surface the user reads, and fail on each place where
#   the shown text takes a value from the exception. Report only; it never
#   edits a file.
# FLAVOUR: standalone
# LOCATION: scripts/check_exception_text.py
# OWNER ROLE: the localisation agent, which also owns the unwrapped-string
#   audit (scripts/string_audit_check.py); contract tests belong to the
#   scripts test owner.
# INVOKED BY: the localisation string audit, and by CI as a gate once the
#   interface code shows no exception text.
# RUNTIME: CPython 3.12+, stdlib only (ast, argparse, json, os, sys).
# ENTRYPOINT: python scripts/check_exception_text.py [paths ...]
#             [--root pixelart_creator/ui] [--json]
# INPUTS:
#   paths   (positional, optional): explicit .py files to examine.
#   --root  (optional, default "pixelart_creator/ui"): directory scanned when
#           no explicit paths are given.
#   --json  (flag, optional): print the machine-readable report (every site,
#           the tainted sites grouped by file, the denominators) instead of
#           the human report.
# OUTPUTS:
#   stdout: the report; the denominators (files examined, handlers examined,
#           sites found) are always printed first.
#   stderr: one-line verdict for failures.
# EXIT CODES: 0 clean (a non-zero number of sites, none tainted);
#   1 any tainted site, OR nothing examined (no file), OR no site found in the
#   files examined (a zero denominator is a failure, never a pass);
#   2 usage error, missing root or path, or a file that cannot be parsed.
# DETERMINISM: deterministic; files and sites are sorted; no clock, no
#   randomness, no network.
# =============================================================================
"""Find where a caught exception's text reaches the user, in the UI layer.

DEFINITION OF A SITE
    A site is a place, inside an ``except ... as <name>`` handler, from which a
    surface the user reads is reached. A handler without ``as <name>`` cannot
    carry exception text and is counted as a handler but yields no site. One
    site is one (location, channel) pair; the number of distinct handlers that
    hold at least one site is printed beside the site count.

THE CHANNELS
    message box
        A ``QMessageBox`` static call (information, warning, critical,
        question, about, aboutQt), a text setter on a ``QMessageBox``
        instance, or a call to a function of the same module that makes one.
    translated template
        ``.replace(...)``, ``.arg(...)``, ``.format(...)`` or ``%`` applied to
        the result of ``tr()``, ``self.tr()`` or ``QCoreApplication
        .translate()`` (directly, through a chain, or through a local that
        holds the result). A message box or signal whose argument is built by
        a template is counted once, as the template.
    worker signal
        ``<signal>.emit(<at least one argument>)`` inside the handler, or a
        call to a function of the same module that does it.
    stored for later display
        An attribute or container assigned or mutated inside the handler with
        a value derived from the exception, and read by a surface call
        elsewhere in the same module (an attribute), or after the handler in
        the same function (a local); or a value derived from the exception
        that the handler returns to its caller.
    direct surface (outside the four channels above; added so that a failure
        shown through a status bar, label, tooltip, text view or window title
        is not invisible to the check)
        A call of a text setter or appender (``setText``, ``showMessage``,
        ``setToolTip``, ``setHtml``, ``appendPlainText`` ...) inside the
        handler, or a call to a function of the same module that makes one.

TAINT
    A value is tainted when it is the exception name, ``str``/``repr``/
    ``format`` of it, an f-string or any other expression holding it,
    ``type(<name>).__name__`` (``type(<name>)`` itself is tainted), an
    attribute of it (``.args``, ``.errno``, ``.filename`` ...), the result of a
    call taking a tainted argument, or a local assigned from such a value
    (assignment, augmented assignment, loop target, or ``append``/``extend``/
    ``add``/``update``... on that local). The only things that clear taint
    are the calls named in SANITISERS (``failure_kind``, ``failure_text``,
    ``isinstance``, ``issubclass``, ``len``, ``bool``, ``id``, ``hasattr``,
    ``callable``): a value that is only classified, never quoted, is clean.
    A site is TAINTED when an argument that reaches the surface is tainted.

LIMITS (what this check cannot see)
    * Taint is followed within one module only. A helper in another module that
      formats the exception is not followed; a tainted value handed to a call
      the check cannot resolve is listed as "not followed" (informational,
      never counted, never an exit cause).
    * A same-module function is resolved by its simple name, through a bare
      name or a ``self``/``cls``/class-name receiver; a method of another
      object with the same name is not resolved.
    * Taint is flow-insensitive inside one handler or function: a local that
      is tainted once stays tainted, and a reassignment does not clear it.
    * A function is assumed to put its tainted parameter into what it shows
      when the parameter reaches the surface call's arguments; a function that
      ignores the value after a call is a false positive, not a miss.
    * A signal emitted in a worker is a site; the slot that receives the text
      and shows it is not an exception handler and is not examined.
    * ``QTextEdit.append`` on an attribute is read as a container mutation,
      not as a surface; ``list.append`` on a plain local is a container.
    * Exception text re-raised in another exception, written to a log, or
      printed is not a surface and is not a site.
    * Text reaching the user through a custom widget method that is not in the
      setter list is not seen.
    * The raise sites in the layers below the interface are out of scope.
    A runtime test with a planted marker text over the channels is the
    backstop for what a static scan cannot follow.

OCTOBER FIGURE
    An earlier hand measurement found 72 such sites. It is printed beside the
    measured total as a record. It is never compared and never a target.
"""

import argparse
import ast
import json
import os
import sys

OCTOBER_FIGURE = 72

CH_BOX = "message box"
CH_TEMPLATE = "translated template"
CH_SIGNAL = "worker signal"
CH_STORED = "stored for later display"
CH_DIRECT = "direct surface"
CHANNELS = (CH_BOX, CH_TEMPLATE, CH_SIGNAL, CH_STORED, CH_DIRECT)

BOX_CLASS = "QMessageBox"
BOX_STATICS = {"information", "warning", "critical", "question", "about", "aboutQt"}
BOX_INSTANCE_TEXT = {"setText", "setInformativeText", "setDetailedText"}
TR_NAMES = {"tr", "translate", "trUtf8"}
TEMPLATE_METHODS = {"replace", "arg", "format"}
SANITISERS = {
    "failure_kind",
    "failure_text",
    "isinstance",
    "issubclass",
    "len",
    "bool",
    "id",
    "hasattr",
    "callable",
}
DIRECT_SETTERS = {
    "setText",
    "setHtml",
    "setPlainText",
    "setMarkdown",
    "showMessage",
    "setToolTip",
    "setStatusTip",
    "setWhatsThis",
    "setWindowTitle",
    "setTitle",
    "setLabelText",
    "setPlaceholderText",
    "setItemText",
    "setTabText",
    "setTabToolTip",
    "setAccessibleName",
    "setAccessibleDescription",
    "setPrefix",
    "setSuffix",
    "addItem",
    "addItems",
    "appendPlainText",
    "appendHtml",
    "insertPlainText",
    "insertHtml",
}
MUTATORS = {"append", "extend", "add", "insert", "update", "setdefault", "appendleft"}
LOG_METHODS = {
    "debug",
    "info",
    "warning",
    "error",
    "exception",
    "critical",
    "log",
    "fatal",
}
QUIET_CALLS = {
    "str",
    "repr",
    "print",
    "format",
    "list",
    "tuple",
    "dict",
    "set",
    "frozenset",
    "sorted",
    "int",
    "float",
    "getattr",
    "type",
    "hash",
    "join",
    "strip",
    "lstrip",
    "rstrip",
    "split",
    "splitlines",
    "lower",
    "upper",
    "replace",
    "encode",
    "decode",
    "startswith",
    "endswith",
    "get",
    "items",
    "keys",
    "values",
    "append",
    "extend",
    "add",
    "insert",
    "update",
    "setdefault",
    "min",
    "max",
    "next",
    "iter",
    "enumerate",
    "zip",
    "map",
    "filter",
    "any",
    "all",
}


def call_name(func):
    """Return the simple name a call's callee ends in, or None."""
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def walk_all(nodes):
    """Yield every AST node under each node of an iterable."""
    for node in nodes:
        for sub in ast.walk(node):
            yield sub


def is_tr_call(node):
    """True for tr(...), self.tr(...), QCoreApplication.translate(...)."""
    return isinstance(node, ast.Call) and call_name(node.func) in TR_NAMES


def root_name(node):
    """Return the base Name id of a Name/Attribute/Subscript chain, or None."""
    while isinstance(node, (ast.Attribute, ast.Subscript)):
        node = node.value
    return node.id if isinstance(node, ast.Name) else None


def target_names(target):
    """Names bound or mutated by an assignment target (not attributes)."""
    if isinstance(target, ast.Name):
        return [target.id]
    if isinstance(target, (ast.Tuple, ast.List)):
        out = []
        for elt in target.elts:
            out.extend(target_names(elt))
        return out
    if isinstance(target, ast.Starred):
        return target_names(target.value)
    if isinstance(target, ast.Subscript):
        base = root_name(target)
        return [base] if base and base not in ("self", "cls") else []
    return []


def target_attrs(target):
    """Attribute names written by an assignment target."""
    if isinstance(target, ast.Attribute):
        return [target.attr]
    if isinstance(target, (ast.Tuple, ast.List)):
        out = []
        for elt in target.elts:
            out.extend(target_attrs(elt))
        return out
    if isinstance(target, ast.Subscript) and isinstance(target.value, ast.Attribute):
        return [target.value.attr]
    return []


def assignment_pairs(node):
    """Return (targets, value) for an assignment-like statement, or None."""
    if isinstance(node, ast.Assign):
        return node.targets, node.value
    if isinstance(node, ast.AugAssign):
        return [node.target], node.value
    if isinstance(node, ast.AnnAssign) and node.value is not None:
        return [node.target], node.value
    if isinstance(node, ast.NamedExpr):
        return [node.target], node.value
    if isinstance(node, (ast.For, ast.AsyncFor)):
        return [node.target], node.iter
    return None


class Reach:
    """One surface reached from a region: channel, location, taint, fix point."""

    def __init__(self, channel, node, label, tainted, fix_line, via=""):
        self.channel = channel
        self.line = node.lineno
        self.col = node.col_offset
        self.label = label
        self.tainted = tainted
        self.fix_line = fix_line
        self.via = via


class Effect:
    """What a same-module function does with its parameters."""

    def __init__(self, params, param_reaches):
        self.params = params
        self.param_reaches = param_reaches


class Module:
    """One parsed module: its functions, classes and the memoised effects."""

    def __init__(self, relpath, tree):
        self.rel = relpath
        self.tree = tree
        self.funcs = {}
        self.classes = set()
        self.parents = {}
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                self.parents[child] = node
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self.funcs.setdefault(node.name, []).append(node)
            elif isinstance(node, ast.ClassDef):
                self.classes.add(node.name)
        self._effects = {}
        self._in_progress = set()

    def enclosing_function(self, node):
        """Nearest enclosing function definition of a node, or None."""
        cur = self.parents.get(node)
        while cur is not None:
            if isinstance(cur, (ast.FunctionDef, ast.AsyncFunctionDef)):
                return cur
            cur = self.parents.get(cur)
        return None

    def effect(self, name):
        """Memoised Effect of the same-module functions called `name`."""
        if name in self._effects:
            return self._effects[name]
        if name in self._in_progress or name not in self.funcs:
            return None
        self._in_progress.add(name)
        try:
            defs = self.funcs[name]
            first = defs[0]
            params = _param_names(first)
            param_reaches = {}
            for fn in defs:
                for p in _param_names(fn):
                    pctx = Ctx(self, {p})
                    hits = [r for r in pctx.reaches(fn.body) if r.tainted]
                    param_reaches.setdefault(p, []).extend(hits)
            eff = Effect(params, param_reaches)
        finally:
            self._in_progress.discard(name)
        self._effects[name] = eff
        return eff


def _param_names(fn):
    """Positional-or-keyword parameter names of a function, without self/cls."""
    args = fn.args
    names = [a.arg for a in list(args.posonlyargs) + list(args.args)]
    names += [a.arg for a in args.kwonlyargs]
    is_static = any(
        isinstance(d, ast.Name) and d.id == "staticmethod" for d in fn.decorator_list
    )
    if names and names[0] in ("self", "cls") and not is_static:
        names = names[1:]
    return names


class Ctx:
    """Taint state of one region (a handler body or a function body)."""

    def __init__(self, module, names, attrs=(), sanitise=True):
        self.mod = module
        self.names = set(names)
        self.attrs = set(attrs)
        self.sanitise = sanitise
        self.tr_locals = set()
        self.template_locals = set()
        self.box_locals = set()

    # -- taint ---------------------------------------------------------------
    def tainted(self, node):
        """True when the expression holds a tainted value."""
        if node is None:
            return False
        if isinstance(node, ast.Name):
            return node.id in self.names
        if isinstance(node, ast.Attribute):
            if node.attr in self.attrs and isinstance(node.ctx, ast.Load):
                return True
            return self.tainted(node.value)
        if isinstance(node, ast.Call):
            if self.sanitise and call_name(node.func) in SANITISERS:
                return False
            return any(self.tainted(c) for c in ast.iter_child_nodes(node))
        return any(self.tainted(c) for c in ast.iter_child_nodes(node))

    # -- templates -----------------------------------------------------------
    def is_template(self, node):
        """True for a tr()-based .replace/.arg/.format call or tr() % args."""
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod):
            return is_tr_call(node.left) or (
                isinstance(node.left, ast.Name) and node.left.id in self.tr_locals
            )
        if not isinstance(node, ast.Call):
            return False
        func = node.func
        if not (isinstance(func, ast.Attribute) and func.attr in TEMPLATE_METHODS):
            return False
        cur = func.value
        while True:
            if isinstance(cur, ast.Call):
                if is_tr_call(cur):
                    return True
                f = cur.func
                if isinstance(f, ast.Attribute) and f.attr in TEMPLATE_METHODS:
                    cur = f.value
                    continue
                return False
            if isinstance(cur, ast.Name):
                return cur.id in self.tr_locals
            return False

    def template_derived(self, node):
        """True when an expression holds a template or a local made from one."""
        for sub in ast.walk(node):
            if isinstance(sub, ast.Name) and sub.id in self.template_locals:
                return True
            if self.is_template(sub):
                return True
        return False

    # -- preparation -----------------------------------------------------------
    def prepare(self, body):
        """Compute the local sets (tr, box, template) and the taint fixpoint."""
        nodes = list(walk_all(body))
        for node in nodes:
            if isinstance(node, ast.Assign):
                val = node.value
                if is_tr_call(val):
                    for t in node.targets:
                        self.tr_locals.update(target_names(t))
                if isinstance(val, ast.Call) and call_name(val.func) == BOX_CLASS:
                    for t in node.targets:
                        self.box_locals.update(target_names(t))
        changed = True
        while changed:
            changed = False
            for node in nodes:
                pair = assignment_pairs(node)
                if pair is not None:
                    targets, value = pair
                    bound = []
                    for t in targets:
                        bound.extend(target_names(t))
                    if self.tainted(value):
                        for name in bound:
                            if name not in self.names:
                                self.names.add(name)
                                changed = True
                    if self.template_derived(value):
                        for name in bound:
                            if name not in self.template_locals:
                                self.template_locals.add(name)
                                changed = True
                elif (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr in MUTATORS
                ):
                    base = root_name(node.func.value)
                    if base and base not in ("self", "cls") and base not in self.names:
                        if any(self.tainted(a) for a in node.args):
                            self.names.add(base)
                            changed = True

    # -- surfaces --------------------------------------------------------------
    def _args(self, call):
        return list(call.args) + [k.value for k in call.keywords]

    def reaches(self, body):
        """Return the Reach list for a region (channels reached, taint each)."""
        self.prepare(body)
        out = []
        calls = [n for n in walk_all(body) if isinstance(n, (ast.Call, ast.BinOp))]
        templates = [n for n in calls if self.is_template(n)]
        inner = set()
        for node in templates:
            cur = node.func.value if isinstance(node, ast.Call) else None
            while isinstance(cur, ast.Call) and self.is_template(cur):
                inner.add(cur)
                cur = cur.func.value
        for node in templates:
            if node in inner:
                continue
            out.append(
                Reach(
                    CH_TEMPLATE, node, "tr() template", self.tainted(node), node.lineno
                )
            )
        for call in calls:
            if not isinstance(call, ast.Call) or self.is_template(call):
                continue
            out.extend(self._call_reaches(call))
        return out

    def _call_reaches(self, call):
        func = call.func
        name = call_name(func)
        args = self._args(call)
        suppressed = any(self.template_derived(a) for a in args)
        tainted = any(self.tainted(a) for a in args)
        line = call.lineno
        if isinstance(func, ast.Attribute):
            recv = func.value
            is_box_class = (isinstance(recv, ast.Name) and recv.id == BOX_CLASS) or (
                isinstance(recv, ast.Attribute) and recv.attr == BOX_CLASS
            )
            if is_box_class and name in BOX_STATICS:
                if suppressed:
                    return []
                return [Reach(CH_BOX, call, "QMessageBox.%s" % name, tainted, line)]
            if (
                name in BOX_INSTANCE_TEXT
                and isinstance(recv, ast.Name)
                and recv.id in self.box_locals
            ):
                if suppressed:
                    return []
                label = "%s.%s" % (recv.id, name)
                return [Reach(CH_BOX, call, label, tainted, line)]
            if name == "emit" and args:
                if suppressed:
                    return []
                return [Reach(CH_SIGNAL, call, _unparse(func), tainted, line)]
            if name in DIRECT_SETTERS:
                if suppressed:
                    return []
                return [Reach(CH_DIRECT, call, _unparse(func), tainted, line)]
        helper = self._resolve(call)
        if helper is not None:
            return self._helper_reaches(call, helper)
        return []

    def _resolve(self, call):
        func = call.func
        if isinstance(func, ast.Name):
            return func.id if func.id in self.mod.funcs else None
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
            recv = func.value.id
            if recv in ("self", "cls") or recv in self.mod.classes:
                return func.attr if func.attr in self.mod.funcs else None
        return None

    def _helper_reaches(self, call, name):
        eff = self.mod.effect(name)
        if eff is None:
            return []
        tainted_params = []
        for i, arg in enumerate(call.args):
            if i < len(eff.params) and self.tainted(arg):
                tainted_params.append(eff.params[i])
        for kw in call.keywords:
            if kw.arg in eff.params and self.tainted(kw.value):
                tainted_params.append(kw.arg)
        hits = []
        for p in tainted_params:
            hits.extend(eff.param_reaches.get(p, []))
        out = []
        seen = set()
        for r in hits:
            if r.channel in seen:
                continue
            seen.add(r.channel)
            label = "%s -> %s" % (name, r.label)
            out.append(Reach(r.channel, call, label, True, r.fix_line))
        if not hits and (call.args or call.keywords):
            # a clean call into a function that shows what it is handed
            for plist in eff.param_reaches.values():
                for r in plist:
                    if r.channel in seen:
                        continue
                    seen.add(r.channel)
                    label = "%s -> %s" % (name, r.label)
                    out.append(Reach(r.channel, call, label, False, r.fix_line))
        return out


def _unparse(node):
    try:
        text = ast.unparse(node)
    except Exception:  # pragma: no cover - defensive, ast.unparse is total
        text = "<expr>"
    return text if len(text) <= 60 else text[:57] + "..."


def examine_module(rel, source):
    """Return (handler_count, named_count, sites, unfollowed) for one module."""
    tree = ast.parse(source, filename=rel)
    mod = Module(rel, tree)
    handlers = [n for n in ast.walk(tree) if isinstance(n, ast.ExceptHandler)]
    named = [h for h in handlers if h.name]
    sites = {}
    unfollowed = {}

    def add(channel, line, col, label, tainted, handler, fix_line, via=""):
        key = (line, col, channel)
        rec = sites.get(key)
        if rec is None:
            sites[key] = {
                "file": rel,
                "line": line,
                "channel": channel,
                "surface": label,
                "tainted": bool(tainted),
                "handler_line": handler.lineno,
                "fix_line": fix_line,
                "via": via,
            }
        elif tainted and not rec["tainted"]:
            rec["tainted"] = True
            rec["surface"] = label
            rec["fix_line"] = fix_line

    stored_cache = {}
    for handler in named:
        ctx = Ctx(mod, {handler.name})
        for r in ctx.reaches(handler.body):
            add(r.channel, r.line, r.col, r.label, r.tainted, handler, r.fix_line)
        func = mod.enclosing_function(handler)
        mention = Ctx(mod, ctx.names, sanitise=False)
        mention.tr_locals = ctx.tr_locals
        in_raise = set()
        for node in walk_all(handler.body):
            if isinstance(node, ast.Raise):
                in_raise.update(ast.walk(node))
        for node in walk_all(handler.body):
            # a value derived from the exception returned to the caller
            if isinstance(node, ast.Return) and node.value is not None:
                if ctx.tainted(node.value):
                    add(
                        CH_STORED,
                        node.lineno,
                        node.col_offset,
                        "returned to caller",
                        True,
                        handler,
                        node.lineno,
                    )
            # stored attributes and local containers
            writes = []
            pair = assignment_pairs(node)
            if pair is not None and not isinstance(node, (ast.For, ast.AsyncFor)):
                targets, value = pair
                for t in targets:
                    writes.append((t, value))
            elif (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in MUTATORS
            ):
                for a in node.args:
                    writes.append((node.func.value, a))
            for target, value in writes:
                if not mention.tainted(value):
                    continue
                strict = ctx.tainted(value)
                for attr in target_attrs(target):
                    key = ("attr", attr)
                    if key not in stored_cache:
                        stored_cache[key] = _attr_reads(mod, attr)
                    strict_ev, mention_ev = stored_cache[key]
                    if mention_ev:
                        ev = (strict_ev or mention_ev)[0]
                        add(
                            CH_STORED,
                            node.lineno,
                            node.col_offset,
                            "self.%s stored" % attr,
                            strict and bool(strict_ev),
                            handler,
                            ev.fix_line,
                            "read by %s at line %d" % (ev.label, ev.line),
                        )
                local = []
                if isinstance(target, ast.Name):
                    local = [target.id]
                else:
                    local = target_names(target)
                for name in local:
                    if func is None:
                        continue
                    lo, hi = handler.lineno, getattr(handler, "end_lineno", None)
                    hi = hi or handler.lineno
                    strict_ev = _local_reads(mod, func, name, lo, hi, True)
                    mention_ev = _local_reads(mod, func, name, lo, hi, False)
                    if mention_ev:
                        ev = (strict_ev or mention_ev)[0]
                        add(
                            CH_STORED,
                            node.lineno,
                            node.col_offset,
                            "local %s stored" % name,
                            strict and bool(strict_ev),
                            handler,
                            ev.fix_line,
                            "read by %s at line %d" % (ev.label, ev.line),
                        )
        # tainted values handed to a call the check cannot resolve (information)
        for node in walk_all(handler.body):
            if not isinstance(node, ast.Call) or node in in_raise:
                continue
            name = call_name(node.func)
            if name is None or name in QUIET_CALLS or name in SANITISERS:
                continue
            if name in TR_NAMES or name in LOG_METHODS or name == "emit":
                continue
            if name in BOX_STATICS or name in DIRECT_SETTERS or ctx.is_template(node):
                continue
            if name in mod.funcs:
                continue
            if root_name(node.func) in ctx.names:
                continue
            if any(ctx.tainted(a) for a in ctx._args(node)):
                unfollowed[(node.lineno, node.col_offset)] = {
                    "file": rel,
                    "line": node.lineno,
                    "callee": _unparse(node.func),
                }
    ordered = sorted(sites.values(), key=lambda s: (s["line"], s["channel"]))
    unf = sorted(unfollowed.values(), key=lambda u: u["line"])
    return len(handlers), len(named), ordered, unf


def _attr_reads(mod, attr):
    """Surface reads of `self.<attr>` in the module: (strict, mention) lists."""
    strict, mention = [], []
    holders = []
    for fn_list in mod.funcs.values():
        for fn in fn_list:
            for sub in ast.walk(fn):
                if (
                    isinstance(sub, ast.Attribute)
                    and sub.attr == attr
                    and isinstance(sub.ctx, ast.Load)
                ):
                    holders.append(fn)
                    break
    seen = set()
    for fn in holders:
        if id(fn) in seen:
            continue
        seen.add(id(fn))
        for sanitise, bucket in ((True, strict), (False, mention)):
            ctx = Ctx(mod, set(), attrs={attr}, sanitise=sanitise)
            bucket.extend(r for r in ctx.reaches(fn.body) if r.tainted)
    return strict, mention


def _local_reads(mod, func, name, lo, hi, sanitise):
    """Surface reads of a local after a handler, in the same function."""
    ctx = Ctx(mod, {name}, sanitise=sanitise)
    return [r for r in ctx.reaches(func.body) if r.tainted and not lo <= r.line <= hi]


def collect(paths, root):
    """Return the sorted list of .py files to examine."""
    files = []
    if paths:
        files = [p for p in paths if p.endswith(".py") and os.path.isfile(p)]
    elif os.path.isdir(root):
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = sorted(d for d in dirnames if d != "__pycache__")
            for fname in sorted(filenames):
                if fname.endswith(".py"):
                    files.append(os.path.join(dirpath, fname))
    return sorted(set(files))


def build_report(files):
    """Examine files; return the report dict. Raises on an unparsable file."""
    all_sites = []
    unfollowed = []
    handlers = named = 0
    for path in files:
        rel = path.replace("\\", "/")
        with open(path, "rb") as fh:
            source = fh.read().decode("utf-8")
        h, n, sites, unf = examine_module(rel, source)
        handlers += h
        named += n
        all_sites.extend(sites)
        unfollowed.extend(unf)
    by_channel = {c: {"sites": 0, "tainted": 0} for c in CHANNELS}
    tainted_by_file = {}
    handler_keys = set()
    for s in all_sites:
        by_channel[s["channel"]]["sites"] += 1
        handler_keys.add((s["file"], s["handler_line"]))
        if s["tainted"]:
            by_channel[s["channel"]]["tainted"] += 1
            tainted_by_file.setdefault(s["file"], []).append(s)
    fix_points = sorted({(s["file"], s["fix_line"]) for s in all_sites if s["tainted"]})
    fix_points = [{"file": f, "line": n} for f, n in fix_points]
    return {
        "files_examined": len(files),
        "handlers_examined": handlers,
        "handlers_named": named,
        "handlers_with_sites": len(handler_keys),
        "sites_total": len(all_sites),
        "tainted_total": sum(c["tainted"] for c in by_channel.values()),
        "by_channel": by_channel,
        "october_figure": OCTOBER_FIGURE,
        "sites": all_sites,
        "tainted_by_file": tainted_by_file,
        "fix_points": fix_points,
        "not_followed": unfollowed,
    }


def print_human(rep, out):
    """Write the human report."""
    w = out.write
    w(
        "check_exception_text: files examined %d, handlers examined %d "
        "(%d named), sites found %d in %d handlers\n"
        % (
            rep["files_examined"],
            rep["handlers_examined"],
            rep["handlers_named"],
            rep["sites_total"],
            rep["handlers_with_sites"],
        )
    )
    w("%-28s %6s %8s\n" % ("channel", "sites", "tainted"))
    for ch in CHANNELS:
        c = rep["by_channel"][ch]
        w("%-28s %6d %8d\n" % (ch, c["sites"], c["tainted"]))
    w("%-28s %6d %8d\n" % ("total", rep["sites_total"], rep["tainted_total"]))
    w("October figure: %d (a record, not compared)\n" % rep["october_figure"])
    w("sites:\n")
    for s in rep["sites"]:
        mark = "TAINTED" if s["tainted"] else "clean"
        extra = ""
        if s["via"]:
            extra = " (%s)" % s["via"]
        w(
            "  %s:%d [%s] %s %s%s\n"
            % (s["file"], s["line"], s["channel"], mark, s["surface"], extra)
        )
    w(
        "distinct places that show the text (the lines a fix changes): %d\n"
        % len(rep["fix_points"])
    )
    w("not followed (informational, not counted): %d\n" % len(rep["not_followed"]))
    for u in rep["not_followed"]:
        w("  %s:%d %s\n" % (u["file"], u["line"], u["callee"]))


def main(argv=None):
    """Entry point; returns the exit code."""
    ap = argparse.ArgumentParser(
        description="Find where a caught exception's text reaches the user."
    )
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--root", default=os.path.join("pixelart_creator", "ui"))
    ap.add_argument("--json", action="store_true", dest="as_json")
    args = ap.parse_args(argv)

    if not args.paths and not os.path.isdir(args.root):
        sys.stderr.write("check_exception_text: root not found: %r\n" % args.root)
        return 2
    for p in args.paths:
        if not os.path.isfile(p):
            sys.stderr.write("check_exception_text: path not found: %r\n" % p)
            return 2

    files = collect(args.paths, args.root)
    if not files:
        sys.stderr.write("check_exception_text: nothing examined (no .py file)\n")
        sys.stdout.write(
            "check_exception_text: files examined 0, nothing examined\n"
            "October figure: %d (a record, not compared)\n" % OCTOBER_FIGURE
        )
        return 1
    try:
        rep = build_report(files)
    except (SyntaxError, OSError, UnicodeDecodeError) as exc:
        sys.stderr.write("check_exception_text: cannot examine: %r\n" % (exc,))
        return 2

    if args.as_json:
        sys.stdout.write(json.dumps(rep, indent=2, sort_keys=True) + "\n")
    else:
        print_human(rep, sys.stdout)
    if rep["tainted_total"]:
        sys.stderr.write(
            "check_exception_text: %d tainted site(s) of %d\n"
            % (rep["tainted_total"], rep["sites_total"])
        )
        return 1
    if rep["sites_total"] == 0:
        sys.stderr.write("check_exception_text: no site found in the files examined\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
