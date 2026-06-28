import { StyleSheet } from "react-native";
import { renderScreen } from "@/test/renderScreen";
import { lightTheme } from "@/theme/tokens.generated";
import RegisterScreen from "../register";

jest.mock("expo-router", () => ({ Link: ({ children }: { children: React.ReactNode }) => children }));
jest.mock("@/stores/authStore", () => ({
  useAuthStore: (selector: (s: { signUp: () => Promise<void> }) => unknown) =>
    selector({ signUp: jest.fn().mockResolvedValue(undefined) }),
}));

describe("Register screen", () => {
  it("renders the submit label in the button text colour", async () => {
    const { getByText } = await renderScreen(<RegisterScreen />);
    const label = getByText("Register");
    expect(StyleSheet.flatten(label.props.style).color).toBe(lightTheme.buttonPrimary.text.default);
  });
});
