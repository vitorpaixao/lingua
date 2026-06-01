import { forwardRef, useEffect, useState } from 'react';
import { Flex, Spin, Typography } from 'antd';

const POLL_INTERVAL_MS = 1500;
const POLL_URL = '/preview/';

export const PreviewPanel = forwardRef<HTMLIFrameElement, { onLoad?: () => void }>(
  function PreviewPanel({ onLoad }, ref) {
    const [ready, setReady] = useState(false);

    useEffect(() => {
      let cancelled = false;
      const tick = async () => {
        try {
          const res = await fetch(POLL_URL, {
            method: 'GET',
            cache: 'no-store',
          });
          if (cancelled) return;
          if (res.ok) {
            setReady(true);
            return;
          }
        } catch {
          // network error — keep polling
        }
        if (!cancelled) setTimeout(tick, POLL_INTERVAL_MS);
      };
      void tick();
      return () => {
        cancelled = true;
      };
    }, []);

    if (!ready) {
      return (
        <Flex
          vertical
          align="center"
          justify="center"
          gap={12}
          style={{ width: '100%', height: '100%' }}
        >
          <Spin size="large" />
          <Typography.Text type="secondary">
            Waiting for preview server (npm install, Vite startup)…
          </Typography.Text>
        </Flex>
      );
    }

    return (
      <iframe
        ref={ref}
        src="/preview/"
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
