import { View, Alert, ActivityIndicator } from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";
import { useQuery } from "@tanstack/react-query";
import { getFilter } from "@/api/filters";
import { useDeleteFilter, useToggleFilter } from "@/hooks/useFilters";
import { Text } from "@/components/ui/Text";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { useTheme } from "@/theme/useTheme";

export default function FilterDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const filterId = parseInt(id);
  const theme = useTheme();

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
      <View
        style={{
          flex: 1,
          justifyContent: "center",
          alignItems: "center",
          backgroundColor: theme.layerBase.background,
        }}
      >
        <ActivityIndicator size="large" color={theme.link.default} />
      </View>
    );
  }

  const details = [
    { label: "City", value: filter.city },
    {
      label: "Price range",
      value:
        [filter.min_price && `${filter.min_price}`, filter.max_price && `${filter.max_price}`].filter(Boolean).join(" - ") ||
        null,
    },
    { label: "Property type", value: filter.property_type },
    { label: "Min bedrooms", value: filter.min_bedrooms?.toString() },
    { label: "Min area", value: filter.min_area_sqm ? `${filter.min_area_sqm} m2` : null },
    { label: "Websites", value: filter.websites.length ? filter.websites.join(", ") : null },
    { label: "Active", value: filter.is_active ? "Yes" : "No" },
  ];

  return (
    <View style={{ flex: 1, backgroundColor: theme.layerBase.background, padding: theme.space["200"] }}>
      <Text variant="heading-two" style={{ marginBottom: theme.space["200"] }}>
        {filter.name}
      </Text>

      <Card style={{ marginBottom: theme.space["300"] }}>
        {details.map(
          (d) =>
            d.value && (
              <View
                key={d.label}
                style={{ flexDirection: "row", justifyContent: "space-between", paddingVertical: theme.space["100"] }}
              >
                <Text color={theme.text.secondary}>{d.label}</Text>
                <Text variant="label">{d.value}</Text>
              </View>
            ),
        )}
      </Card>

      <Button
        variant="secondary"
        onPress={() => toggleMutation.mutate(filterId)}
        style={{ marginBottom: theme.space["150"] }}
      >
        {`${filter.is_active ? "Disable" : "Enable"} notifications`}
      </Button>

      <Button variant="destructive" onPress={handleDelete}>
        Delete filter
      </Button>
    </View>
  );
}
