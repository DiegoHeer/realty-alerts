import { StyleSheet } from "react-native";
import { renderScreen } from "@/test/renderScreen";
import { lightTheme } from "@/theme/tokens.generated";
import HomeScreen from "../index";

jest.mock("expo-router", () => ({ useRouter: () => ({ push: jest.fn() }) }));
jest.mock("@/hooks/useResidences", () => ({
  useResidences: () => ({ data: [], isLoading: false, refetch: jest.fn(), isRefetching: false }),
}));

describe("Home screen", () => {
  it("renders the empty subtitle in the themed tertiary colour", async () => {
    const { getByText } = await renderScreen(<HomeScreen />);
    const subtitle = getByText(/Listings will appear/i);
    expect(StyleSheet.flatten(subtitle.props.style).color).toBe(lightTheme.text.tertiary);
  });
});
