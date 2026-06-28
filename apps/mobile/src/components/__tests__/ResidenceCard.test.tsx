import { StyleSheet } from "react-native";
import { renderWithTheme } from "@/test/renderWithTheme";
import { ResidenceCard } from "@/components/ResidenceCard";
import { lightTheme } from "@/theme/tokens.generated";
import type { Residence } from "@/types";

jest.mock("expo-router", () => ({ useRouter: () => ({ push: jest.fn() }) }));

const residence: Residence = {
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
};

describe("ResidenceCard", () => {
  it("renders title, link-coloured price and secondary meta", async () => {
    const { getByText } = await renderWithTheme(<ResidenceCard residence={residence} />);
    expect(getByText("Test Home")).toBeTruthy();
    expect(StyleSheet.flatten(getByText("€500.000").props.style).color).toBe(lightTheme.link.default);
    expect(StyleSheet.flatten(getByText("Amsterdam").props.style).color).toBe(lightTheme.text.secondary);
  });
});
