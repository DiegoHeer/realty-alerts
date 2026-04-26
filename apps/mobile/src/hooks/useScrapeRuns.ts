import { useQuery } from "@tanstack/react-query";
import { getScrapeRuns } from "@/api/scrapeRuns";

export function useScrapeRuns(website?: string) {
  return useQuery({
    queryKey: ["scrapeRuns", website],
    queryFn: () => getScrapeRuns(website),
  });
}
