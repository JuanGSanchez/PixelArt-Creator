# The AI assistant — chat to drive the editor

The **AI assistant** lets you drive the editor in **plain language**. You type what you want
in a chat panel, and the assistant carries it out by running the app's **own** operations —
the same [automation](automation-and-scripting.md) commands you can record, script and batch by
hand. It is **model-agnostic**: you point it at any AI provider you like and supply your own
key. It is also **optional** — the app is fully usable without ever configuring it.

> **The assistant acts through the safe automation layer — nothing new is exposed.** Every
> action the assistant takes is an ordinary, allow-listed editor operation dispatched through
> the **same trusted, `eval`-free command layer** that macros and scripts use. It cannot run
> arbitrary code, reach past that command layer, or invent new powers — a chat message is
> **data**, never a licence to do something the editor cannot already do safely.

## Opening the assistant

Open the chat panel from the **Assistant** menu. It appears as a **dockable panel** you can
place beside the canvas, so you can watch the assistant work while your artwork stays in view.
The panel shows the running conversation — your messages, the assistant's replies, and the
edits it makes to the document.

Before the assistant can talk to a provider you first **configure one** (below). Until then it
sits in a clear **not-configured** state rather than failing — configuring a provider is a
one-time step.

## Configuring a provider and key

Open the provider configuration dialog from the **Assistant** menu. The assistant is
**model-agnostic**, so you choose the service and model that suit you and enter:

| Field | What to enter |
| --- | --- |
| **Provider type** | Either an **OpenAI-compatible** service or **Anthropic**. The OpenAI-compatible option covers a wide range of endpoints (OpenAI itself, Gemini's OpenAI-compatible endpoint, and local runtimes such as Ollama or llama.cpp); the Anthropic option talks to Claude natively. |
| **Base URL / endpoint** | The service's API endpoint. Point this at a hosted provider or at a local model server on your own machine. |
| **Model** | The model name to use, as named by your chosen provider. |
| **API key** | Your key for the provider (where the provider requires one — a local model server may not). |

Select **Connect** to make the provider active for the session.

> **Your key is stored securely — never in your project.** The API key you enter is handed to
> the **operating system's secure credential store (the OS keyring)**. It is **never written
> into your `.pixproj` project file, never logged, and never travels with a shared or exported
> project**. Sharing a project therefore never shares your key. Live key access uses an
> optional extra (`pip install ".[assistant_live]"`); see the README.

> **Credential-optional.** The assistant is entirely opt-in. If you never configure a provider,
> nothing about the rest of the editor changes — you simply do not use the assistant. There is
> no forced sign-in and no key is required to use PixelArt Creator.

## Chatting to drive the workflow

With a provider connected, type a request in natural language — for example, asking the
assistant to recolour a region or to generate some procedural content — and send it. The
assistant interprets your request, decides which editor operations achieve it, and runs them,
reporting back in the transcript what it did. Because it is driving the **real** editor
operations, the results are exactly what you would get by performing those steps yourself.

A model round-trip runs on a **background worker**, so the window stays responsive while the
assistant is thinking; a long request can be cancelled.

## Tiered safety — reversible auto-runs, destructive asks first

The assistant classifies every action it wants to take into one of two tiers, and the tier
decides whether it needs your confirmation. This gate lives in the app's own code — it is
**not** something the AI model decides, and no wording in a chat message can talk the editor
out of it.

- **Reversible actions apply straight away.** An action that goes onto the normal
  [undo stack](app-basics.md) as a single, cleanly undoable step (such as a batch recolour or a
  procedural fill) is **applied without asking**. You see it happen in the document, and you can
  **undo it** like any other edit.
- **Destructive actions ask first.** Anything not on the reversible list is treated as
  **destructive by default** and the assistant **pauses to ask you**, naming the exact action.
  It runs **only** if you confirm, and is cancelled otherwise — a destructive action is never
  applied silently.

> **Safe by default.** The gate defaults to *asking* for anything it does not positively know to
> be cleanly reversible. That means a new or unusual action can never slip through and auto-run
> just because nobody classified it — the reversible tier is a small, explicit set, and
> everything else earns a confirmation prompt.

## What the assistant will not do

- **It cannot run arbitrary code.** The assistant drives only the editor's allow-listed
  operations through the trusted command layer; there is no `eval`/`exec` on this path, exactly
  as for [macros and scripts](automation-and-scripting.md).
- **It cannot bypass the confirmation gate.** No instruction — including one that arrives inside
  a tool result — can make a destructive action skip its confirmation, and no non-permitted
  operation can be run just because the conversation asks for it.
- **It never leaks your key.** Your credentials stay in the OS keyring and are used only to talk
  to the provider you configured.

## Accessibility, themes & language

Every control in the assistant panel and the provider dialog has an accessible name and is
reachable from the keyboard, all labels are fully translatable and retranslate live when you
switch language, and both surfaces render correctly in the light and dark themes.

## Related topics

- The assistant drives the same operations as the rest of the
  [automation system](automation-and-scripting.md) — macros, scripts, batch recolour and
  procedural generation.
- Configuring a provider mirrors the credential-optional, keyring-backed pattern used for
  [cloud storage](cloud-and-collaboration.md).
