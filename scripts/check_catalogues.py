#!/usr/bin/env python
# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Lint Qt translation catalogues, translation worklists and plural awareness.

Standalone script, stdlib only, maintained by the localisation owner. It is
read by the localisation gates and may be run by CI. Three modes share one
rule set:

``check_catalogues.py CATALOGUE [CATALOGUE ...] [--source EN.ts] [--json]``
    Lint each catalogue. The denominator printed per catalogue is its number
    of LIVE messages: a message whose translation is marked ``vanished`` or
    ``obsolete`` is excluded. A catalogue whose language equals its source
    language is an identity catalogue: its untranslated messages are expected,
    so the unfinished and empty checks are skipped for it.

``check_catalogues.py worklist FILE --catalogue TS [--json]``
    Lint a translation worklist (JSON) against the catalogue it was exported
    from, entry by entry, with the same per-message rules.

``check_catalogues.py inventory-plurals --catalogue EN.ts --py-dir DIR [--json]``
    List live English messages that bear a count but are not plural aware.

Per-message rules: unfinished; empty but finished; message absent from the
source catalogue; placeholder parity (``%1``..``%99``, ``%n``, ``%L1``);
markup tag and entity parity; ``&&`` pair parity; no lone ``&`` in a
translation (an ``&`` that is not half of ``&&``; the access-key marker is
placed by the application, never typed by a translator); the catalogue's
``language`` attribute equals the code in its file name (the numerus form
count is derived from it); numerus form count equals the language's Qt count,
with no empty form; line-break parity (the count of real line breaks in each
translated form equals the source's); no literal escape (a backslash followed
by ``n``, ``t``, ``r`` or a second backslash, written as characters, is
refused unless the source carries it as often).

Every mode prints how many items it examined and exits 1 when that is zero.

