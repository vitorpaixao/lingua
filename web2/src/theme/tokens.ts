/**
 * Single token source for the embedded Ant Design X chat.
 *
 * The shell's palette is defined by the shadcn "radix-mira" preset (b5nh4SoPXk)
 * as OKLCH CSS variables in `src/globals.css`. antd v6's theme engine cannot
 * parse `oklch()` strings, so the values the chat needs are mirrored here as
 * hex/sRGB equivalents of the same preset tokens. When the preset palette
 * changes, update globals.css and re-mirror the primary/base colours here.
 */
export const palette = {
  light: {
    background: '#ffffff', // oklch(1 0 0)
    foreground: '#0a0a0a', // oklch(0.145 0 0)
    primary: '#007a55', //   oklch(0.508 0.118 165.612)
    border: '#e5e5e5', //    oklch(0.922 0 0)
    muted: '#f5f5f5',
    mutedForeground: '#737373',
  },
  dark: {
    background: '#0a0a0a', // oklch(0.145 0 0)
    foreground: '#fafafa', // oklch(0.985 0 0)
    primary: '#006045', //   oklch(0.432 0.095 166.913)
    border: '#262626', //    solid equivalent of oklch(1 0 0 / 10%)
    muted: '#262626',
    mutedForeground: '#a3a3a3',
  },
} as const;

export const radius = {
  sm: 7, // ~ 0.45rem preset --radius
  lg: 9,
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
      fontFamily: "'Public Sans Variable', system-ui, sans-serif",
    },
  };
}
