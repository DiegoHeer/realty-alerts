import { useMemo } from "react";
import { StyleSheet } from "react-native";
import { useTheme } from "./useTheme";
import type { Theme } from "./types";

export function useThemedStyles<T extends StyleSheet.NamedStyles<T>>(
  factory: (theme: Theme) => T,
): T {
  const theme = useTheme();
  // `factory` is intentionally excluded: callers pass a module-scope factory
  // (stable identity), so memoizing on `theme` alone is correct and including
  // `factory` would defeat memoization for inline factories.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  return useMemo(() => StyleSheet.create(factory(theme)), [theme]);
}
