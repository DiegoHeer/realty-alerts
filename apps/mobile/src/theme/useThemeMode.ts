import { useThemeStore } from "./themeStore";
import type { ThemeMode } from "./types";

export function useThemeMode(): { mode: ThemeMode; setMode: (mode: ThemeMode) => void } {
  const mode = useThemeStore((s) => s.mode);
  const setMode = useThemeStore((s) => s.setMode);
  return { mode, setMode };
}
