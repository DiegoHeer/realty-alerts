import { create } from "zustand";

// Auth not implemented; tracked in follow-up PR.
// These are minimal local types to keep consumers compiling.
export interface AuthUser {
  id: string;
  email: string | null;
}

export interface AuthSession {
  access_token: string;
  user: AuthUser;
}

interface AuthState {
  session: AuthSession | null;
  user: AuthUser | null;
  isLoading: boolean;
  initialize: () => Promise<void>;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
}

const NOT_IMPLEMENTED = new Error("Auth not implemented; pending follow-up PR");

export const useAuthStore = create<AuthState>((set) => ({
  session: null,
  user: null,
  isLoading: false,

  initialize: async () => {
    set({ session: null, user: null, isLoading: false });
  },

  signIn: async (_email: string, _password: string) => {
    throw NOT_IMPLEMENTED;
  },

  signUp: async (_email: string, _password: string) => {
    throw NOT_IMPLEMENTED;
  },

  signOut: async () => {
    set({ session: null, user: null });
  },
}));