Exit codes: 0 clean; 1 findings reported, or nothing examined; 2 usage or
read error.
"""

import argparse
import ast
import collections
import dataclasses
import json
import os
import re
import sys
import xml.etree.ElementTree as ET

EXIT_OK = 0
EXIT_FINDINGS = 1
EXIT_ERROR = 2

# Number of plural forms Qt uses per language (primary language subtag).
NUMERUS_FORMS = {
    "en": 2,
    "es": 2,
    "fr": 2,
    "de": 2,
    "ru": 3,
    "zh": 1,
    "ko": 1,
    "ja": 1,
}

DEAD_KINDS = ("vanished", "obsolete")

PLACEHOLDER = re.compile(r"%L?(?:[1-9][0-9]?|n)")
COUNT_PLACEHOLDER = re.compile(r"%L?n$")
ENTITY = re.compile(r"&(?:[A-Za-z][A-Za-z0-9]*|#[0-9]+|#[xX][0-9A-Fa-f]+);")
TAG = re.compile(r"<(/?)([A-Za-z][A-Za-z0-9]*)[^<>]*?(/?)>")
LITERAL_ESCAPE = re.compile(r"\\[ntr\\]")
OPTIONAL_PLURAL = re.compile(r"[A-Za-z]\((?:s|es|ies)\)")
COUNT_WORDS = frozenset(
    {"n", "num", "nb", "count", "counts", "total", "number", "len", "frames"}
)
FILLERS = frozenset({"arg", "replace", "format"})

# A placeholder: ``%1``, ``%L1``, ``{name}``, ``{0}`` or ``{0:.0f}``.
ANY_PLACEHOLDER = r"(?:%L?[1-9][0-9]?|\{[A-Za-z_0-9]*(?::[^}]*)?\})"
# A plural noun that a number agrees with. A placeholder written right before
# one of these is a count, whatever the argument is called. Units
# that are symbols (``ms``, ``px``, ``PPI``) are deliberately absent: they do
# not inflect.
COUNTED_NOUNS = (
    "assets|bytes|changes|colours|colors|edits|entries|files|frames|images|"
    "items|layers|members|milliseconds|minutes|objects|operations|palettes|"
    "pixels|references|regions|seconds|steps|tags|targets|tiles|tracks"
)
COUNTED_NOUN = re.compile(ANY_PLACEHOLDER + r"\s+(?:" + COUNTED_NOUNS + r")\b")
# The two forms in which a number stands beside no noun it could agree with:
# a closing ``label: N`` and ``N of M``.
LABEL_TAIL = r":\s*{token}\s*\.?\s*$"
INDEX_OF_TOTAL = (
    r"{token}\s+of\s+" + ANY_PLACEHOLDER,  # portability: ok (regex)
    ANY_PLACEHOLDER + r"\s+of\s+{token}",  # portability: ok (regex)
)
WRAPPERS = frozenset({"str", "int", "float", "round", "abs"})


class CatalogueError(Exception):
    """Raised when a catalogue, worklist or source tree cannot be read."""


@dataclasses.dataclass(frozen=True)
class Message:
    """One ``<message>`` of a catalogue."""

    context: str
    source: str
    disambiguation: str
    extra_comment: str
    numerus: bool
    kind: str
    forms: tuple
    location: str

    @property
    def live(self) -> bool:
        """Return True unless the translation is vanished or obsolete."""
        return self.kind not in DEAD_KINDS

    @property
    def key(self) -> tuple:
        """Return the identity Qt gives the message."""
        return (self.context, self.source, self.disambiguation)


@dataclasses.dataclass(frozen=True)
class Catalogue:
    """A parsed ``.ts`` file."""

    path: str
    language: str
    source_language: str
    messages: tuple

    @property
    def identity(self) -> bool:
        """Return True when the catalogue translates into its own source."""
        return bool(self.language) and self.language == self.source_language

    def live_messages(self) -> list:
        """Return the live messages."""
        return [m for m in self.messages if m.live]


def _read_message(context: str, element) -> Message:
    """Build a Message from a ``<message>`` element."""
    numerus = element.get("numerus") == "yes"
    translation = element.find("translation")
    kind = ""
    forms: list = []
    if translation is not None:
        kind = translation.get("type") or ""
        if numerus:
            forms = [f.text or "" for f in translation.findall("numerusform")]
        else:
            forms = [translation.text or ""]
    location = element.find("location")
    where = ""
    if location is not None:
        where = f"{location.get('filename', '')}:{location.get('line', '')}"
    return Message(
        context=context,
        source=element.findtext("source") or "",
        disambiguation=element.findtext("comment") or "",
        extra_comment=element.findtext("extracomment") or "",
        numerus=numerus,
        kind=kind,
        forms=tuple(forms),
        location=where,
    )


def load_catalogue(path: str) -> Catalogue:
    """Parse a ``.ts`` file, reading it in binary."""
    try:
        with open(path, "rb") as handle:
            data = handle.read()
        root = ET.fromstring(data)
    except (OSError, ET.ParseError) as exc:
        raise CatalogueError(f"{path}: {exc}") from exc
    if root.tag != "TS":
        raise CatalogueError(f"{path}: root element is <{root.tag}>, not <TS>")
    messages = []
    for context in root.iter("context"):
        name = context.findtext("name") or ""
        for element in context.findall("message"):
            messages.append(_read_message(name, element))
    return Catalogue(
        path=path,
        language=root.get("language") or "",
        source_language=root.get("sourcelanguage") or "en",
        messages=tuple(messages),
    )


def expected_forms(language: str):
    """Return the Qt plural form count for a language code, or None."""
    primary = re.split(r"[_-]", language)[0] if language else ""
    return NUMERUS_FORMS.get(primary)


def file_code(path: str):
    """Return the language code carried by a catalogue file name, or None."""
    stem = os.path.splitext(os.path.basename(path))[0]
    if "_" not in stem:
        return None
    return stem.split("_", 1)[1]


def _placeholders(text: str, numerus: bool) -> collections.Counter:
    """Count the placeholders of a text, ignoring ``%n`` for plural messages."""
    found = PLACEHOLDER.findall(text)
    if numerus:
        found = [p for p in found if not COUNT_PLACEHOLDER.match(p)]
    return collections.Counter(found)


def _tags(text: str) -> collections.Counter:
    """Count markup tags by name, closing flag and self-closing flag."""
    return collections.Counter(
        f"<{close}{name.lower()}{selfclose}>"
        for close, name, selfclose in TAG.findall(text)
    )


def _ampersands(text: str) -> tuple:
    """Return the number of ``&&`` pairs and of lone ``&`` outside entities."""
    stripped = ENTITY.sub("", text)
    return stripped.count("&&"), stripped.replace("&&", "").count("&")


def _line_breaks(text: str) -> int:
    """Return the number of real line breaks in a text (CRLF counts once)."""
    return text.replace("\r\n", "\n").replace("\r", "\n").count("\n")


def _show(counter: collections.Counter) -> str:
    """Render a Counter for a message."""
    return ", ".join(sorted(counter.elements())) or "none"


def _parity(source: str, text: str, numerus: bool) -> list:
    """Return the parity problems of one translated form against its source."""
    problems = []
    src_ph, tr_ph = _placeholders(source, numerus), _placeholders(text, numerus)
    if src_ph != tr_ph:
        problems.append(
            (
                "placeholders",
                f"source has [{_show(src_ph)}], translation has [{_show(tr_ph)}]",
            )
        )
    src_tags, tr_tags = _tags(source), _tags(text)
    if src_tags != tr_tags:
        problems.append(
            (
                "markup",
                f"source tags [{_show(src_tags)}], translation tags "
                f"[{_show(tr_tags)}]",
            )
        )
    src_ent = collections.Counter(ENTITY.findall(source))
    tr_ent = collections.Counter(ENTITY.findall(text))
    if src_ent != tr_ent:
        problems.append(
            (
                "entities",
                f"source has [{_show(src_ent)}], translation has [{_show(tr_ent)}]",
            )
        )
    src_pairs, _ = _ampersands(source)
    tr_pairs, tr_lone = _ampersands(text)
    if src_pairs != tr_pairs:
        problems.append(
            (
                "ampersand-pairs",
                f"source has {src_pairs} '&&', translation has {tr_pairs}",
            )
        )
    if tr_lone:
        problems.append(
            (
                "lone-ampersand",
                f"translation has {tr_lone} '&' that is not part of '&&'",
            )
        )
    src_breaks, tr_breaks = _line_breaks(source), _line_breaks(text)
    if src_breaks != tr_breaks:
        problems.append(
            (
                "line-break-parity",
                f"source has {src_breaks} line break(s), translation has {tr_breaks}",
            )
        )
    extra = collections.Counter(LITERAL_ESCAPE.findall(text))
    extra.subtract(collections.Counter(LITERAL_ESCAPE.findall(source)))
    extra = +extra
    if extra:
        problems.append(
            (
                "literal-escape",
                "translation has literal backslash sequence(s) the source lacks: "
                + ", ".join(f"{k} x{v}" for k, v in sorted(extra.items())),
            )
        )
    return problems


def entry_problems(
    source: str,
    forms,
    numerus: bool,
    plural_forms,
    finished: bool = True,
) -> list:
    """Return ``(check, detail)`` problems for one message's translation forms.

    ``plural_forms`` is the language's Qt form count (None when unknown). A
    message that is not finished is only checked for its form count.
    """
    problems = []
    wanted = plural_forms if numerus else 1
    if wanted is not None and len(forms) != wanted:
        problems.append(
            ("numerus-forms", f"{len(forms)} form(s) present, {wanted} required")
        )
    if not finished:
        return problems
    for index, text in enumerate(forms):
        label = f"form {index + 1}: " if numerus else ""
        if not text.strip():
            problems.append(("empty", f"{label}translation is empty"))
            continue
        problems.extend(
            (check, label + detail) for check, detail in _parity(source, text, numerus)
        )
    return problems


def _finding(check: str, message=None, detail: str = "") -> dict:
    """Build one finding record."""
    return {
        "check": check,
        "context": message.context if message else None,
        "source": message.source if message else None,
        "detail": detail,
    }


def lint_catalogue(catalogue: Catalogue, source_keys=None) -> dict:
    """Lint one catalogue and return its record (denominator, findings)."""
    live = catalogue.live_messages()
    findings = []
    code = file_code(catalogue.path)
    if not catalogue.language:
        findings.append(_finding("language-attribute", None, "no language attribute"))
    elif code is None:
        findings.append(
            _finding(
                "language-attribute",
                None,
                f"cannot read a language code from the file name "
                f"{os.path.basename(catalogue.path)!r}",
            )
        )
    elif code != catalogue.language:
        findings.append(
            _finding(
                "language-attribute",
                None,
                f"language attribute {catalogue.language!r} differs from the "
                f"file code {code!r}",
            )
        )
    plural_forms = expected_forms(catalogue.language)
    if catalogue.language and plural_forms is None:
        findings.append(
            _finding(
                "language-unknown",
                None,
                f"no Qt plural form count is known for {catalogue.language!r}",
            )
        )
    if not live:
        findings.append(_finding("nothing-examined", None, "no live messages"))
    for message in live:
        if source_keys is not None and message.key not in source_keys:
            findings.append(_finding("absent-from-source", message, message.location))
        pending = message.kind == "unfinished"
        if pending and not catalogue.identity:
            findings.append(_finding("unfinished", message, message.location))
        finished = not pending
        for check, detail in entry_problems(
            message.source, message.forms, message.numerus, plural_forms, finished
        ):
            if pending and catalogue.identity and check == "empty":
                continue
            findings.append(_finding(check, message, detail))
    return {
        "path": catalogue.path,
        "language": catalogue.language,
        "file_code": code,
        "identity": catalogue.identity,
        "examined": len(live),
        "excluded_vanished_or_obsolete": len(catalogue.messages) - len(live),
        "findings": findings,
    }


def lint_worklist(worklist: dict, catalogue: Catalogue) -> dict:
    """Lint a worklist's entries against the catalogue they were exported from."""
    findings = []
    entries = worklist.get("entries")
    if worklist.get("schema") != 1:
        findings.append(_finding("worklist-schema", None, "schema is not 1"))
    if not isinstance(entries, list):
        entries = []
        findings.append(_finding("worklist-schema", None, "no entries list"))
    if worklist.get("language") != catalogue.language:
        findings.append(
            _finding(
                "language-attribute",
                None,
                f"worklist language {worklist.get('language')!r} differs from the "
                f"catalogue's {catalogue.language!r}",
            )
        )
    named = worklist.get("source_catalogue")
    if named != os.path.basename(catalogue.path):
        findings.append(
            _finding(
                "worklist-catalogue",
                None,
                f"worklist names {named!r}, checked against "
                f"{os.path.basename(catalogue.path)!r}",
            )
        )
    plural_forms = expected_forms(catalogue.language)
    index = {m.key: m for m in catalogue.live_messages()}
    seen = set()
    for number, entry in enumerate(entries, start=1):
        stub = dataclasses.replace(
            _blank_message(),
            context=str(entry.get("context") or ""),
            source=str(entry.get("source") or ""),
        )
        where = f"entry {number}"
        key = (stub.context, stub.source, entry.get("disambiguation") or "")
        if key in seen:
            findings.append(_finding("duplicate-entry", stub, where))
        seen.add(key)
        message = index.get(key)
        if message is None:
            findings.append(
                _finding("unknown-key", stub, f"{where}: not a live message")
            )
            continue
        if bool(entry.get("numerus")) != message.numerus:
            findings.append(
                _finding("numerus-flag", stub, f"{where}: differs from catalogue")
            )
        comment = entry.get("comment")
        if comment is not None and comment != message.extra_comment:
            findings.append(
                _finding("comment-mismatch", stub, f"{where}: differs from catalogue")
            )
        forms = entry.get("translation")
        if not isinstance(forms, list) or not all(isinstance(f, str) for f in forms):
            findings.append(
                _finding("worklist-schema", stub, f"{where}: translation not a list")
            )
            continue
        required = plural_forms if message.numerus else 1
        if entry.get("forms_required") != required and required is not None:
            findings.append(
                _finding(
                    "numerus-forms",
                    stub,
                    f"{where}: forms_required {entry.get('forms_required')!r}, "
                    f"language needs {required}",
                )
            )
        for check, detail in entry_problems(
            message.source, forms, message.numerus, plural_forms
        ):
            findings.append(_finding(check, stub, f"{where}: {detail}"))
    if not entries:
        findings.append(_finding("nothing-examined", None, "no worklist entries"))
    return {
        "path": catalogue.path,
        "language": catalogue.language,
        "examined": len(entries),
        "findings": findings,
    }


