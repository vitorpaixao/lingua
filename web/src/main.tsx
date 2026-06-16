import React from 'react';
import ReactDOM from 'react-dom/client';
import { App } from './App';
import './index.css';
import './theme/overrides.css';

async function bootstrap() {
  if (import.meta.env.DEV && import.meta.env.VITE_USE_MSW !== 'false') {
    const { worker } = await import('./mocks/browser');
    await worker.start({
      onUnhandledRequest: 'bypass',
      serviceWorker: { url: '/mockServiceWorker.js' },
    });
  } else if ('serviceWorker' in navigator) {
    // Production / MSW-disabled: kill any service worker a prior dev session
    // may have registered. Otherwise it intercepts every fetch and returns
    // cached HTML for JS module requests, breaking the page with MIME errors.
    const regs = await navigator.serviceWorker.getRegistrations();
    if (regs.length > 0) {
      await Promise.all(regs.map((r) => r.unregister()));
      // Hard reload to bust any in-flight intercepts
      window.location.reload();
      return;
    }
  }

  ReactDOM.createRoot(document.getElementById('root')!).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>,
  );
}

void bootstrap();
