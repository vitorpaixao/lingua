import { forwardRef, useEffect, useState } from 'react';
import { Flex, Spin, Typography } from 'antd';

const POLL_INTERVAL_MS = 1500;
const POLL_URL = '/preview/';

type Props = {
  onLoad?: () => void;
  /**
   * Bumping this forces the iframe to unmount + remount, hard-reloading the
   * preview. Used after a workspace switch so Vite re-evaluates from the
   * newly-active /project subdir.
   */
  reloadKey?: number;
};

export const PreviewPanel = forwardRef<HTMLIFrameElement, Props>(
  function PreviewPanel({ onLoad, reloadKey = 0 }, ref) {
    const [ready, setReady] = useState(false);

    useEffect(() => {
      setReady(false);
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
    }, [reloadKey]);

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
        key={reloadKey}
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
