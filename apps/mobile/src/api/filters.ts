import { api } from "./client";
import type { Filter, FilterCreate, FilterUpdate } from "@/types";

export async function getFilters(): Promise<Filter[]> {
  return api.get<Filter[]>("/api/v1/filters/");
}

export async function getFilter(id: number): Promise<Filter> {
  return api.get<Filter>(`/api/v1/filters/${id}`);
}

export async function createFilter(data: FilterCreate): Promise<Filter> {
  return api.post<Filter>("/api/v1/filters/", data);
}

export async function updateFilter(id: number, data: FilterUpdate): Promise<Filter> {
  return api.patch<Filter>(`/api/v1/filters/${id}`, data);
}

export async function deleteFilter(id: number): Promise<void> {
  return api.delete(`/api/v1/filters/${id}`);
}

export async function toggleFilter(id: number): Promise<Filter> {
  return api.post<Filter>(`/api/v1/filters/${id}/toggle`);
}
