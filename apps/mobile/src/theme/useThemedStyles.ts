import { useMemo } from "react";
import { StyleSheet } from "react-native";
import { useTheme } from "./useTheme";
import type { Theme } from "./types";

export function useThemedStyles<T extends StyleSheet.NamedStyles<T>>(
  factory: (theme: Theme) => T,
): T {
  const theme = useTheme();
  return useMemo(() => StyleSheet.create(factory(theme)), [theme]);
}
