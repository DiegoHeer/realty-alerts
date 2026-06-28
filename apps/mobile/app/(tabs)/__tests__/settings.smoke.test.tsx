import { renderScreen } from "@/test/renderScreen";
import SettingsScreen from "../settings";

jest.mock("@/stores/authStore", () => ({
  useAuthStore: () => ({ user: { email: "test@example.com" }, signOut: jest.fn() }),
}));
jest.mock("@/hooks/useScrapeRuns", () => ({
  useScrapeRuns: () => ({ data: [], isLoading: false }),
}));

describe("Settings screen", () => {
  it("renders under the theme without crashing", async () => {
    const { getByText } = await renderScreen(<SettingsScreen />);
    expect(getByText("test@example.com")).toBeTruthy();
  });
});
