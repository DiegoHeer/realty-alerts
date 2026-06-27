import { StyleSheet } from "react-native";
import { renderWithTheme } from "@/test/renderWithTheme";
import { Input } from "../Input";
import { lightTheme } from "@/theme/tokens.generated";

describe("Input", () => {
  it("applies the input palette and themed placeholder colour", async () => {
    const { getByTestId } = await renderWithTheme(<Input testID="in" placeholder="Email" />);
    const node = getByTestId("in");
    const flat = StyleSheet.flatten(node.props.style);
    expect(flat.backgroundColor).toBe(lightTheme.input.background);
    expect(flat.color).toBe(lightTheme.input.text);
    expect(flat.borderColor).toBe(lightTheme.input.border);
    expect(flat.borderWidth).toBe(1);
    expect(flat.borderRadius).toBe(lightTheme.radius["100"]);
    expect(node.props.placeholderTextColor).toBe(lightTheme.input.icon);
  });

  it("respects an explicit placeholderTextColor override", async () => {
    const { getByTestId } = await renderWithTheme(
      <Input testID="in" placeholder="Email" placeholderTextColor="#abcdef" />,
    );
    expect(getByTestId("in").props.placeholderTextColor).toBe("#abcdef");
  });
});
