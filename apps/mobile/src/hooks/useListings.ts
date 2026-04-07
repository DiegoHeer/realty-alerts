import { useQuery } from "@tanstack/react-query";
import { getListings, type ListingParams } from "@/api/listings";

export function useListings(params?: ListingParams) {
  return useQuery({
    queryKey: ["listings", params],
    queryFn: () => getListings(params),
  });
}
