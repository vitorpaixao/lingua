# Lingua — Product Definition & Analysis

> Speak your app into existence.

*An open-source, code-agnostic design system specification engine and conversational app builder.*

---

## 1. What Lingua Is

Lingua is an open-source project that treats a **design system as an abstraction** and treats code libraries (Ant Design, shadcn/ui, Angular Material, etc.) as **interchangeable render targets** for that abstraction.

Lingua's definition of a design system is deliberately code-agnostic:

- **Look & feel** — foundations and tokens
- **Experience** — patterns (layout, navigation, flows) and component usage (which abstract component, when, and why)

Code is downstream and swappable. The same Lingua definition should produce the same look, feel, and experience whether rendered through Ant Design or shadcn — accepting small, *declared* deltas where the underlying code genuinely differs.

In one line: **Lingua is a design system specification language, and the component libraries are its compile targets.**

### Two products in one engine

Lingua serves two activities that share the same LangGraph machinery:

1. **Define / maintain the design system** — author tokens, patterns, and abstract component usage; keep them updated over time.
2. **Build screens** — generate real application screens that conform to the defined system, in whichever code layer the target software uses.

---

## 2. The Architecture Model

```
        LINGUA DESIGN SYSTEM (source of truth — code-agnostic)
        ├── Foundations / Tokens   → the look & feel
        ├── Patterns               → layout, navigation, experience rules
        └── Component usage        → abstract component vocabulary (when & why)
                          │
                          │  rendered by ↓
        ┌─────────────────┼─────────────────┬──────────────┐
   ANT DESIGN          SHADCN           ANGULAR         (future adapters)
   adapter             adapter          adapter
```

### Knowledge / repo structure

```
lingua-ds/                        # the abstract, code-agnostic definition
├── foundations/
│   └── tokens.json               # single token source of truth
├── patterns/
│   ├── layout/                   # layout & navigation patterns
│   ├── forms/
│   └── ...
└── components/                   # ABSTRACT component vocabulary
    ├── overlay.md                # Overlay.Blocking, Overlay.Contextual...
    ├── disclosure.md
    └── ...

adapters/
├── antd/
│   ├── tokens.adapter.ts         # maps tokens.json → Ant theme config
│   ├── components.map.json       # abstract concept → Ant component
│   └── conformance.json          # declared matches / partials / gaps
├── shadcn/
│   ├── tokens.adapter.ts         # maps tokens.json → CSS variables
│   ├── components.map.json
│   └── conformance.json
└── angular/
    └── ...
```

### The system layers

**1. Knowledge layer (what Lingua knows)**
The design system definition. Splits into:
- *Descriptive* knowledge — component APIs, props, variants. Cheap to ingest from existing DS docs / MCP servers (Ant and shadcn both ship MCPs).
- *Prescriptive* knowledge — when/why to use, what to use instead, anti-patterns, decision trees. This is the real intellectual asset and must be authored, not scraped.

**2. Conversation layer (how Lingua interviews)**
The LangGraph orchestrator guides users through *experience decisions*, not just "what do you want to build":
- "Is this action reversible?" → affects confirmation pattern
- "How many items will this list hold?" → affects pagination strategy
- "Inline or dedicated page?" → affects layout choice

**3. Generation layer (what Lingua produces)**
- Screen code in the target adapter's library
- A rationale doc explaining *why* each decision was made
- A challengeable decision log
- Suggested next screens based on flow logic

### Stack (current)

- **LangGraph** — orchestration (conversation, interview, refinement, planning, approval)
- **OpenCode** — headless coding agent in a Docker container (file edits, builds, hot reload)
- **Ant Design X** in an Ant Design project — the chat/UI layer (replaced the earlier Chainlit plan)
- Live preview via Vite + React served from the container, in an iframe

---

## 3. Core Definitions

