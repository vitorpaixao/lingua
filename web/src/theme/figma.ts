/**
 * Raw design values from the Figma redesign (node 6:2) that have NO Ant Design token
 * equivalent. Keep this list minimal — anything that maps to a semantic token belongs in
 * ./tokens.ts instead.
 */
export const figma = {
  /** Outer gutter around the preview "popped window" card (Figma padding). */
  previewGutter: 12,
  /** Inner padding of the preview window card. */
  previewCardPadding: 8,
} as const;
