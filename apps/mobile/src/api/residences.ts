import { api } from "./client";
import type { Residence } from "@/types";

export interface ResidenceParams {
  city?: string;
  min_price?: number;
  max_price?: number;
  property_type?: string;
  website?: string;
  page?: number;
  page_size?: number;
}

export async function getResidences(params?: ResidenceParams): Promise<Residence[]> {
  const query: Record<string, string> = {};
  if (params?.city) query.city = params.city;
  if (params?.min_price != null) query.min_price = String(params.min_price);
  if (params?.max_price != null) query.max_price = String(params.max_price);
  if (params?.property_type) query.property_type = params.property_type;
  if (params?.website) query.website = params.website;
  if (params?.page != null) query.page = String(params.page);
  if (params?.page_size != null) query.page_size = String(params.page_size);

  return api.get<Residence[]>("/api/v1/residences/", query);
}

export async function getResidence(id: number): Promise<Residence> {
  return api.get<Residence>(`/api/v1/residences/${id}`);
}
