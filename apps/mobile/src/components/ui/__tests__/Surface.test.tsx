import { StyleSheet, Text as RNText, useColorScheme } from "react-native";
import { renderWithTheme } from "@/test/renderWithTheme";
import { Surface } from "../Surface";
import { useThemeStore } from "@/theme/themeStore";
import { lightTheme, darkTheme } from "@/theme/tokens.generated";

// AsyncStorage is mocked globally in jest.setup.js. Here we only need to control
// the system colour scheme for the dark-reactivity case.
jest.mock("react-native/Libraries/Utilities/useColorScheme");

const mockedScheme = useColorScheme as jest.Mock;

describe("Surface", () => {
  beforeEach(() => {
    useThemeStore.setState({ mode: "system" });
    mockedScheme.mockReturnValue("light");
  });

  it("applies the layerOne palette, default radius and 1px border by default", async () => {
    const { getByTestId } = await renderWithTheme(
      <Surface testID="s">
        <RNText>x</RNText>
      </Surface>,
    );
    const flat = StyleSheet.flatten(getByTestId("s").props.style);
    expect(flat.backgroundColor).toBe(lightTheme.layerOne.background);
    expect(flat.borderColor).toBe(lightTheme.layerOne.border);
    expect(flat.borderWidth).toBe(1);
    expect(flat.borderRadius).toBe(lightTheme.radius["150"]);
  });

  it("applies chosen layer, radius, padding and soft shadow", async () => {
    const { getByTestId } = await renderWithTheme(
      <Surface testID="s" layer="two" radius="200" padding="300" shadow="sm">
        <RNText>x</RNText>
      </Surface>,
    );
    const flat = StyleSheet.flatten(getByTestId("s").props.style);
    expect(flat.backgroundColor).toBe(lightTheme.layerTwo.background);
    expect(flat.borderRadius).toBe(lightTheme.radius["200"]);
    expect(flat.padding).toBe(lightTheme.space["300"]);
    expect(flat.elevation).toBe(lightTheme.shadow.outer.soft.sm.elevation);
    expect(flat.shadowRadius).toBe(lightTheme.shadow.outer.soft.sm.shadowRadius);
  });

  it("reacts to the dark scheme", async () => {
    mockedScheme.mockReturnValue("dark");
    const { getByTestId } = await renderWithTheme(
      <Surface testID="s">
        <RNText>x</RNText>
      </Surface>,
    );
    const flat = StyleSheet.flatten(getByTestId("s").props.style);
    expect(flat.backgroundColor).toBe(darkTheme.layerOne.background);
  });
});
