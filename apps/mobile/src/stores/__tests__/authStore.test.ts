import { useAuthStore, type AuthSession } from "@/stores/authStore";

const seedSession: AuthSession = {
  access_token: "token-abc",
  user: { id: "u1", email: "user@example.com" },
};

describe("useAuthStore", () => {
  beforeEach(() => {
    useAuthStore.setState({ session: null, user: null, isLoading: false });
  });

  it("starts with no session and not loading", () => {
    const state = useAuthStore.getState();
    expect(state.session).toBeNull();
    expect(state.user).toBeNull();
    expect(state.isLoading).toBe(false);
  });

  it("initialize() resets to a clean unauthenticated state", async () => {
    useAuthStore.setState({ session: seedSession, user: seedSession.user, isLoading: true });

    await useAuthStore.getState().initialize();

    const state = useAuthStore.getState();
    expect(state.session).toBeNull();
    expect(state.user).toBeNull();
    expect(state.isLoading).toBe(false);
  });

  it("signOut() clears session and user", async () => {
    useAuthStore.setState({ session: seedSession, user: seedSession.user });

    await useAuthStore.getState().signOut();

    const state = useAuthStore.getState();
    expect(state.session).toBeNull();
    expect(state.user).toBeNull();
  });

  it.each(["signIn", "signUp"] as const)(
    "%s() throws because auth is not implemented yet",
    async (method) => {
      await expect(
        useAuthStore.getState()[method]("user@example.com", "pw"),
      ).rejects.toThrow(/not implemented/i);
    },
  );
});
