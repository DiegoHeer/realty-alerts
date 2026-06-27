import { Pressable, type PressableProps, type ViewStyle } from "react-native";
import { Text } from "./Text";
import { useTheme } from "@/theme/useTheme";

type ButtonVariant = "primary" | "secondary";
type ButtonState = "default" | "pressed" | "disabled";

export interface ButtonProps extends Omit<PressableProps, "children" | "style" | "disabled"> {
  variant?: ButtonVariant;
  disabled?: boolean;
  children: string;
  style?: ViewStyle;
}

const PALETTE = { primary: "buttonPrimary", secondary: "buttonSecondary" } as const;

export function Button({ variant = "primary", disabled = false, children, style, ...rest }: ButtonProps) {
  const theme = useTheme();
  const palette = theme[PALETTE[variant]];
  const stateFor = (pressed: boolean): ButtonState => (disabled ? "disabled" : pressed ? "pressed" : "default");

  return (
    <Pressable
      disabled={disabled}
      style={({ pressed }) => {
        const s = stateFor(pressed);
        return [
          {
            backgroundColor: palette.background[s],
            borderColor: palette.border[s],
            borderWidth: 1,
            borderRadius: theme.radius.full,
            paddingVertical: theme.space["150"],
            paddingHorizontal: theme.space["300"],
            alignItems: "center",
          } as ViewStyle,
          style,
        ];
      }}
      {...rest}
    >
      {({ pressed }) => (
        <Text variant="label" color={palette.text[stateFor(pressed)]}>
          {children}
        </Text>
      )}
    </Pressable>
  );
}
