# Lingua — The Experience

> Speak your app into existence.

This document describes Lingua through the eyes of the people who use it: what they
see on first run, how they create a project, and what each feature does for them. It is
written in two layers:

- **Part 1–2 — what's real today.** The shipped product, narrated by the one persona it
  serves now: the **Product Developer** who builds screens by talking to an agent.
- **Part 3 — where it's going.** The wider vision from
  [`product-definition.md`](../product-definition.md), told through the personas that
  vision is built for.

Features are tagged so you always know what's live versus aspirational:
🟢 **Live** · 🟡 **Coming** (placeholder already visible in the UI) · 🔵 **Vision**
(design-system engine, not yet built).

For the canonical vocabulary behind the nouns used here (Conversation, Workspace,
Credential Vault…), see [`CONTEXT.md`](../../CONTEXT.md).

---

## Who Lingua is for

| Persona | What they want | Served today? |
|---------|----------------|---------------|
| **Product Developer** (the Consumer) | Build screens by describing them; iterate fast; ship | 🟢 Yes — the whole shipped product |
| **DS Lead / Author** | Define tokens, patterns, and component-usage opinions once | 🔵 Vision |
| **Platform / Frontend Engineer** (Adapter Maintainer) | Wire adapters, manage conformance, retrofit legacy apps | 🔵 Vision |
| **Engineering Leadership** (Buyer) | One consistent look, feel, and experience across many products | 🔵 Vision |
| **OSS Contributor** | Extend adapters, contribute knowledge packs | 🔵 Vision |

---

# Part 1 — The shipped experience (Product Developer)

## Onboarding: first run

You start the stack (`docker compose up -d`) and open `http://localhost:5173`. Lingua
loads the project list — empty the first time.

**The first-run gate.** Before you can build anything, Lingua needs to know which LLM to
talk to. On first run the **System settings** drawer opens automatically and *cannot be
dismissed*; **New project** stays disabled; an inline banner reads *"Connect a model to
get started."* This is deliberate — there is no way to fall into a broken half-configured
state.

In **System settings** you fill the **Credential Vault**:

1. **Model connection** (required):
   - **Provider** — *OpenRouter*, *Local (OpenAI-compatible)*, or *Custom*.
   - **Base URL** — hidden for OpenRouter (fixed); editable for Local/Custom (e.g. an
     Ollama endpoint at `http://host.docker.internal:11434/v1`).
   - **Model** — an autocomplete that *fetches the live model list* from the provider so
     you pick a real id, with a reload button.
   - **API key** — stored encrypted; often unnecessary for local models.
2. **GitHub Personal Access Token** (optional) — only needed to create repositories and to
   Publish. Stored encrypted. (OAuth sign-in is planned.)

You click **Save**. The vault is now configured, the drawer unlocks, the banner clears,
and **New project** lights up. Onboarding is done — it's a single screen, gated so you
can't skip the one thing that matters.

> Secrets live in an encrypted, per-instance vault — *not* in environment variables. The
> old `OPENROUTER_API_KEY` / `GITHUB_TOKEN` env vars are gone.

## Creating your first project

Click **New project**. The dialog asks for:

1. **Name** — the display name on the project card.
2. **Bootstrap repo URL** — any public Vite + React scaffold to clone as your starting
   point (it must *not* ship a `.opencode/` directory — Lingua owns that). This is the
   only required repo.
3. **Where Publish will push** — one of two branches:
   - ☑ **"Create a GitHub repository for me"** — Lingua creates a fresh repo on your
     GitHub account (choose **Private/Public** and an optional description) and wires it as
     the target. Requires the GitHub PAT.
   - ☐ left unchecked — paste an existing **Target repo URL**, or leave it blank and set it
     later.

Click **Create**. Lingua clones the bootstrap repo into the project's own subdirectory and
takes you straight into the **workspace**. On first open the workspace container runs
`npm install` (~30s); the preview panel polls and flips to your live app the moment Vite
responds.

