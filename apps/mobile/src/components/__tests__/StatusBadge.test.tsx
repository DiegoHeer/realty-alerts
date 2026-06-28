import { StyleSheet } from "react-native";
import { renderWithTheme } from "@/test/renderWithTheme";
import { StatusBadge } from "@/components/StatusBadge";
import { lightTheme } from "@/theme/tokens.generated";

const STATUS_FEEDBACK = {
  running: "warning",
  success: "success",
  failed: "error",
} as const;

describe("StatusBadge", () => {
  it.each(Object.keys(STATUS_FEEDBACK) as (keyof typeof STATUS_FEEDBACK)[])(
    "renders the status label for %s",
    async (status) => {
      const { getByText } = await renderWithTheme(<StatusBadge status={status} />);
      expect(getByText(status)).toBeTruthy();
    },
  );

  it.each(Object.entries(STATUS_FEEDBACK))(
    "maps %s to the %s feedback palette",
    async (status, variant) => {
      const { getByText } = await renderWithTheme(
        <StatusBadge status={status as keyof typeof STATUS_FEEDBACK} />,
      );
      const label = getByText(status);
      expect(StyleSheet.flatten(label.props.style).color).toBe(lightTheme.feedback[variant].text);
      expect(StyleSheet.flatten(label.parent?.props.style).backgroundColor).toBe(
        lightTheme.feedback[variant].background,
      );
    },
  );
});