| Term | Definition |
|------|------------|
| **Design System (Lingua's def.)** | Look & feel (foundations, tokens) + experience (patterns, component usage). NOT code. |
| **Abstract component vocabulary** | Neutral component concepts (e.g. `Overlay.Blocking`, `Disclosure.Inline`) that each adapter maps to real components. |
| **Adapter** | A code layer that renders the Lingua DS into a specific library (Ant, shadcn, Angular). |
| **Conformance map** | An adapter's declared list of full matches, partial matches, and gaps versus the abstract definition. |
| **Token contract** | The single token source consumed by all adapters to enforce "same look and feel." |
| **Knowledge pack** | A versioned bundle of DS definition + adapter mappings for a given setup. |
| **Descriptive knowledge** | What a component *is* (API, props). |
| **Prescriptive knowledge** | When/why to use it, alternatives, anti-patterns. |

---

## 4. The Flagship Use Case

**The multi-software, multi-stack company.**

A company has ~10 software products: some on Ant Design, some on shadcn, some on Angular. They need the *same look and feel* and the *same experience* across all of them.

Lingua's path:
1. Define the tokens and DS once in Lingua.
2. Apply that definition to the **older/existing** software via adapters — unifying look & feel without a rewrite.
3. Build **new** screens through Lingua, automatically conforming to the shared design system, in whatever code layer the target product uses.

The migration story is a standalone value proposition: moving from Ant to shadcn is normally a months-long rewrite. Under Lingua, the DS definition is stable — only the adapter changes.

---

## 5. Challenges (Open Problems)

### Architectural / technical

1. **Quality of the abstraction.** If the abstract vocabulary leans too close to one library (e.g. Ant), the others feel bolted on. Mitigation: design the abstract layer by examining 2–3 philosophically different systems at once (Ant = batteries-included; shadcn = copy-paste primitives) and keep only what maps cleanly to all.
2. **Token reproducibility across adapters.** "Same look and feel" lives or dies on tokens. Ant uses design tokens natively; shadcn uses CSS variables; Angular Material has its own theming. One source must emit all formats (Style Dictionary / Tokens Studio-style pipeline).
3. **Declared deltas, not silent ones.** Each adapter must publish a conformance map so behavioral/visual differences are inspectable, never surprising.
4. **Applying the DS to legacy software.** Retrofitting tokens onto existing apps is harder than greenfield generation; each stack has its own theming entry points and constraints.
5. **Decision logic must be deterministic.** Decision trees must be *executed*, not fuzzy-matched. RAG is fine for advisory prose but wrong for branching logic.

### Knowledge / content

6. **The empty-state problem.** A company won't hand-author dozens of decision trees. Solved here by shipping opinionated open-source seed packs (a feature in OSS, not a liability).
7. **Licensing on scraped docs.** Ant (MIT) and shadcn (MIT) are permissive but prose can't be copied wholesale. Scrape to *learn and synthesize*, then author original prescriptive knowledge.
8. **Minimum viable knowledge layer.** Too much required input kills adoption; too little kills generation quality. The threshold must be found.

### Lifecycle / maintenance

9. **Upstream DS changes** (Ant v6, new shadcn components) require a re-ingestion/diff step, with pack versions pinned to DS versions.
10. **Internal opinion changes** need version history so consuming teams see what changed.
11. **Local override drift** — when a company customizes and upstream later updates, it becomes a git-like merge problem (show the diff, let them reconcile).
12. **Update communication.** Needs both a machine-readable changelog (so Lingua can surface relevant updates *during* development) and a human-readable blog/release-notes view generated from it.

---

## 6. Product Manager Analysis

### 6.1 Product quality assessment

**Strengths**
- **Genuine differentiation.** Most "DS-agnostic" tools leak implementation upward; Lingua's hard abstraction line is unusual and defensible.
- **Strong wedge use case.** The multi-stack company is a real, painful, underserved problem with budget attached.
- **Two value props from one engine.** "Unify look & feel across stacks" (migration/retrofit) and "generate conformant screens" (build) reinforce each other.
- **OSS-aligned opinions.** Strong, forkable defaults are a feature in open source, sidestepping the "we can't be right for everyone" trap.
- **Leverages existing ecosystem.** Ant and shadcn ship MCPs + solid docs, lowering descriptive-ingestion cost.

**Weaknesses / risks**
- **Abstraction is the make-or-break.** The entire product rests on the quality of the neutral vocabulary. Get it wrong and adapters fragment.
- **Scope is large.** Spec language + adapters + generation + lifecycle is several products. Risk of building broad and shallow.
- **Conformance expectation management.** "Same look and feel" is a promise; users will notice deltas. Must be framed as "intentional, declared deltas" from day one.
- **Maintenance burden scales with adapters.** Each new library and each upstream version is ongoing work.
- **Adoption friction for legacy retrofit.** The most valuable use case (apply DS to old apps) is also the technically hardest.

**Quality verdict:** Strong *concept* with a clear, defensible wedge. The risk is almost entirely in *execution discipline* — keeping scope narrow (one category, two adapters) until the abstraction is proven. This is a "depth before breadth" product.

### 6.2 Competitive landscape

| Category | Examples | How Lingua differs |
|----------|----------|--------------------|
| **AI app builders** | Lovable, v0 (Vercel), Bolt.new | They generate code from prompts but are *DS-naive* — no enforced design system, no cross-stack reproducibility. Lingua generates *conformant* code against a defined DS. |
| **Design-to-code** | Figma Dev Mode, Anima, Locofy, Builder.io | Convert designs to code per-screen; not a living, code-agnostic DS spec. No cross-library rendering of one definition. |
| **Token / theming tools** | Style Dictionary, Tokens Studio, Supernova, Knapsack | Strong on tokens & docs, but stop at look & feel. They don't encode *experience* (patterns, component-usage decisions) or generate screens. Closest neighbors on the foundations layer. |
| **DS documentation platforms** | zeroheight, Backlight, Storybook | Document an existing DS; they don't abstract it across code layers or build screens conversationally. |
| **Headless / cross-framework UI** | Radix, Ark UI, Mitosis (write-once-compile-many) | Mitosis is the closest *technical* analogue (one source → many frameworks) but it's component-level, not design-system + experience level, and not conversational. |

**Whitespace:** No one occupies "code-agnostic design system spec + experience knowledge + conversational screen generation across stacks." Supernova/Knapsack are the closest on tooling philosophy; Mitosis is closest on cross-framework compilation. Lingua's unique combination is the abstraction line + the experience/prescriptive layer + generation.

**Competitive risk:** A well-funded incumbent (Vercel/v0, Figma, Supernova) could add DS-conformance to an existing product faster than Lingua can build the whole stack. Lingua's defense is OSS community, the depth of the prescriptive knowledge, and the multi-stack reproducibility that single-stack incumbents have no incentive to build.

### 6.3 Target users (personas)

1. **DS Lead / Design Engineer (the Author)** — owns the design system. Defines tokens, patterns, abstract component usage; reviews seed packs; publishes versions; approves release notes. *Primary champion.*
2. **Platform/Frontend Engineer (the Adapter Maintainer)** — wires adapters, manages conformance maps, handles upstream version bumps and legacy retrofits.
3. **Product Developer (the Consumer)** — builds screens conversationally; consumes opinionated guidance; gets notified of relevant DS updates mid-build.
4. **Engineering Leadership (the Buyer/Sponsor)** — feels the pain of inconsistent UX across 10 products; cares about cost of unification and migration risk reduction.
5. **OSS Contributor** — extends adapters, contributes knowledge packs for new libraries, files opinion PRs.

### 6.4 User journeys

**A. DS Lead — defining the system (first run)**
1. Points Lingua at existing component libraries / MCPs.
2. Lingua ingests descriptive layer automatically; proposes prescriptive scaffolding (decision trees, "use when") as *editable drafts*.
3. Lead is interviewed by the same LangGraph engine; corrects/approves opinions.
4. Defines tokens once; previews them rendered through each adapter.
5. Publishes a versioned knowledge pack.

**B. Platform Engineer — retrofitting legacy software**
1. Selects a target product and its stack (e.g. Angular).
2. Applies the token contract via the Angular adapter.
3. Reviews the conformance map for declared deltas.
4. Iterates until look & feel matches; commits.

**C. Product Developer — building a new screen**
1. Describes the screen in plain language.
2. Lingua interviews on experience decisions (reversibility, data volume, layout).
3. Executes the relevant decision trees deterministically; selects abstract components.
4. Generates conformant code in the target adapter + rationale doc.
5. Sees live preview; challenges/adjusts decisions; iterates.
6. If a used pattern changed recently, Lingua proactively flags it.

**D. Leadership — evaluating adoption**
1. Sees one DS definition rendered identically across Ant + shadcn demos.
2. Reviews the migration/retrofit story and maintenance model.
3. Sponsors a pilot on one painful cross-stack flow.

### 6.5 Additional PM analyses

**Positioning statement (draft):**
*For engineering organizations running multiple products across different front-end stacks, Lingua is an open-source design system engine that defines look, feel, and experience independently of code — so one design system renders consistently across Ant Design, shadcn, Angular, and more, and new screens are generated to conform automatically.*

**Riskiest assumptions (validate first):**
1. A useful abstract component vocabulary that maps cleanly across philosophically different libraries actually exists. *(Highest risk — validate with one category × two adapters before anything else.)*
2. Companies will trust generated screens enough to ship them.
3. Token reproducibility can hit "close enough" that the delta is acceptable.
4. The retrofit-to-legacy path is feasible enough to be a selling point, not just a demo.

**Suggested MVP scope (depth before breadth):**
- One pattern category (overlays *or* layout/navigation) defined abstractly.
- Two adapters (Ant + shadcn) with explicit conformance maps.
- Token contract → both adapters, one shared visual result.
- Conversational generation for that one category, with rationale output.
- A machine-readable changelog feeding a simple release-notes view.

**Success metrics (early):**
- % of generated screens accepted without manual code edits.
- Visual delta between adapters for the same definition (measured, not vibes).
- Time to retrofit one legacy screen vs. manual baseline.
- Author effort to reach "minimum viable knowledge layer."
- OSS signal: stars, adapter contributions, knowledge-pack PRs.

**Go-to-market (OSS):**
- Dogfood on a reference DS as "system zero," shipped as the opinionated seed pack.
- Lead with the cross-stack reproducibility demo (one definition, two libraries, side by side) — it's the "wow" no competitor shows.
- Build community around adapter authorship; each new adapter expands reach.

---

## 7. Recommended Next Step

Draft the **abstract component vocabulary** for one category (overlays or layout/navigation), end to end:
**abstract concept → Ant mapping → shadcn mapping → conformance notes.**

This is the riskiest assumption and the foundation everything else hangs on. Proving one category across two opposite libraries validates (or kills) the core thesis cheaply.
