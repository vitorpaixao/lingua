/**
 * The live-preview pane. In the prototype it is a static empty preview area.
 * The real iframe wiring arrives at step-2 integration into web/.
 */
export function PreviewPane() {
  return (
    <div
      data-fig="preview"
      className="flex h-full min-w-0 flex-1 flex-col gap-4 overflow-y-auto p-4"
    >
      <div className="flex flex-1 items-center justify-center rounded-md text-sm text-muted-foreground">
        Live preview
      </div>
    </div>
  );
}
