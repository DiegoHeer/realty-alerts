import { useQuery } from "@tanstack/react-query";
import { getResidences, type ResidenceParams } from "@/api/residences";

export function useResidences(params?: ResidenceParams) {
  return useQuery({
    queryKey: ["residences", params],
    queryFn: () => getResidences(params),
  });
}
