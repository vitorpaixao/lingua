/**
 * Raw design values from the Figma redesign (node 6:2) that have NO Ant Design token
 * equivalent. Keep this list minimal — anything that maps to a semantic token belongs in
 * ./tokens.ts instead.
 */
export const figma = {
  /**
   * Single workspace gutter. Drives the left column's left/right inset and the preview
   * splitter-panel inset (Figma hoists the horizontal gutter onto the column containers).
   * Change this to reflow both columns.
   */
  workspaceGutter: 24,
  /** Inner padding of the preview window card. */
  previewCardPadding: 8,
} as const;
