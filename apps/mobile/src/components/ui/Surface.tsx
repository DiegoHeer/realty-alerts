import { View, type ViewProps, type ViewStyle } from "react-native";
import { useTheme } from "@/theme/useTheme";
import { useThemedStyles } from "@/theme/useThemedStyles";
import type { Theme } from "@/theme/types";

export type SurfaceLayer = "base" | "one" | "two";
export type SoftShadow = keyof Theme["shadow"]["outer"]["soft"];

export interface SurfaceProps extends ViewProps {
  layer?: SurfaceLayer;
  shadow?: SoftShadow;
  radius?: keyof Theme["radius"];
  padding?: keyof Theme["space"];
}

const factory = (theme: Theme) => ({
  base: { backgroundColor: theme.layerBase.background, borderColor: theme.layerBase.border, borderWidth: 1 },
  one: { backgroundColor: theme.layerOne.background, borderColor: theme.layerOne.border, borderWidth: 1 },
  two: { backgroundColor: theme.layerTwo.background, borderColor: theme.layerTwo.border, borderWidth: 1 },
});

export function Surface({ layer = "one", shadow, radius = "150", padding, style, ...rest }: SurfaceProps) {
  const styles = useThemedStyles(factory);
  const theme = useTheme();
  const dynamic: ViewStyle = { borderRadius: theme.radius[radius] };
  if (padding !== undefined) dynamic.padding = theme.space[padding];
  const shadowStyle = shadow ? theme.shadow.outer.soft[shadow] : undefined;
  return <View style={[styles[layer], dynamic, shadowStyle, style]} {...rest} />;
}
