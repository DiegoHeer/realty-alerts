import { renderScreen } from "@/test/renderScreen";
import FilterDetail from "../[id]";

jest.mock("expo-router", () => ({
  useLocalSearchParams: () => ({ id: "1" }),
  useRouter: () => ({ push: jest.fn(), back: jest.fn() }),
}));
jest.mock("@/api/filters", () => ({
  getFilter: jest.fn().mockResolvedValue({
    id: 1,
    user_id: "u1",
    name: "Amsterdam Filter",
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
  }),
}));
jest.mock("@/hooks/useFilters", () => ({
  useDeleteFilter: () => ({ mutateAsync: jest.fn() }),
  useToggleFilter: () => ({ mutate: jest.fn() }),
}));

describe("Filter detail screen", () => {
  it("renders the filter name once loaded", async () => {
    const { findByText } = await renderScreen(<FilterDetail />);
    expect(await findByText("Amsterdam Filter")).toBeTruthy();
  });
});
