import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getFilters,
  createFilter,
  updateFilter,
  deleteFilter,
  toggleFilter,
} from "@/api/filters";
import type { FilterCreate, FilterUpdate } from "@/types";

export function useFilters() {
  return useQuery({
    queryKey: ["filters"],
    queryFn: getFilters,
  });
}

export function useCreateFilter() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: FilterCreate) => createFilter(data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["filters"] }),
  });
}

export function useUpdateFilter() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: FilterUpdate }) => updateFilter(id, data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["filters"] }),
  });
}

export function useDeleteFilter() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => deleteFilter(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["filters"] }),
  });
}

export function useToggleFilter() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => toggleFilter(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["filters"] }),
  });
}
