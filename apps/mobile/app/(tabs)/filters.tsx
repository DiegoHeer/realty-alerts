import { FlatList, View, Text, Pressable, RefreshControl, ActivityIndicator } from "react-native";
import { useRouter } from "expo-router";
import { useFilters, useToggleFilter } from "@/hooks/useFilters";
import { FilterCard } from "@/components/FilterCard";

export default function FiltersScreen() {
  const { data: filters, isLoading, refetch, isRefetching } = useFilters();
  const toggleMutation = useToggleFilter();
  const router = useRouter();

  if (isLoading) {
    return (
      <View style={{ flex: 1, justifyContent: "center", alignItems: "center" }}>
        <ActivityIndicator size="large" color="#2563eb" />
      </View>
    );
  }

  return (
    <View style={{ flex: 1 }}>
      <FlatList
        data={filters}
        keyExtractor={(item) => String(item.id)}
        renderItem={({ item }) => (
          <FilterCard
            filter={item}
            onToggle={(id) => toggleMutation.mutate(id)}
            onPress={(id) => router.push(`/filter/${id}`)}
          />
        )}
        contentContainerStyle={{ padding: 16 }}
        refreshControl={<RefreshControl refreshing={isRefetching} onRefresh={refetch} />}
        ListEmptyComponent={
          <View style={{ alignItems: "center", paddingTop: 60 }}>
            <Text style={{ fontSize: 16, color: "#6b7280" }}>No filters yet.</Text>
            <Text style={{ fontSize: 14, color: "#9ca3af", marginTop: 4 }}>
              Create a filter to get notified about new listings.
            </Text>
          </View>
        }
      />

      <Pressable
        onPress={() => router.push("/filter/create")}
        style={{
          position: "absolute",
          bottom: 24,
          right: 24,
          backgroundColor: "#2563eb",
          width: 56,
          height: 56,
          borderRadius: 28,
          alignItems: "center",
          justifyContent: "center",
          elevation: 4,
          shadowColor: "#000",
          shadowOffset: { width: 0, height: 2 },
          shadowOpacity: 0.25,
          shadowRadius: 4,
        }}
      >
        <Text style={{ color: "#fff", fontSize: 28, lineHeight: 30 }}>+</Text>
      </Pressable>
    </View>
  );
}
