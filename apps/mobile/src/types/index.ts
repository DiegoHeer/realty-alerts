export interface UserProfile {
  email: string | null;
  timezone: string;
}

export interface UserUpdate {
  timezone?: string;
}

export interface Residence {
  id: number;
  website: string;
  detail_url: string;
  title: string;
  price: string;
  price_cents: number | null;
  city: string;
  property_type: string | null;
  bedrooms: number | null;
  area_sqm: number | null;
  image_url: string | null;
  status: string;
  scraped_at: string;
  created_at: string;
}

export interface Filter {
  id: number;
  user_id: string;
  name: string;
  city: string | null;
  min_price: number | null;
  max_price: number | null;
  property_type: string | null;
  min_bedrooms: number | null;
  min_area_sqm: number | null;
  websites: string[];
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface FilterCreate {
  name: string;
  city?: string;
  min_price?: number;
  max_price?: number;
  property_type?: string;
  min_bedrooms?: number;
  min_area_sqm?: number;
  websites?: string[];
  is_active?: boolean;
}

export type FilterUpdate = Partial<FilterCreate>;

export interface ScrapeRun {
  id: number;
  website: string;
  started_at: string;
  finished_at: string | null;
  status: "running" | "success" | "failed";
  listings_found: number;
  new_residences_count: number;
  new_listings_count: number;
  error_message: string | null;
  duration_seconds: number | null;
}
