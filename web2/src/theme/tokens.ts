/**
 * Single token source (derived from Figma node 17:178 `Lingua-shadcnui`).
 *
 * These values are the contract shared by both render targets:
 *  - shadcn / Tailwind: mirrored as CSS variables in `src/globals.css`.
 *  - Ant Design (embedded chat): consumed by `buildAntdTheme()` below.
 *
 * When a token changes, update it here and in globals.css together.
 */
export const palette = {
  light: {
    background: '#ffffff',
    foreground: '#0a0a0a',
    primary: '#1677ff',
    border: '#e5e5e5',
    muted: '#f5f5f5',
    mutedForeground: '#737373',
  },
  dark: {
    background: '#0a0a0a',
    foreground: '#fafafa',
    primary: '#3b9eff',
    border: '#404040',
    muted: '#262626',
    mutedForeground: '#a3a3a3',
  },
} as const;

export const radius = {
  sm: 6,
  lg: 8,
} as const;

export type ThemeMode = 'light' | 'dark';

/**
 * Builds an antd ThemeConfig from the shared palette so the embedded
 * Ant Design X chat matches the shadcn shell exactly.
 *
 * Typed loosely to avoid importing antd types here; the real shape is
 * `import('antd').ThemeConfig`.
 */
export function buildAntdTheme(mode: ThemeMode) {
  const p = palette[mode];
  return {
    token: {
      colorPrimary: p.primary,
      colorBgBase: p.background,
      colorTextBase: p.foreground,
      colorBorder: p.border,
      borderRadius: radius.sm,
      borderRadiusLG: radius.lg,
      fontFamily: 'Inter, system-ui, sans-serif',
    },
  };
}
