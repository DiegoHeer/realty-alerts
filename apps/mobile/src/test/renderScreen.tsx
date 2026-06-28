import { render } from "@testing-library/react-native";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactElement } from "react";
import { ThemeProvider } from "@/theme/ThemeProvider";

// Wraps a screen in the providers it needs to render in isolation. Screen data
// hooks / api / router are mocked per-test with jest.mock; the QueryClient here
// satisfies any screen that calls useQuery directly (residence/[id], filter/[id]).
export function renderScreen(ui: ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>{ui}</ThemeProvider>
    </QueryClientProvider>,
  );
}
