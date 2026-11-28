# Security Policy

## Supported Versions

PixelArt Creator is currently in **0.x**, pre-1.0 development
(`pyproject.toml` reports `version = "0.5.0"`, classified
`Development Status :: 3 - Alpha`). Only the **latest released version**
receives security fixes; there is no long-term-support branch at this
stage. The latest released version is **0.5.0**.

| Version        | Supported           |
| -------------- | ------------------- |
| 0.5.0 (latest) | :white_check_mark:  |
| Older releases | :x:                 |

### Version 0.4.0

Security support for **0.4.0** has ended. It was the last release that
installs on Python 3.13; every later release needs Python 3.14 or newer
(see the [changelog](CHANGELOG.md)). Staying on 0.4.0 to keep Python 3.13
means running a version that no longer receives security fixes. To receive
them, use Python 3.14 or newer and upgrade to the latest release. The
packaged installers (Windows, macOS and Linux) are self-contained builds
and do not depend on the Python version of your system.

## Reporting a Vulnerability

Please **do not** open a public issue for a security vulnerability.

Report it privately using GitHub's **Private vulnerability reporting**
feature, from this repository's **Security** tab ("Report a vulnerability").
That channel goes directly to the maintainer and is not visible publicly
until a fix is available.

Please include, as far as you can:

- a description of the vulnerability and its potential impact,
- steps to reproduce it (a minimal project file, script, or input),
- the affected version/commit and your OS.

## What to expect

This project is maintained by one person. Reports will be acknowledged as
soon as practical, and a fix or mitigation will be prioritized for
confirmed vulnerabilities. There is no guaranteed response-time SLA at this
stage of the project, but private reports are read.

If a report turns out not to be exploitable or is out of scope, you will
still get a reply explaining why.