You're now looking at your app on the left-hand chat and the running app on the right.
Type a prompt — *"add a blue button"*, *"make the background a gradient"*, *"create a
counter component"* — and watch the agent edit the source while the preview hot-reloads.

## Inside the workspace

The workspace is a split view. Top-left is a header (back to projects, the Lingua
wordmark, theme toggle). Below it, an **activity switcher** and the active panel; on the
right, the **preview**.

### The activity switcher

A horizontal segmented control with four activities:

- 🟢 **Chats** — live, the only working activity today.
- 🟡 **AI Coding**, 🟡 **Create Image**, 🟡 **Deep Search** — visible but disabled. They
  are deliberate placeholders signalling where the product is expanding.

### Conversations (the Chats activity)

Each project holds many durable **Conversations** — independent chat threads.

- **New conversation** starts a fresh thread, auto-titled from your first prompt.
- Threads are **grouped by date** (Today / Yesterday / Previous 7 days / Older).
- Per-thread menu: **Rename / Archive / Delete**.
- Reopening a thread restores its *full transcript* — reasoning, every tool step, results —
  and the agent resumes with its memory intact, even after `docker compose down/up`.

### The chat itself

You type a prompt; the agent works and streams back:

- A **thought chain** — reasoning and each tool call (read, edit, write, bash) rendered
  live as collapsible steps with per-action icons and status colours; it auto-collapses
  when done.
- **Clarifying questions** — the agent can pause and ask, offering option buttons; your
  input locks until you answer.
- **Resumable streams** — close the tab mid-build and the agent keeps running; reconnecting
  replays whatever you missed.

### The preview and its toolbar

The right panel is your running app in an iframe. Across the top of the preview card:

- **Project name** and a **branch badge** showing the current git branch and live state —
  *N unsaved*, *N ahead*, *no upstream* — polled continuously.
- **Select** (the **element picker**) — toggle it, click any element in the preview, and
  its exact source location + selector is injected as the first node of your next prompt.
  No more describing *which* button.
- **Publish** — one click: stages all changes, commits with a timestamped message, and
  pushes to the target repo using the vault's PAT. If you're on `main`/`master`, Lingua
  auto-creates a `lingua/<timestamp>` branch so it never fights branch protection.

### Project settings

