import { api } from "./client";
import type { ScrapeRun } from "@/types";

export async function getScrapeRuns(website?: string): Promise<ScrapeRun[]> {
  const params: Record<string, string> = {};
  if (website) params.website = website;
  return api.get<ScrapeRun[]>("/api/v1/scrape-runs/", params);
}
