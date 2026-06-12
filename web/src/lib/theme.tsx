import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from 'react';

type Mode = 'light' | 'dark';
const STORAGE_KEY = 'lingua_theme_mode';

type Ctx = { mode: Mode; setMode: (m: Mode) => void; toggle: () => void };
const ThemeCtx = createContext<Ctx | null>(null);

function loadMode(): Mode {
  if (typeof window === 'undefined') return 'dark';
  const stored = window.localStorage.getItem(STORAGE_KEY);
  return stored === 'light' ? 'light' : 'dark';
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [mode, setModeState] = useState<Mode>(() => loadMode());

  const setMode = (m: Mode) => {
    setModeState(m);
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(STORAGE_KEY, m);
    }
  };
  const toggle = () => setMode(mode === 'light' ? 'dark' : 'light');

  useEffect(() => {
    document.documentElement.dataset.theme = mode;
  }, [mode]);

  return (
    <ThemeCtx.Provider value={{ mode, setMode, toggle }}>
      {children}
    </ThemeCtx.Provider>
  );
}

export function useTheme(): Ctx {
  const ctx = useContext(ThemeCtx);
  if (!ctx) throw new Error('useTheme must be used within ThemeProvider');
  return ctx;
}
