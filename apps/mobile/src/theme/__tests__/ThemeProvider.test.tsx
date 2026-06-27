import { render, screen } from "@testing-library/react-native";
import { Text, useColorScheme } from "react-native";
import { ThemeProvider } from "../ThemeProvider";
import { useTheme } from "../useTheme";
import { useThemeStore } from "../themeStore";
import { lightTheme, darkTheme } from "../tokens.generated";

jest.mock("@react-native-async-storage/async-storage", () =>
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  require("@react-native-async-storage/async-storage/jest/async-storage-mock"),
);
jest.mock("react-native/Libraries/Utilities/useColorScheme");

function Probe() {
  const theme = useTheme();
  return <Text testID="bg">{theme.layerBase.background}</Text>;
}

const mockedScheme = useColorScheme as jest.Mock;

describe("ThemeProvider", () => {
  beforeEach(() => useThemeStore.setState({ mode: "system" }));

  it("uses the dark theme when system is dark and mode is system", async () => {
    mockedScheme.mockReturnValue("dark");
    await render(
      <ThemeProvider>
        <Probe />
      </ThemeProvider>,
    );
    expect(screen.getByTestId("bg").props.children).toBe(darkTheme.layerBase.background);
  });

  it("honours a manual light override regardless of system", async () => {
    mockedScheme.mockReturnValue("dark");
    useThemeStore.setState({ mode: "light" });
    await render(
      <ThemeProvider>
        <Probe />
      </ThemeProvider>,
    );
    expect(screen.getByTestId("bg").props.children).toBe(lightTheme.layerBase.background);
  });
});