def _blank_message() -> Message:
    """Return an empty Message used to label worklist findings."""
    return Message("", "", "", "", False, "", (), "")


def _call_name(node: ast.Call):
    """Return the called function's simple name, or None."""
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    if isinstance(node.func, ast.Name):
        return node.func.id
    return None


def _translated_literal(node: ast.AST):
    """Return ``(text, plural_aware)`` when ``node`` is a literal tr() call."""
    if not isinstance(node, ast.Call):
        return None
    name = _call_name(node)
    if name == "tr":
        at = 0
    elif name == "translate":
        at = 1
    else:
        return None
    if len(node.args) <= at:
        return None
    literal = node.args[at]
    if not (isinstance(literal, ast.Constant) and isinstance(literal.value, str)):
        return None
    aware = len(node.args) > at + 2 or any(k.arg == "n" for k in node.keywords)
    return literal.value, aware


def _count_like(expression: ast.AST) -> bool:
    """Return True when an argument expression plausibly carries a count."""
    while (
        isinstance(expression, ast.Call)
        and _call_name(expression) in WRAPPERS
        and expression.args
    ):
        expression = expression.args[0]
    if isinstance(expression, ast.Call) and _call_name(expression) == "len":
        return True
    name = None
    if isinstance(expression, ast.Name):
        name = expression.id
    elif isinstance(expression, ast.Attribute):
        name = expression.attr
    if name is None:
        return False
    lowered = name.lower().lstrip("_")
    return bool(COUNT_WORDS.intersection(lowered.split("_"))) or lowered.endswith(
        "count"
    )


