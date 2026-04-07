import { FlatList, View, Text, RefreshControl, ActivityIndicator } from "react-native";
import { useListings } from "@/hooks/useListings";
import { ListingCard } from "@/components/ListingCard";

export default function HomeScreen() {
  const { data: listings, isLoading, refetch, isRefetching } = useListings();

  if (isLoading) {
    return (
      <View style={{ flex: 1, justifyContent: "center", alignItems: "center" }}>
        <ActivityIndicator size="large" color="#2563eb" />
      </View>
    );
  }

  return (
    <FlatList
      data={listings}
      keyExtractor={(item) => String(item.id)}
      renderItem={({ item }) => <ListingCard listing={item} />}
      contentContainerStyle={{ padding: 16 }}
      refreshControl={<RefreshControl refreshing={isRefetching} onRefresh={refetch} />}
      ListEmptyComponent={
        <View style={{ alignItems: "center", paddingTop: 60 }}>
          <Text style={{ fontSize: 16, color: "#6b7280" }}>No listings yet.</Text>
          <Text style={{ fontSize: 14, color: "#9ca3af", marginTop: 4 }}>
            Listings will appear once the scraper runs.
          </Text>
        </View>
      }
    />
  );
}
