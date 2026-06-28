import { StyleSheet } from "react-native";
import { renderWithTheme } from "@/test/renderWithTheme";
import { FilterCard } from "@/components/FilterCard";
import { lightTheme } from "@/theme/tokens.generated";
import type { Filter } from "@/types";

const filter: Filter = {
  id: 1,
  user_id: "u1",
  name: "My Filter",
  city: "Amsterdam",
  min_price: 1000,
  max_price: 2000,
  property_type: "Apartment",
  min_bedrooms: 2,
  min_area_sqm: null,
  websites: ["funda"],
  is_active: true,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

describe("FilterCard", () => {
  it("renders the name and secondary-coloured details", async () => {
    const { getByText } = await renderWithTheme(
      <FilterCard filter={filter} onToggle={() => {}} onPress={() => {}} />,
    );
    expect(getByText("My Filter")).toBeTruthy();
    const details = getByText(/Amsterdam/);
    expect(StyleSheet.flatten(details.props.style).color).toBe(lightTheme.text.secondary);
  });
});
