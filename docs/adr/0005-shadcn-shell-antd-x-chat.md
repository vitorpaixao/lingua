# shadcn/ui for the shell; Ant Design X retained for the chat

Status: accepted

The web UI is moving to a shadcn/ui design system (matching the Figma redesign `Lingua-shadcnui`, node `17:178`, and the "shadcn as a render target" direction in `docs/product-definition.md`). The shipped chat, however, is built on **Ant Design X** (`Bubble.List`, `Sender`, `Think`, `ThoughtChain`, `Conversations`) — a chat-specific component set that shadcn has **no equivalent for**. Rebuilding it would be high-effort, high-risk, and would throw away the durable-transcript replay wiring (see [0001](0001-conversation-as-durable-entity.md)).

Decision: **the application shell (sidebar, stage header, layout, forms, menus, preview chrome) is shadcn/ui; the chat area stays Ant Design X.** Two UI libraries coexist in one app on purpose. A throwaway prototype under `web2/` validated the shell visually against Figma before integration into `web/`.

## Coexistence mechanics

- **Tailwind preflight is ON; antd is isolated to the chat.** (Corrected — see note below.) Ant Design v6's reset is component-scoped CSS-in-JS (`:where(.ant-*)`); it is *not* a global reset, so it never gives shadcn's shell the `box-sizing: border-box` and `<ul>`/`<li>` resets it assumes. The shell therefore owns the global reset via Tailwind preflight. antd's styles are wrapped in a CSS cascade layer (`<StyleProvider layer>` in `ChatPanel.tsx`) and `globals.css` declares `@layer tailwind-base, antd` — so preflight resets the shell while antd's component styles still win inside the chat subtree. Tailwind utilities stay unlayered and win over both.

  > **Correction (2026-06-26):** this ADR originally stated preflight was OFF and "antd owns the global reset." That premise was false — antd's reset is component-scoped, so the shadcn shell rendered with no reset (overflowing sidebar, horizontal scrollbar, footer under the chat). Fixed by re-enabling preflight and isolating antd to the chat via cascade layers, as described above.
- **Single token source.** Figma variables are captured once in `theme/tokens.ts` and emitted to **both** targets: shadcn CSS variables in `globals.css`, and the antd `ConfigProvider` theme (`buildAntdTheme`) for the chat. One palette, two render targets — the "token contract" from `product-definition.md`.
- **One dark-mode toggle drives both.** `lib/theme.tsx` is the single switch: it sets the `.dark` class (shadcn/Tailwind) and selects the antd algorithm + `data-theme` (chat). Dark is the default.
- The chat subtree is wrapped in its own `ConfigProvider` + `XProvider`, scoping antd's CSS-in-JS so the rest of the shell is pure shadcn/Tailwind.

## Considered options

- **Rebuild the chat in shadcn** — rejected: no shadcn primitives for streaming bubbles / sender / thought-chain; large rewrite, loses tested streaming + replay logic for no visual gain.
- **Keep the whole UI on Ant Design** — rejected: the Figma redesign and product vision are shadcn; antd's look diverges from the target design system.
- **Two libraries, split by area (chosen)** — shadcn for the shell, antd X for chat. Accepts the cost of shipping both libraries and reconciling their CSS resets, in exchange for keeping the chat exactly as-is.

## Consequences

- The bundle ships both Tailwind/shadcn and antd + @ant-design/x. Acceptable; the chat already required antd.
- Anyone touching the chat works in antd conventions (`ConfigProvider`, `useToken`, X components); everything else is shadcn + Tailwind utilities. This boundary is the rule of thumb for all future UI work.
- Theming changes must be made in `theme/tokens.ts` and mirrored in `globals.css` so the two render targets stay aligned.
- Step-2 integration into `web/` re-applies the same mechanics there; `ChatPanel.tsx` / `ConversationList.tsx` remain on Ant Design X untouched. The IntroPage-vs-sidebar navigation model is resolved during that integration (see `plan/step2.md`).
