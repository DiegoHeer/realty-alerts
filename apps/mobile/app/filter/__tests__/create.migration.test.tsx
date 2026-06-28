import { renderScreen } from "@/test/renderScreen";
import CreateFilter from "../create";

jest.mock("expo-router", () => ({ useRouter: () => ({ back: jest.fn() }) }));
jest.mock("@/hooks/useFilters", () => ({
  useCreateFilter: () => ({ mutateAsync: jest.fn().mockResolvedValue({ id: 1 }), isPending: false }),
}));

describe("Create filter screen", () => {
  it("renders the form under the theme without crashing", async () => {
    const { getByText } = await renderScreen(<CreateFilter />);
    expect(getByText(/Name/i)).toBeTruthy();
  });
});