A gear view in the workspace edits **per-project** configuration: the **name** and the
**Target repository** (saving it also rewrites the checkout's `origin` remote). The
**Bootstrap repository** is shown but read-only — it's cloned once at creation.

### Switching projects

Each project lives in its own subdirectory; switching preserves code. If the current
project has uncommitted changes, Lingua intercepts the switch and offers to **Publish
first** or **Switch anyway** — your work is never silently lost.

---

# Part 2 — Feature catalog

## 🟢 Live today

**Onboarding & configuration**
- First-run gate that blocks project creation until a model is connected
- Encrypted Credential Vault (Model Connection + GitHub PAT), replacing env-var secrets
- Multi-provider model connection (OpenRouter / Local / Custom, all OpenAI-compatible)
- Live model listing with reload, per provider

**Projects**
- Create a project from any Vite + React bootstrap repo
- Optional one-step GitHub repo creation (private/public + description)
- Project cards (bootstrap, target, last-opened); Open and Archive
- Per-project settings: rename, edit target repo (rewrites `origin`); read-only bootstrap
- Dirty-switch guard: Publish-first or Switch-anyway when leaving unsaved work

**Building**
- Split-screen chat + live preview (Vite HMR in an iframe)
- Streaming thought-chain: reasoning + every tool call, with per-action icons/status
- Clarifying questions with option buttons and input locking
- Resumable streams that survive tab close (replay on reconnect)
- Element picker — click a preview element to inject its source/selector into the prompt
- Durable Conversations: many per project, date-grouped, rename/archive/delete, full
  transcript + agent memory replay across restarts

**Shipping**
- One-click Publish with auto `lingua/<timestamp>` branch and token-based push
- Live branch/dirty badge (branch, unsaved count, ahead, no-upstream)

**Platform**
- Pluggable agent engines behind one shared Step contract (identical UI either way)
- Same-origin nginx proxy; resizable/collapsible panels; persisted light/dark theme

## 🟡 Coming (placeholders already in the UI)

- **AI Coding** — a dedicated coding activity beyond conversational editing
- **Create Image** — image generation as a first-class activity
- **Deep Search** — codebase/knowledge search as an activity
- **OAuth GitHub sign-in** — replacing the manual PAT (noted in System settings today)

## 🔵 Vision (the design-system engine)

From [`product-definition.md`](../product-definition.md) and the
[`ROADMAP`](../ROADMAP.md) "Next" section — none of this is built yet:

- **Abstract component vocabulary** — neutral concepts (`Overlay.Blocking`,
  `Disclosure.Inline`) mapped per library
- **Adapters** — Ant Design / shadcn / Angular render targets for one shared definition
- **Token contract** — a single `tokens.json` emitted to every adapter's theming format
- **Conformance maps** — declared matches / partials / gaps per adapter (never silent)
- **Deterministic decision-tree interview** — experience questions (reversibility, data
  volume, layout) that *execute* logic to pick patterns
- **Rationale + decision log** — a "why" doc emitted alongside each generated screen
- **Opinionated seed packs** — a shipped "system zero" to solve the empty-state problem
- **Lifecycle** — DS re-ingestion on upstream changes, version history, local-override
  drift reconciliation, legacy retrofit

---

# Part 3 — Where this is going (the other personas)

Today Lingua serves the Product Developer. The vision is a **code-agnostic design-system
specification engine** where the *same* definition renders consistently across Ant, shadcn,
and Angular, and new screens are generated to conform automatically. These are the journeys
that future unlocks — aspirational, told to show the destination.

### 🔵 DS Lead / Author — defining the system

1. Points Lingua at existing component libraries / MCPs.
2. Lingua ingests the *descriptive* layer (APIs, props) automatically and proposes
   *prescriptive* scaffolding (decision trees, "use when") as editable drafts.
3. The same conversational engine interviews the Lead, who corrects and approves opinions.
4. Defines tokens once and previews them rendered through each adapter.
5. Publishes a versioned **knowledge pack**.

### 🔵 Platform Engineer — retrofitting a legacy app

1. Selects a target product and its stack (e.g. Angular).
2. Applies the token contract via that stack's adapter.
3. Reviews the **conformance map** for declared deltas.
4. Iterates until look & feel match, then commits — no rewrite.

### 🔵 Product Developer — building a *conformant* screen

The shipped flow, deepened: instead of free-form edits, Lingua interviews on **experience
decisions** (Is this reversible? How many items? Inline or dedicated page?), executes the
relevant decision trees deterministically, selects abstract components, and generates code
in the target adapter — plus a rationale doc. If a pattern you used changed upstream, Lingua
flags it mid-build.

### 🔵 Engineering Leadership — evaluating adoption

1. Sees one DS definition rendered identically across Ant + shadcn, side by side.
2. Reviews the migration/retrofit story and the maintenance model.
3. Sponsors a pilot on one painful cross-stack flow.

### 🔵 OSS Contributor — extending reach

Contributes new adapters and knowledge packs; files "opinion" PRs against the prescriptive
layer. Each new adapter expands what one Lingua definition can render.

---

## Related docs

| Topic | Where |
|-------|-------|
| Domain glossary | [`CONTEXT.md`](../../CONTEXT.md) |
| Product vision & PM analysis | [`product-definition.md`](../product-definition.md) |
| What's built / what's next | [`ROADMAP.md`](../ROADMAP.md) |
| Architecture decisions | [`adr/`](../adr/) |
| Setup & configuration | [`README.md`](../../README.md) |
