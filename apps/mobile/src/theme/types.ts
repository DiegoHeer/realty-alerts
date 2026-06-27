import { lightTheme } from "./tokens.generated";

// Both palettes share one shape; derive it from the light theme.
export type Theme = typeof lightTheme;
export type ColorScheme = "light" | "dark";
export type ThemeMode = "system" | "light" | "dark";
