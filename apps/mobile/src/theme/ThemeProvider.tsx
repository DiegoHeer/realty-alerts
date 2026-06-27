import { createContext, type ReactNode } from "react";
import { useColorScheme } from "react-native";
import { darkTheme, lightTheme } from "./tokens.generated";
import { useThemeStore } from "./themeStore";
import type { ColorScheme, Theme } from "./types";

export interface ThemeContextValue {
  theme: Theme;
  scheme: ColorScheme;
}

export const ThemeContext = createContext<ThemeContextValue | null>(null);

export function ThemeProvider({ children }: { children: ReactNode }) {
  const system = useColorScheme();
  const mode = useThemeStore((s) => s.mode);
  const scheme: ColorScheme = mode === "system" ? (system === "dark" ? "dark" : "light") : mode;
  const theme: Theme = scheme === "dark" ? darkTheme : lightTheme;
  return <ThemeContext.Provider value={{ theme, scheme }}>{children}</ThemeContext.Provider>;
}