def _filled_tokens(call: ast.Call, position: int) -> list:
    """Return the placeholder tokens a count-like fill call supplies.

    ``position`` is the number of ``arg()`` values applied before this call.
    The tokens are alternatives: any one of them marks a count-bearing text.
    """
    tokens = []
    name = call.func.attr
    if name == "arg":
        for offset, value in enumerate(call.args):
            if _count_like(value):
                tokens.extend(
                    [f"%{position + offset + 1}", f"%L{position + offset + 1}"]
                )
    elif name == "replace" and len(call.args) >= 2:
        marker, value = call.args[0], call.args[1]
        if (
            isinstance(marker, ast.Constant)
            and isinstance(marker.value, str)
            and PLACEHOLDER.fullmatch(marker.value)
            and _count_like(value)
        ):
            tokens.append(marker.value)
    elif name == "format":
        for keyword in call.keywords:
            if keyword.arg and _count_like(keyword.value):
                tokens.append("{" + keyword.arg)
    return tokens


def _scan_file(path: str, root: str) -> list:
    """Return the count-bearing tr().arg() sites of one Python file."""
    try:
        with open(path, "rb") as handle:
            tree = ast.parse(handle.read(), filename=path)
    except (OSError, SyntaxError, ValueError) as exc:
        raise CatalogueError(f"{path}: {exc}") from exc
    relative = os.path.relpath(path, root).replace(os.sep, "/")
    sites = []
    inner = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or id(node) in inner:
            continue
        fills = []
        current = node
        while (
            isinstance(current, ast.Call)
            and isinstance(current.func, ast.Attribute)
            and current.func.attr in FILLERS
        ):
            inner.add(id(current))
            fills.append(current)
            current = current.func.value
        inner.add(id(current))
        translated = _translated_literal(current)
        if translated is None:
            continue
        text, aware = translated
        tokens = []
        position = 0
        for fill in reversed(fills):
            tokens.extend(_filled_tokens(fill, position))
            if fill.func.attr == "arg":
                position += len(fill.args)
        counted = tokens
        sites.append(
            {
                "text": text,
                "aware": aware,
                "file": relative,
                "line": current.lineno,
                "count_placeholders": counted,
            }
        )
    return sites


