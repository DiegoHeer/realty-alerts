import { View, type ViewProps } from "react-native";
import { Text } from "./Text";
import { useTheme } from "@/theme/useTheme";

export type BadgeVariant = "success" | "error" | "warning" | "info" | "neutral";

export interface BadgeProps extends Omit<ViewProps, "children"> {
  variant: BadgeVariant;
  children: string;
}

export function Badge({ variant, children, style, ...rest }: BadgeProps) {
  const theme = useTheme();
  const palette: { background: string; text: string } =
    variant === "neutral"
      ? { background: theme.layerTwo.background, text: theme.layerTwo.text }
      : theme.feedback[variant];

  return (
    <View
      style={[
        {
          backgroundColor: palette.background,
          borderRadius: theme.radius.full,
          paddingVertical: theme.space["050"],
          paddingHorizontal: theme.space["100"],
          alignSelf: "flex-start",
        },
        style,
      ]}
      {...rest}
    >
      <Text variant="caption" color={palette.text}>
        {children}
      </Text>
    </View>
  );
}
