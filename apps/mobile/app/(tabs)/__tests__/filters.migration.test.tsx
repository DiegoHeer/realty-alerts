import { StyleSheet } from "react-native";
import { renderScreen } from "@/test/renderScreen";
import { lightTheme } from "@/theme/tokens.generated";
import FiltersScreen from "../filters";

jest.mock("expo-router", () => ({ useRouter: () => ({ push: jest.fn() }) }));
jest.mock("@/hooks/useFilters", () => ({
  useFilters: () => ({ data: [], isLoading: false, refetch: jest.fn(), isRefetching: false }),
  useToggleFilter: () => ({ mutate: jest.fn() }),
}));

describe("Filters screen", () => {
  it("renders the empty state with themed tertiary text", async () => {
    const { getByText } = await renderScreen(<FiltersScreen />);
    const subtitle = getByText(/Create a filter/i);
    expect(StyleSheet.flatten(subtitle.props.style).color).toBe(lightTheme.text.tertiary);
  });
});
