import { useThemeStore } from "../themeStore";

jest.mock("@react-native-async-storage/async-storage", () =>
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  require("@react-native-async-storage/async-storage/jest/async-storage-mock"),
);

describe("themeStore", () => {
  beforeEach(() => useThemeStore.setState({ mode: "system" }));

  it("defaults to system mode", () => {
    expect(useThemeStore.getState().mode).toBe("system");
  });

  it("updates mode via setMode", () => {
    useThemeStore.getState().setMode("dark");
    expect(useThemeStore.getState().mode).toBe("dark");
  });
});
