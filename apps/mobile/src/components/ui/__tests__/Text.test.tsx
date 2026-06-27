import { StyleSheet } from "react-native";
import { renderWithTheme } from "@/test/renderWithTheme";
import { Text } from "../Text";
import { lightTheme } from "@/theme/tokens.generated";

describe("Text", () => {
  it("applies the body variant typography and layerBase text colour by default", async () => {
    const { getByText } = await renderWithTheme(<Text>Hello</Text>);
    const flat = StyleSheet.flatten(getByText("Hello").props.style);
    expect(flat).toMatchObject(lightTheme.type.body);
    expect(flat.color).toBe(lightTheme.layerBase.text);
  });

  it("applies a chosen variant and a colour override", async () => {
    const { getByText } = await renderWithTheme(
      <Text variant="heading-one" color="#123456">
        Hi
      </Text>,
    );
    const flat = StyleSheet.flatten(getByText("Hi").props.style);
    expect(flat).toMatchObject(lightTheme.type["heading-one"]);
    expect(flat.color).toBe("#123456");
  });
});