def _agreement_free(source: str, tokens: list) -> str:
    """Return why every counted token of ``source`` has no noun, or ''.

    A number written as ``label: N`` at the end of a text, or as ``N of M``,
    stands beside no noun whose form could change with it. The reason is
    returned only when EVERY counted token present in the text is of that
    kind; one token that sits before a noun keeps the message listed.
    """
    present = [t for t in tokens if t in source]
    reasons = set()
    for token in present:
        escaped = re.escape(token)
        if re.search(LABEL_TAIL.replace("{token}", escaped), source):
            reasons.add("label-colon")
        elif any(
            re.search(form.replace("{token}", escaped), source)
            for form in INDEX_OF_TOTAL
        ):
            reasons.add("index-of-total")
        else:
            return ""
    return "+".join(sorted(reasons))


def _is_listed(entry: dict, listed: list) -> bool:
    """Return True when another rule lists the message of ``entry`` anyway."""
    return any(
        item["context"] == entry["context"] and item["source"] == entry["source"]
        for item in listed
    )


def inventory_plurals(catalogue: Catalogue, py_dir: str) -> dict:
    """List count-bearing live messages that are not plural aware.

    The rules are fixed and run over the English catalogue and the tr() call
    sites found under ``py_dir``. A count-argument hit whose placeholders all
    stand in a ``label: N`` or ``N of M`` form is not listed but is reported
    under ``excluded`` with its reason; a message no other rule lists whose
    placeholder precedes a plural noun is listed as ``counted-noun``.
    """
    live = catalogue.live_messages()
    sites = []
    files = 0
    for folder, _dirs, names in os.walk(py_dir):
        for name in sorted(n for n in names if n.endswith(".py")):
            files += 1
            sites.extend(_scan_file(os.path.join(folder, name), py_dir))
    by_text = collections.defaultdict(list)
    for site in sites:
        by_text[site["text"]].append(site)
    listed = []
    excluded = []
    for message in live:
        if message.numerus:
            continue
        rules = []
        if re.search(r"%L?n", message.source):
            rules.append("percent-n-without-numerus")
        if OPTIONAL_PLURAL.search(message.source):
            rules.append("optional-plural-suffix")
        sites_here = [
            s
            for s in by_text.get(message.source, [])
            if not s["aware"]
            and any(t in message.source for t in s["count_placeholders"])
        ]
        kept = []
        for site in sites_here:
            reason = _agreement_free(message.source, site["count_placeholders"])
            if not reason:
                kept.append(site)
            elif not any(e["source"] == message.source for e in excluded):
                excluded.append(
                    {
                        "context": message.context,
                        "source": message.source,
                        "reason": reason,
                        "call_sites": [f"{site['file']}:{site['line']}"],
                    }
                )
        sites_here = kept
        if sites_here:
            rules.append("count-argument")
        if not rules and COUNTED_NOUN.search(message.source):
            rules.append("counted-noun")
        if rules:
            listed.append(
                {
                    "context": message.context,
                    "source": message.source,
                    "rules": rules,
                    "location": message.location,
                    "call_sites": [f"{s['file']}:{s['line']}" for s in sites_here],
                }
            )
    return {
        "path": catalogue.path,
        "examined": len(live),
        "python_files": files,
        "call_sites": len(sites),
        "listed": listed,
        "excluded": [e for e in excluded if not _is_listed(e, listed)],
    }


