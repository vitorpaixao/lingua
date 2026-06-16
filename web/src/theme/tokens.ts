import { theme as antdTheme } from 'antd';
import type { ThemeConfig } from 'antd';

/**
 * Lingua design tokens, derived from the Figma redesign (file hsmeBU2xSzfBxCO8tUe6g9,
 * node 6:2). Values are mapped onto Ant Design's semantic tokens wherever an equivalent
 * exists, so components pick them up automatically through ConfigProvider. Raw values
 * with no token equivalent live in ./figma.ts.
 *
 * The Figma is dark-only; that palette becomes the dark-mode overrides. Light mode keeps
 * Ant Design's default algorithm untouched (the app still has a light/dark toggle).
 */

const PRIMARY = '#1677ff';

// Dark palette lifted straight from the Figma node hexes.
const darkPalette = {
  colorBgLayout: '#15161a', // app / outer background
  colorBgContainer: '#24252a', // cards, chat bubbles, preview surface
  colorBgElevated: '#393a40', // raised surfaces (sender input, popovers)
  colorBorder: '#6d6d6d', // inactive pill / control borders
} as const;

export function buildLinguaTheme(mode: 'light' | 'dark'): ThemeConfig {
  const dark = mode === 'dark';
  return {
    algorithm: dark ? antdTheme.darkAlgorithm : antdTheme.defaultAlgorithm,
    token: {
      colorPrimary: PRIMARY,
      borderRadius: 8, // pills / buttons / inputs (Figma 8px)
      borderRadiusLG: 16, // cards / bubbles / preview window (Figma 16px)
      ...(dark ? darkPalette : {}),
    },
    components: {
      // Figma shows the active activity pill as a solid white fill on dark.
      Segmented: dark
        ? {
            trackBg: darkPalette.colorBgContainer,
            itemSelectedBg: '#ffffff',
            itemSelectedColor: darkPalette.colorBgLayout,
          }
        : {},
    },
  };
}
