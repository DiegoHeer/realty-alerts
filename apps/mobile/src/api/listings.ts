import { api } from "./client";
import type { Listing } from "@/types";

export interface ListingParams {
  city?: string;
  min_price?: number;
  max_price?: number;
  property_type?: string;
  website?: string;
  page?: number;
  page_size?: number;
}

export async function getListings(params?: ListingParams): Promise<Listing[]> {
  const query: Record<string, string> = {};
  if (params?.city) query.city = params.city;
  if (params?.min_price != null) query.min_price = String(params.min_price);
  if (params?.max_price != null) query.max_price = String(params.max_price);
  if (params?.property_type) query.property_type = params.property_type;
  if (params?.website) query.website = params.website;
  if (params?.page != null) query.page = String(params.page);
  if (params?.page_size != null) query.page_size = String(params.page_size);

  return api.get<Listing[]>("/api/v1/listings/", query);
}

export async function getListing(id: number): Promise<Listing> {
  return api.get<Listing>(`/api/v1/listings/${id}`);
}
