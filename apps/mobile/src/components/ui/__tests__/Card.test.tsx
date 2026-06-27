import { StyleSheet, Text as RNText } from "react-native";
import { renderWithTheme } from "@/test/renderWithTheme";
import { Card } from "../Card";
import { lightTheme } from "@/theme/tokens.generated";

describe("Card", () => {
  it("renders a layerOne surface with default sm elevation and padding", async () => {
    const { getByTestId } = await renderWithTheme(
      <Card testID="c">
        <RNText>x</RNText>
      </Card>,
    );
    const flat = StyleSheet.flatten(getByTestId("c").props.style);
    expect(flat.backgroundColor).toBe(lightTheme.layerOne.background);
    expect(flat.elevation).toBe(lightTheme.shadow.outer.soft.sm.elevation);
    expect(flat.padding).toBe(lightTheme.space["200"]);
    expect(flat.borderRadius).toBe(lightTheme.radius["150"]);
  });

  it("allows overriding the shadow level", async () => {
    const { getByTestId } = await renderWithTheme(
      <Card testID="c" shadow="md">
        <RNText>x</RNText>
      </Card>,
    );
    const flat = StyleSheet.flatten(getByTestId("c").props.style);
    expect(flat.elevation).toBe(lightTheme.shadow.outer.soft.md.elevation);
  });
});
