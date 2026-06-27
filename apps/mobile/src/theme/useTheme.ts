import { useContext } from "react";
import { ThemeContext } from "./ThemeProvider";
import type { Theme } from "./types";

export function useTheme(): Theme {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used within a ThemeProvider");
  return ctx.theme;
}
