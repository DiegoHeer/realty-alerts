import { StyleSheet } from "react-native";
import { renderWithTheme } from "@/test/renderWithTheme";
import { Badge } from "../Badge";
import { lightTheme } from "@/theme/tokens.generated";

const FEEDBACK = ["success", "error", "warning", "info"] as const;

describe("Badge", () => {
  it.each(FEEDBACK)("applies the %s feedback palette", async (variant) => {
    const { getByText, getByTestId } = await renderWithTheme(
      <Badge testID="b" variant={variant}>
        {variant}
      </Badge>,
    );
    const bg = StyleSheet.flatten(getByTestId("b").props.style).backgroundColor;
    const fg = StyleSheet.flatten(getByText(variant).props.style).color;
    expect(bg).toBe(lightTheme.feedback[variant].background);
    expect(fg).toBe(lightTheme.feedback[variant].text);
  });

  it("falls back to layerTwo for the neutral variant", async () => {
    const { getByText, getByTestId } = await renderWithTheme(
      <Badge testID="b" variant="neutral">
        n
      </Badge>,
    );
    expect(StyleSheet.flatten(getByTestId("b").props.style).backgroundColor).toBe(
      lightTheme.layerTwo.background,
    );
    expect(StyleSheet.flatten(getByText("n").props.style).color).toBe(lightTheme.layerTwo.text);
  });
});
