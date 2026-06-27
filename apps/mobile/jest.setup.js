// Global jest setup. AsyncStorage's native module is null under jest, so mock it
// once here — every themed-component test renders through ThemeProvider -> themeStore,
// which imports AsyncStorage at module load.
jest.mock("@react-native-async-storage/async-storage", () =>
  require("@react-native-async-storage/async-storage/jest/async-storage-mock"),
);
