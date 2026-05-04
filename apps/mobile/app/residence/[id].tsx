import { View, Text, Image, Pressable, ScrollView, Linking, ActivityIndicator } from "react-native";
import { useLocalSearchParams } from "expo-router";
import { useQuery } from "@tanstack/react-query";
import { getResidence } from "@/api/residences";

export default function ResidenceDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const residenceId = parseInt(id);

  const { data: residence, isLoading } = useQuery({
    queryKey: ["residence", residenceId],
    queryFn: () => getResidence(residenceId),
    enabled: !isNaN(residenceId),
  });

  if (isLoading || !residence) {
    return (
      <View style={{ flex: 1, justifyContent: "center", alignItems: "center" }}>
        <ActivityIndicator size="large" color="#2563eb" />
      </View>
    );
  }

  return (
    <ScrollView style={{ flex: 1, backgroundColor: "#f9fafb" }}>
      {residence.image_url && (
        <Image source={{ uri: residence.image_url }} style={{ width: "100%", height: 250 }} resizeMode="cover" />
      )}

      <View style={{ padding: 16 }}>
        <Text style={{ fontSize: 22, fontWeight: "700", marginBottom: 8 }}>{residence.title}</Text>
        <Text style={{ fontSize: 24, fontWeight: "700", color: "#2563eb", marginBottom: 16 }}>{residence.price}</Text>

        <View style={{ backgroundColor: "#fff", borderRadius: 12, padding: 16, marginBottom: 16 }}>
          {[
            { label: "City", value: residence.city },
            { label: "Type", value: residence.property_type },
            { label: "Bedrooms", value: residence.bedrooms?.toString() },
            { label: "Area", value: residence.area_sqm ? `${residence.area_sqm} m2` : null },
            { label: "Website", value: residence.website },
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
          onPress={() => Linking.openURL(residence.detail_url)}
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
