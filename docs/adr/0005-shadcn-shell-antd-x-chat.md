# shadcn/ui for the shell; Ant Design X retained for the chat

Status: accepted

The web UI is moving to a shadcn/ui design system (matching the Figma redesign `Lingua-shadcnui`, node `17:178`, and the "shadcn as a render target" direction in `docs/product-definition.md`). The shipped chat, however, is built on **Ant Design X** (`Bubble.List`, `Sender`, `Think`, `ThoughtChain`, `Conversations`) — a chat-specific component set that shadcn has **no equivalent for**. Rebuilding it would be high-effort, high-risk, and would throw away the durable-transcript replay wiring (see [0001](0001-conversation-as-durable-entity.md)).

Decision: **the application shell (sidebar, stage header, layout, forms, menus, preview chrome) is shadcn/ui; the chat area stays Ant Design X.** Two UI libraries coexist in one app on purpose. A throwaway prototype under `web2/` (Tailwind v4 + the shadcn `radix-mira` theme preset) validated the shell visually against Figma before integration into `web/`.

## Coexistence mechanics

- **Tailwind preflight is ON; antd is isolated to the chat.** Ant Design v6's reset is component-scoped CSS-in-JS (`:where(.ant-*)`); it is *not* a global reset, so it never gives shadcn's shell the `box-sizing: border-box` and `<ul>`/`<li>` resets it assumes. The shell therefore owns the global reset via Tailwind preflight (the `base` layer). antd's styles are wrapped in a CSS cascade layer named `antd` (`<StyleProvider layer>` in `ChatPanel.tsx`), and `globals.css` pre-declares the order `@layer theme, base, antd, components, utilities;` — so preflight resets the shell while antd's component styles, sitting after `base`, still win inside the chat subtree. Tailwind utilities live in the last layer and win over both.

  > **History:** an earlier revision (v3, `@layer tailwind-base, antd`) first claimed preflight was OFF and "antd owns the global reset." That premise was false — antd's reset is component-scoped, so the shadcn shell rendered with no reset (overflowing sidebar, horizontal scrollbar, footer under the chat). Fixed by re-enabling preflight and isolating antd to the chat via cascade layers. The prototype then migrated to Tailwind v4, where `@import "tailwindcss"` emits the `theme`/`base`/`utilities` layers and the explicit order statement above places `antd` between them.
- **Single token source.** The shell palette is the preset's OKLCH CSS variables in `globals.css` (mapped to Tailwind via `@theme inline`). antd v6's theme engine cannot parse `oklch()`, so `theme/tokens.ts` mirrors the primary + base colours as hex/sRGB and feeds the antd `ConfigProvider` theme (`buildAntdTheme`) for the chat. One palette, two render targets — the "token contract" from `product-definition.md`. When the preset palette changes, update `globals.css` and re-mirror `tokens.ts`.
- **One dark-mode toggle drives both.** `lib/theme.tsx` is the single switch: it sets the `.dark` class (shadcn/Tailwind) and selects the antd algorithm + `data-theme` (chat). Dark is the default.
- The chat subtree is wrapped in its own `ConfigProvider` + `XProvider`, scoping antd's CSS-in-JS so the rest of the shell is pure shadcn/Tailwind.

## Considered options

- **Rebuild the chat in shadcn** — rejected: no shadcn primitives for streaming bubbles / sender / thought-chain; large rewrite, loses tested streaming + replay logic for no visual gain.
- **Keep the whole UI on Ant Design** — rejected: the Figma redesign and product vision are shadcn; antd's look diverges from the target design system.
- **Two libraries, split by area (chosen)** — shadcn for the shell, antd X for chat. Accepts the cost of shipping both libraries and reconciling their CSS resets, in exchange for keeping the chat exactly as-is.

## Consequences

- The bundle ships both Tailwind/shadcn and antd + @ant-design/x. Acceptable; the chat already required antd.
- Anyone touching the chat works in antd conventions (`ConfigProvider`, `useToken`, X components); everything else is shadcn + Tailwind utilities. This boundary is the rule of thumb for all future UI work.
- Theming changes are made to the preset palette in `globals.css` and mirrored (as hex) in `theme/tokens.ts` so the antd chat stays aligned with the shell.
- Step-2 integration into `web/` re-applies the same mechanics there; `ChatPanel.tsx` / `ConversationList.tsx` remain on Ant Design X untouched. The IntroPage-vs-sidebar navigation model is resolved during that integration (see `plan/step2.md`).