def _clip(text, width: int = 70) -> str:
    """Shorten a string for one-line display."""
    text = " ".join((text or "").split())
    return text if len(text) <= width else text[: width - 3] + "..."


def _print_findings(record: dict, out) -> None:
    """Print a record's header and findings as text."""
    print(f"{record['path']}: examined {record['examined']}", file=out)
    for finding in record["findings"]:
        subject = (
            f" [{finding['context']}] {_clip(finding['source'])}"
            if (finding["source"] is not None)
            else ""
        )
        print(f"  {finding['check']}:{subject} {finding['detail']}", file=out)


def _finish(report: dict, as_json: bool) -> int:
    """Print the report, then return the exit code it implies."""
    code = report["exit"]
    if as_json:
        print(json.dumps(report, indent=2, ensure_ascii=True))
    return code


def _run_lint(args) -> int:
    """Lint one or more catalogues."""
    source_keys = None
    if args.source:
        source = load_catalogue(args.source)
        source_keys = {m.key for m in source.live_messages()}
    records = []
    for path in args.catalogues:
        record = lint_catalogue(
            load_catalogue(path),
            (
                None
                if source_keys is not None and _same_file(path, args.source)
                else source_keys
            ),
        )
        records.append(record)
    examined = sum(r["examined"] for r in records)
    total = sum(len(r["findings"]) for r in records)
    code = EXIT_FINDINGS if total or examined == 0 else EXIT_OK
    report = {
        "mode": "lint",
        "source": args.source,
        "catalogues": records,
        "examined_total": examined,
        "findings_total": total,
        "exit": code,
    }
    if not args.json:
        for record in records:
            _print_findings(record, sys.stdout)
        print(f"examined {examined} live message(s), {total} finding(s)")
        if examined == 0:
            print("nothing examined")
    return _finish(report, args.json)


