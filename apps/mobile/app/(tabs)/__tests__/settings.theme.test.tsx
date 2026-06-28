import { fireEvent, screen } from "@testing-library/react-native";
import { StyleSheet } from "react-native";
import { renderWithTheme } from "@/test/renderWithTheme";
import { ThemeModeSelector } from "../settings";
import { useThemeStore } from "@/theme/themeStore";
import { lightTheme } from "@/theme/tokens.generated";

describe("ThemeModeSelector", () => {
  beforeEach(() => useThemeStore.setState({ mode: "system" }));

  it("sets the mode to dark when Dark is pressed", async () => {
    await renderWithTheme(<ThemeModeSelector />);
    fireEvent.press(screen.getByText("Dark"));
    expect(useThemeStore.getState().mode).toBe("dark");
  });

  it("highlights the active segment with the layerTwo background", async () => {
    await renderWithTheme(<ThemeModeSelector />);
    const active = screen.getByText("System").parent;
    expect(StyleSheet.flatten(active?.props.style).backgroundColor).toBe(lightTheme.layerTwo.background);
  });
});
