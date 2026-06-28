import { StyleSheet } from "react-native";
import { renderScreen } from "@/test/renderScreen";
import { lightTheme } from "@/theme/tokens.generated";
import ResidenceDetail from "../[id]";

jest.mock("expo-router", () => ({ useLocalSearchParams: () => ({ id: "1" }) }));
jest.mock("@/api/residences", () => ({
  getResidence: jest.fn().mockResolvedValue({
    id: 1,
    website: "funda",
    detail_url: "https://example.com/1",
    title: "Test Home",
    price: "€500.000",
    price_cents: 50000000,
    city: "Amsterdam",
    property_type: "Apartment",
    bedrooms: 3,
    area_sqm: 80,
    image_url: null,
    status: "active",
    scraped_at: "2026-01-01T00:00:00Z",
    created_at: "2026-01-01T00:00:00Z",
  }),
}));

describe("Residence detail screen", () => {
  it("renders the price in the link colour once loaded", async () => {
    const { findByText } = await renderScreen(<ResidenceDetail />);
    const price = await findByText("€500.000");
    expect(StyleSheet.flatten(price.props.style).color).toBe(lightTheme.link.default);
  });
});
