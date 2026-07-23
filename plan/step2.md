# Step 2 — Integrate the shadcn shell into `web/`

> Prerequisite: the `web2/` visual prototype is validated against Figma `17:178`.
> This step migrates those patterns into the shipped app and deletes `web2/`.
> See [ADR-0005](../docs/adr/0005-shadcn-shell-antd-x-chat.md) for the rules.

## Rule (unchanged)

shadcn/ui for the whole shell; **Ant Design X stays for the chat**
(`web/src/components/ChatPanel.tsx`, `ConversationList.tsx`). Preflight OFF,
single token source, one toggle drives both dark modes.

## Steps

1. **Add Tailwind + shadcn to `web/`.**
   - Install `tailwindcss@^3`, `postcss`, `autoprefixer`, `tailwindcss-animate`,
     `class-variance-authority`, `clsx`, `tailwind-merge`, `lucide-react`, and the
     radix packages used by the ported components.
   - Copy `tailwind.config.ts` (preflight off), `postcss.config.js`,
     `components.json`, `src/lib/utils.ts`, and `src/components/ui/*` from `web2/`.
   - Add `@tailwind` directives + the token CSS variables to a `web/src/globals.css`
     and import it from `web/src/main.tsx`.

2. **Fold the token source into the existing theme.**
   - Merge `web2/src/theme/tokens.ts` into `web/src/theme/tokens.ts` so the same
     palette feeds both the shadcn CSS variables and the existing antd
     `ConfigProvider` (`buildLinguaTheme`). Reconcile with `web/src/theme/figma.ts`.

3. **Extend the dark-mode context.**
   - Update `web/src/lib/theme.tsx` so the toggle also sets the `.dark` class
     (it already sets the antd algorithm + `data-theme`). Keep dark as default.

4. **Port the shell components** from `web2/src/components`:
   - `AppSidebar`, `StageHeader`, `PreviewPane` chrome.
   - Mount `AppSidebar` in `web/src/pages/WorkspacePage.tsx`; wire the
     `panel-left` toggle to collapse it. Replace `WorkspaceHeader.tsx` with
     `StageHeader`. **Do not touch `ChatPanel.tsx` / `ConversationList.tsx`.**
   - Wire the sidebar's project/conversation switchers to the real data already
     loaded in `WorkspacePage` (project list, conversations, URL params
     `?id=&c=`); reuse `api/client.ts` calls — no new data layer.

5. **Migrate remaining antd structural components to shadcn, screen by screen
   (outside chat):** `Layout`/`Splitter` → flex + a resizable primitive,
   `Drawer`/`Modal` → shadcn `sheet`/`dialog`, `Form` → react-hook-form +
   shadcn `form`, `Segmented`/`Select`/`AutoComplete` → shadcn equivalents,
   `message`/`modal` imperatives → `sonner` toasts. Affected files:
   `IntroPage.tsx`, `SystemSettingsForm.tsx`, `ProjectSettingsForm.tsx`,
   `NewProjectModal.tsx`, `DirtySwitchModal.tsx`, `ActivityTabs.tsx`,
   `PreviewToolbar.tsx`, `ThemeToggle.tsx`.

6. **Resolve the navigation model (deferred from step 1).**
   The new sidebar carries project switch + Projects/Conversations nav. Decide:
   does the sidebar's "Projects" view replace `IntroPage`'s project-list, or does
   `IntroPage` remain the first-run/empty landing? Update routing in `App.tsx`
   accordingly.

7. **Clean up.** Delete `web2/`. Update `docs/STRUCTURE.md` (frontend section) to
   note shadcn shell + antd X chat.

## Verification

- `cd web && npm run build` (`tsc -b && vite build`) passes; `npm run lint`;
  `npm test` (vitest) green — update/extend tests touching migrated components.
- Theme toggle flips shadcn (`.dark`) and the antd chat together; dark default.
- Live `ChatPanel` SSE streaming still works against the orchestrator
  (`/api/chat/stream`); the new sidebar mounts and switches projects/conversations.
- Visual parity with Figma `17:178` in the real workspace.
