import { lightTheme } from "./tokens.generated";

// Strip readonly and widen literal leaves so both light and dark palettes
// (each exported `as const` with distinct literal types) are assignable to Theme.
type Widen<T> = T extends readonly (infer U)[]
  ? readonly Widen<U>[]
  : T extends object
    ? { -readonly [K in keyof T]: Widen<T[K]> }
    : T extends string
      ? string
      : T extends number
        ? number
        : T extends boolean
          ? boolean
          : T;

// Both palettes share one shape; derive a widened version from the light theme.
export type Theme = Widen<typeof lightTheme>;
export type ColorScheme = "light" | "dark";
export type ThemeMode = "system" | "light" | "dark";
