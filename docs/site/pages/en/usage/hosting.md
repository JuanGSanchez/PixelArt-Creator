<!-- REQ-P13-BACKEND-003 -->
<!-- surface-only: site — deployment/installation content; split out of the bundle's collaboration.md "Operator note: running the sync backend" section, which stays the bundle's single mention of this material (WP-8 unit 2d) -->
# Hosting the real-time relay: three co-equal options

Real-time collaboration (live co-editing, cursors, and branching) is carried by
a small **sync backend** relay (see the
[Real-time co-editing](collaboration.md#real-time-co-editing) section of the
Shared projects guide). Where that relay runs is **your choice**, and the
platform ships **three co-equal hosting options** — none of them is a
"recommended" or "production" default, and picking one changes **nothing**
about the app or backend itself.

!!! important "No forced default"
    The app's collaboration behaviour is identical no matter which option you
    use, including if you use none of them: the shipped default is
    **local / loopback**, and adopting either of the other two options requires
    **no code change** to the app or the backend (`REQ-P13-BACKEND-003`).

## Option 1 — Local / loopback (the shipped default)

Nothing to set up. The relay's default bind is `127.0.0.1` (loopback), and this
is what the app uses out of the box — single machine, local testing, or offline
use. This is the baseline every other option is measured against, and it is
fully exercised end to end by the automated test suite.

## Option 2 — Cloud provider-adapter

Collaboration can also flow through the same **provider-agnostic cloud port**
used for single-user cloud saves (see the [Cloud](cloud.md) guide): the
built-in in-memory adapter by default, or a real Google Drive / OneDrive /
Dropbox account behind the identical Connect flow. Pick this option if you
already route projects through a cloud provider and want collaboration to
follow the same path — everything is driven from the in-app **Cloud** menu, so
no server administration is required on your part. See
[Connecting a cloud provider](cloud.md#connecting-a-cloud-provider) and
[Shared projects & comments](collaboration.md) for the connect / share
workflow.

## Option 3 — Self-hosted VPS

You can run the **unchanged** `sync_backend/` relay yourself, on a generic VPS
reachable over the public internet, using the deployment artifacts shipped
alongside the backend:

- **`deploy/Dockerfile`** — builds a container image that runs the relay as a
  non-root process.
- **`deploy/pixelart-sync.service`** — a systemd unit for running the relay as
  a managed service on a Linux host.
- **`deploy/nginx-sync.conf`** — an Nginx reverse-proxy configuration that
  terminates TLS and proxies WSS to the relay, with the WebSocket
  `Upgrade`/`Connection` headers and idle-timeout tuning it needs to stay
  connected.
- **`deploy/run_sync_backend.py`** — the launcher these artifacts use to start
  the relay.

!!! note "Deployment artifacts only — the backend source does not change"
    These files package and run the same `sync_backend/` relay used by the
    other two options; they do not modify it. Choosing this option is entirely
    optional and reversible, and it has no effect on anyone who does not use
    it.

!!! tip "Operator-level detail"
    Certificate provisioning, firewall rules, and other server-administration
    steps are outside the scope of this user guide. Detailed operator setup
    lives in the project's private deployment notes; the inline setup comments
    in each `deploy/` artifact above are the public-facing starting point.

## Choosing between the three

| Option | Setup effort | Good for |
| --- | --- | --- |
| Local / loopback | None — it's the default | Single machine, local testing, offline use |
| Cloud provider-adapter | Connect a provider from the Cloud menu | Teams already using a cloud provider |
| Self-hosted VPS | Deploy the `deploy/` artifacts above | Hosting the relay yourself, on your own server |

Whichever you choose (or none), the rest of the collaboration workflow —
sharing, comments, presence, real-time co-editing, and branching — behaves
exactly as documented in [Shared projects & comments](collaboration.md).
