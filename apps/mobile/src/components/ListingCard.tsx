import { View, Text, Image, Pressable, Linking } from "react-native";
import type { Listing } from "@/types";

interface Props {
  listing: Listing;
}

export function ListingCard({ listing }: Props) {
  return (
    <Pressable
      onPress={() => Linking.openURL(listing.detail_url)}
      style={{
        backgroundColor: "#fff",
        borderRadius: 12,
        marginBottom: 12,
        overflow: "hidden",
        elevation: 2,
        shadowColor: "#000",
        shadowOffset: { width: 0, height: 1 },
        shadowOpacity: 0.1,
        shadowRadius: 3,
      }}
    >
      {listing.image_url && (
        <Image
          source={{ uri: listing.image_url }}
          style={{ width: "100%", height: 180 }}
          resizeMode="cover"
        />
      )}
      <View style={{ padding: 12 }}>
        <Text style={{ fontSize: 16, fontWeight: "600", marginBottom: 4 }}>
          {listing.title}
        </Text>
        <Text style={{ fontSize: 18, fontWeight: "700", color: "#2563eb", marginBottom: 4 }}>
          {listing.price}
        </Text>
        <View style={{ flexDirection: "row", gap: 8 }}>
          <Text style={{ color: "#6b7280", fontSize: 13 }}>{listing.city}</Text>
          {listing.property_type && (
            <Text style={{ color: "#6b7280", fontSize: 13 }}>{listing.property_type}</Text>
          )}
          {listing.bedrooms && (
            <Text style={{ color: "#6b7280", fontSize: 13 }}>{listing.bedrooms} bed</Text>
          )}
          {listing.area_sqm && (
            <Text style={{ color: "#6b7280", fontSize: 13 }}>{listing.area_sqm} m²</Text>
          )}
        </View>
      </View>
    </Pressable>
  );
}
