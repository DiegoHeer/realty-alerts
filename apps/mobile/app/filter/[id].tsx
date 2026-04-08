import { View, Text, Pressable, Alert, ActivityIndicator } from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";
import { useQuery } from "@tanstack/react-query";
import { getFilter } from "@/api/filters";
import { useDeleteFilter, useToggleFilter } from "@/hooks/useFilters";

export default function FilterDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const filterId = parseInt(id);

  const { data: filter, isLoading } = useQuery({
    queryKey: ["filter", filterId],
    queryFn: () => getFilter(filterId),
    enabled: !isNaN(filterId),
  });

  const deleteMutation = useDeleteFilter();
  const toggleMutation = useToggleFilter();

  const handleDelete = () => {
    Alert.alert("Delete filter", `Delete "${filter?.name}"?`, [
      { text: "Cancel", style: "cancel" },
      {
        text: "Delete",
        style: "destructive",
        onPress: async () => {
          await deleteMutation.mutateAsync(filterId);
          router.back();
        },
      },
    ]);
  };

  if (isLoading || !filter) {
    return (
      <View style={{ flex: 1, justifyContent: "center", alignItems: "center" }}>
        <ActivityIndicator size="large" color="#2563eb" />
      </View>
    );
  }

  const details = [
    { label: "City", value: filter.city },
    { label: "Price range", value: [filter.min_price && `${filter.min_price}`, filter.max_price && `${filter.max_price}`].filter(Boolean).join(" - ") || null },
    { label: "Property type", value: filter.property_type },
    { label: "Min bedrooms", value: filter.min_bedrooms?.toString() },
    { label: "Min area", value: filter.min_area_sqm ? `${filter.min_area_sqm} m2` : null },
    { label: "Websites", value: filter.websites.length ? filter.websites.join(", ") : null },
    { label: "Active", value: filter.is_active ? "Yes" : "No" },
  ];

  return (
    <View style={{ flex: 1, backgroundColor: "#f9fafb", padding: 16 }}>
      <Text style={{ fontSize: 24, fontWeight: "700", marginBottom: 16 }}>{filter.name}</Text>

      <View style={{ backgroundColor: "#fff", borderRadius: 12, padding: 16, marginBottom: 24 }}>
        {details.map(
          (d) =>
            d.value && (
              <View key={d.label} style={{ flexDirection: "row", justifyContent: "space-between", paddingVertical: 8 }}>
                <Text style={{ color: "#6b7280" }}>{d.label}</Text>
                <Text style={{ fontWeight: "500" }}>{d.value}</Text>
              </View>
            ),
        )}
      </View>

      <Pressable
        onPress={() => toggleMutation.mutate(filterId)}
        style={{ backgroundColor: "#e0e7ff", padding: 16, borderRadius: 8, alignItems: "center", marginBottom: 12 }}
      >
        <Text style={{ color: "#3730a3", fontWeight: "600" }}>
          {filter.is_active ? "Disable" : "Enable"} notifications
        </Text>
      </Pressable>

      <Pressable
        onPress={handleDelete}
        style={{ backgroundColor: "#fee2e2", padding: 16, borderRadius: 8, alignItems: "center" }}
      >
        <Text style={{ color: "#991b1b", fontWeight: "600" }}>Delete filter</Text>
      </Pressable>
    </View>
  );
}