def _same_file(first: str, second: str) -> bool:
    """Return True when two paths name the same file."""
    return os.path.normcase(os.path.abspath(first)) == os.path.normcase(
        os.path.abspath(second)
    )


def _run_worklist(args) -> int:
    """Lint a worklist against its catalogue."""
    try:
        with open(args.worklist, "rb") as handle:
            worklist = json.loads(handle.read().decode("utf-8"))
    except (OSError, ValueError) as exc:
        raise CatalogueError(f"{args.worklist}: {exc}") from exc
    if not isinstance(worklist, dict):
        raise CatalogueError(f"{args.worklist}: not a JSON object")
    record = lint_worklist(worklist, load_catalogue(args.catalogue))
    total = len(record["findings"])
    code = EXIT_FINDINGS if total or record["examined"] == 0 else EXIT_OK
    report = {
        "mode": "worklist",
        "worklist": args.worklist,
        "record": record,
        "examined_total": record["examined"],
        "findings_total": total,
        "exit": code,
    }
    if not args.json:
        _print_findings(record, sys.stdout)
        print(f"examined {record['examined']} worklist entr(ies), {total} finding(s)")
        if record["examined"] == 0:
            print("nothing examined")
    return _finish(report, args.json)


def _run_inventory(args) -> int:
    """List count-bearing messages that are not plural aware."""
    catalogue = load_catalogue(args.catalogue)
    if not catalogue.identity:
        raise CatalogueError(
            f"{args.catalogue}: the inventory runs over the source-language "
            f"catalogue, not {catalogue.language!r}"
        )
    record = inventory_plurals(catalogue, args.py_dir)
    blind = record["examined"] == 0 or record["python_files"] == 0
    code = EXIT_FINDINGS if record["listed"] or blind else EXIT_OK
    report = dict(record, mode="inventory-plurals", exit=code)
    if not args.json:
        for item in record["listed"]:
            sites = ", ".join(item["call_sites"]) or item["location"]
            print(
                f"  {','.join(item['rules'])}: [{item['context']}] "
                f"{_clip(item['source'])} ({sites})"
            )
        for item in record["excluded"]:
            print(
                f"  excluded ({item['reason']}): [{item['context']}] "
                f"{_clip(item['source'])} ({', '.join(item['call_sites'])})"
            )
        print(
            f"examined {record['examined']} live message(s) and "
            f"{record['call_sites']} tr() call site(s) in "
            f"{record['python_files']} file(s); {len(record['listed'])} listed"
            + (f", {len(record['excluded'])} excluded" if record["excluded"] else "")
        )
        if blind:
            print("nothing examined")
    return _finish(report, args.json)


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        epilog="Without a mode word the catalogue lint runs.",
    )
    modes = parser.add_subparsers(dest="mode", required=True)
    lint = modes.add_parser("lint", help="lint catalogues (the default mode)")
    lint.add_argument("catalogues", nargs="+", metavar="CATALOGUE")
    lint.add_argument("--source", help="source catalogue; every message must exist")
    lint.add_argument("--json", action="store_true", help="print JSON")
    lint.set_defaults(run=_run_lint)
    work = modes.add_parser("worklist", help="lint a translation worklist")
    work.add_argument("worklist", metavar="FILE")
    work.add_argument("--catalogue", required=True, help="the target catalogue")
    work.add_argument("--json", action="store_true", help="print JSON")
    work.set_defaults(run=_run_worklist)
    inv = modes.add_parser("inventory-plurals", help="list non-plural-aware counts")
    inv.add_argument("--catalogue", required=True, help="the English catalogue")
    inv.add_argument("--py-dir", required=True, help="Python source tree to scan")
    inv.add_argument("--json", action="store_true", help="print JSON")
    inv.set_defaults(run=_run_inventory)
    return parser


def main(argv=None) -> int:
    """Run the requested mode and return the process exit code."""
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] not in (
        "lint",
        "worklist",
        "inventory-plurals",
        "-h",
        "--help",
    ):
        argv.insert(0, "lint")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = build_parser().parse_args(argv)
    try:
        return args.run(args)
    except CatalogueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
