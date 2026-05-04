import { View, Text, Image, Pressable } from "react-native";
import { useRouter } from "expo-router";
import type { Residence } from "@/types";

interface Props {
  residence: Residence;
}

export function ResidenceCard({ residence }: Props) {
  const router = useRouter();

  return (
    <Pressable
      onPress={() => router.push(`/residence/${residence.id}`)}
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
      {residence.image_url && (
        <Image
          source={{ uri: residence.image_url }}
          style={{ width: "100%", height: 180 }}
          resizeMode="cover"
        />
      )}
      <View style={{ padding: 12 }}>
        <Text style={{ fontSize: 16, fontWeight: "600", marginBottom: 4 }}>
          {residence.title}
        </Text>
        <Text style={{ fontSize: 18, fontWeight: "700", color: "#2563eb", marginBottom: 4 }}>
          {residence.price}
        </Text>
        <View style={{ flexDirection: "row", gap: 8 }}>
          <Text style={{ color: "#6b7280", fontSize: 13 }}>{residence.city}</Text>
          {residence.property_type && (
            <Text style={{ color: "#6b7280", fontSize: 13 }}>{residence.property_type}</Text>
          )}
          {residence.bedrooms && (
            <Text style={{ color: "#6b7280", fontSize: 13 }}>{residence.bedrooms} bed</Text>
          )}
          {residence.area_sqm && (
            <Text style={{ color: "#6b7280", fontSize: 13 }}>{residence.area_sqm} m²</Text>
          )}
        </View>
      </View>
    </Pressable>
  );
}
