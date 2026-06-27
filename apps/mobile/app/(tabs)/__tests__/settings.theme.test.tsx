import { render, screen, fireEvent } from "@testing-library/react-native";
import { ThemeModeSelector } from "../settings";
import { useThemeStore } from "@/theme/themeStore";

// eslint-disable-next-line @typescript-eslint/no-require-imports
jest.mock("@react-native-async-storage/async-storage", () => require("@react-native-async-storage/async-storage/jest/async-storage-mock"));

describe("ThemeModeSelector", () => {
  beforeEach(() => useThemeStore.setState({ mode: "system" }));

  it("sets the mode to dark when Dark is pressed", async () => {
    await render(<ThemeModeSelector />);
    fireEvent.press(screen.getByText("Dark"));
    expect(useThemeStore.getState().mode).toBe("dark");
  });
});
