import { StyleSheet } from "react-native";
import { renderScreen } from "@/test/renderScreen";
import { lightTheme } from "@/theme/tokens.generated";
import LoginScreen from "../login";

jest.mock("expo-router", () => ({ Link: ({ children }: { children: React.ReactNode }) => children }));
jest.mock("@/stores/authStore", () => ({
  useAuthStore: (selector: (s: { signIn: () => Promise<void> }) => unknown) =>
    selector({ signIn: jest.fn().mockResolvedValue(undefined) }),
}));

describe("Login screen", () => {
  it("renders the sign-in label in the button text colour", async () => {
    const { getByText } = await renderScreen(<LoginScreen />);
    const label = getByText("Sign in");
    expect(StyleSheet.flatten(label.props.style).color).toBe(lightTheme.buttonPrimary.text.default);
  });
});
