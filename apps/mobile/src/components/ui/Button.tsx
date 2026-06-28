import { Pressable, type PressableProps, type ViewStyle } from "react-native";
import { Text } from "./Text";
import { useTheme } from "@/theme/useTheme";
import type { Theme } from "@/theme/types";

type ButtonVariant = "primary" | "secondary" | "destructive";
type ButtonState = "default" | "pressed" | "disabled";

export interface ButtonProps extends Omit<PressableProps, "children" | "style" | "disabled"> {
  variant?: ButtonVariant;
  disabled?: boolean;
  children: string;
  style?: ViewStyle;
}

const STATEFUL = { primary: "buttonPrimary", secondary: "buttonSecondary" } as const;

interface ResolvedStyle {
  backgroundColor: string;
  textColor: string;
  borderColor: string;
  opacity: number;
}

// Resolve background/text/border for a variant in a given interaction state.
function resolve(theme: Theme, variant: ButtonVariant, state: ButtonState): ResolvedStyle {
  if (variant === "destructive") {
    // feedback.error has no per-state tokens: reuse the shared disabled greys,
    // and dim on press since there is no pressed token.
    if (state === "disabled") {
      return {
        backgroundColor: theme.buttonPrimary.background.disabled,
        textColor: theme.buttonPrimary.text.disabled,
        borderColor: "transparent",
        opacity: 1,
      };
    }
    return {
      backgroundColor: theme.feedback.error.background,
      textColor: theme.feedback.error.text,
      borderColor: "transparent",
      opacity: state === "pressed" ? 0.85 : 1,
    };
  }
  const palette = theme[STATEFUL[variant]];
  return {
    backgroundColor: palette.background[state],
    textColor: palette.text[state],
    borderColor: palette.border[state],
    opacity: 1,
  };
}

export function Button({ variant = "primary", disabled = false, children, style, ...rest }: ButtonProps) {
  const theme = useTheme();
  const stateFor = (pressed: boolean): ButtonState => (disabled ? "disabled" : pressed ? "pressed" : "default");

  return (
    <Pressable
      disabled={disabled}
      style={({ pressed }) => {
        const r = resolve(theme, variant, stateFor(pressed));
        return [
          {
            backgroundColor: r.backgroundColor,
            borderColor: r.borderColor,
            borderWidth: 1,
            borderRadius: theme.radius.full,
            paddingVertical: theme.space["150"],
            paddingHorizontal: theme.space["300"],
            alignItems: "center",
            opacity: r.opacity,
          } as ViewStyle,
          style,
        ];
      }}
      {...rest}
    >
      {({ pressed }) => (
        <Text variant="label" color={resolve(theme, variant, stateFor(pressed)).textColor}>
          {children}
        </Text>
      )}
    </Pressable>
  );
}
