import { TextInput, type TextInputProps } from "react-native";
import { useTheme } from "@/theme/useTheme";

export type InputProps = TextInputProps;

export function Input({ style, placeholderTextColor, ...rest }: InputProps) {
  const theme = useTheme();
  return (
    <TextInput
      placeholderTextColor={placeholderTextColor ?? theme.input.icon}
      style={[
        {
          backgroundColor: theme.input.background,
          color: theme.input.text,
          borderColor: theme.input.border,
          borderWidth: 1,
          borderRadius: theme.radius["100"],
          paddingVertical: theme.space["150"],
          paddingHorizontal: theme.space["200"],
          fontFamily: theme.type.body.fontFamily,
          fontSize: theme.type.body.fontSize,
        },
        style,
      ]}
      {...rest}
    />
  );
}
