import { View, Text, Image, Pressable, ScrollView, Linking, ActivityIndicator } from "react-native";
import { useLocalSearchParams } from "expo-router";
import { useQuery } from "@tanstack/react-query";
import { getListing } from "@/api/listings";

export default function ListingDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const listingId = parseInt(id);

  const { data: listing, isLoading } = useQuery({
    queryKey: ["listing", listingId],
    queryFn: () => getListing(listingId),
    enabled: !isNaN(listingId),
  });

  if (isLoading || !listing) {
    return (
      <View style={{ flex: 1, justifyContent: "center", alignItems: "center" }}>
        <ActivityIndicator size="large" color="#2563eb" />
      </View>
    );
  }

  return (
    <ScrollView style={{ flex: 1, backgroundColor: "#f9fafb" }}>
      {listing.image_url && (
        <Image source={{ uri: listing.image_url }} style={{ width: "100%", height: 250 }} resizeMode="cover" />
      )}

      <View style={{ padding: 16 }}>
        <Text style={{ fontSize: 22, fontWeight: "700", marginBottom: 8 }}>{listing.title}</Text>
        <Text style={{ fontSize: 24, fontWeight: "700", color: "#2563eb", marginBottom: 16 }}>{listing.price}</Text>

        <View style={{ backgroundColor: "#fff", borderRadius: 12, padding: 16, marginBottom: 16 }}>
          {[
            { label: "City", value: listing.city },
            { label: "Type", value: listing.property_type },
            { label: "Bedrooms", value: listing.bedrooms?.toString() },
            { label: "Area", value: listing.area_sqm ? `${listing.area_sqm} m2` : null },
            { label: "Website", value: listing.website },
          ].map(
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
          onPress={() => Linking.openURL(listing.detail_url)}
          style={{
            backgroundColor: "#2563eb",
            padding: 16,
            borderRadius: 8,
            alignItems: "center",
          }}
        >
          <Text style={{ color: "#fff", fontWeight: "600", fontSize: 16 }}>View on website</Text>
        </Pressable>
      </View>
    </ScrollView>
  );
}
