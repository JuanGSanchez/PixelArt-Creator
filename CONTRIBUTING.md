# Contributing to PixelArt Creator

Thanks for your interest in PixelArt Creator. The project is currently
maintained by a single person, so please be patient with review times —
every contribution is still read and every issue still gets a reply.

All changes go through a pull request. The `main` branch does not accept
direct pushes; the only way in is a PR from a branch, reviewed and merged
through GitHub.

## Becoming a collaborator

Issue creation on this repository is restricted to collaborators. If you'd
like to report a bug, propose a feature, or otherwise open an issue, please
first ask to become a collaborator by contacting the maintainer,
[@JuanGSanchez](https://github.com/JuanGSanchez), through the contact
options listed on their GitHub profile. Once you have collaborator access,
open issues using the templates described below.

Pull requests are welcome from anyone with collaborator access; if you are
not yet a collaborator and would like to submit one, please ask first, the
same way, before starting significant work.

## Reporting bugs and proposing features

Collaborators: please open an issue before starting significant work, so we
can agree on the approach first. Use the appropriate issue template under
`.github/ISSUE_TEMPLATE/` — bug report, feature request, performance,
translation, documentation, or task — whichever fits. A template asks for:

- what you expected to happen and what happened instead (for a bug),
- the use case a new feature would serve,
- your OS and Python version, if relevant.

## Development setup

The project targets **Python 3.13 or newer** (the repository pins an exact
interpreter, 3.13.13, via `.python-version`, which is what CI runs).

Clone the repository and install it with the development extra, which pulls
in the test and lint toolchain (pytest, black, isort, flake8, mypy,
pydocstyle, mkdocs) in addition to the runtime dependencies:

```sh
pip install -e ".[dev]"
```

### Running the tests

The full suite runs headless (no display server required):

```sh
pytest
```

This collects both the main suite (`testing/suites/`) and the web viewer's
own tests (`web_viewer/tests/`), as declared in `pyproject.toml`. A few
marker groups are deselected by default because they need something the
default environment does not provide — a GPU/display, network access, real
cloud credentials, or a real LLM provider:

```sh
pytest -m "not slow and not gpu and not cloud_live and not assistant_live and not integration"
```

Coverage is measured with `pytest --cov=pixelart_creator` and checked
against a **90% line / 80% branch** gate; see `pyproject.toml`'s
`[tool.coverage]` sections and the CI workflow for the exact invocation.

### Style and static checks

Run these before opening a PR — CI runs the same checks and will fail the
build otherwise:

```sh
black --check pixelart_creator scripts
isort --check-only pixelart_creator scripts
flake8 pixelart_creator scripts
mypy pixelart_creator
```

Docstrings follow PEP 257 (module and function level) and are checked with:

```sh
pydocstyle pixelart_creator
```

If you touch `docs/site/`, verify the documentation site still builds:

```sh
mkdocs build -f docs/site/mkdocs.yml --strict
```

### Commit messages and branch names

Commits follow [Conventional Commits](https://www.conventionalcommits.org/)
(`feat: …`, `fix: …`, `docs: …`, `refactor: …`, `test: …`, `chore: …`).

Branches are named `feat-<slug>`, `fix-<slug>`, `chore-<slug>` or
`docs-<slug>` — a hyphen, never a slash — matching the type of change.

### Layering

The codebase keeps a strict three-layer split: `ui/` (PySide6, all Qt
code), `logic/` (pure Python, no Qt), and `data/` (I/O, no Qt). Domain
behaviour belongs in `logic/`/`data/` so it stays unit-testable headless;
please keep new code on the correct side of that line.

### Translations

User-facing strings are wrapped in `tr()`/`translate()` and extracted into
Qt `.ts` catalogues (`pixelart_creator/i18n/`) compiled to `.qm` at build
time. If you add or change a user-visible string in `ui/`, make sure it is
wrapped for translation; catalogue extraction and compilation are handled
by the project's own tooling rather than by hand-editing `.ts`/`.qm` files
in a PR.

## Questions

If something here doesn't work as described and you are a collaborator,
please open an issue — that usually means the docs are out of date, which
is itself worth reporting. If you are not yet a collaborator, contact the
maintainer as described above.
