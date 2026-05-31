import { forwardRef } from 'react';

export const PreviewPanel = forwardRef<HTMLIFrameElement, { onLoad?: () => void }>(
  function PreviewPanel({ onLoad }, ref) {
    return (
      <iframe
        ref={ref}
        src="/preview"
        title="Preview"
        onLoad={onLoad}
        style={{
          width: '100%',
          height: '100%',
          border: 'none',
          background: '#fff',
        }}
      />
    );
  },
);
