import { Text as RNText, type TextProps } from "react-native";
import { useTheme } from "@/theme/useTheme";
import { useThemedStyles } from "@/theme/useThemedStyles";
import type { Theme } from "@/theme/types";

export type TextVariant = keyof Theme["type"];

export interface AppTextProps extends TextProps {
  variant?: TextVariant;
  color?: string;
}

const factory = (theme: Theme) => theme.type;

export function Text({ variant = "body", color, style, ...rest }: AppTextProps) {
  const styles = useThemedStyles(factory);
  const theme = useTheme();
  const resolvedColor = color ?? theme.layerBase.text;
  return <RNText style={[styles[variant], { color: resolvedColor }, style]} {...rest} />;
}
