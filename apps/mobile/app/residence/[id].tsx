import { View, Image, ScrollView, Linking, ActivityIndicator } from "react-native";
import { useLocalSearchParams } from "expo-router";
import { useQuery } from "@tanstack/react-query";
import { getResidence } from "@/api/residences";
import { Text } from "@/components/ui/Text";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { useTheme } from "@/theme/useTheme";

export default function ResidenceDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const residenceId = parseInt(id);
  const theme = useTheme();

  const { data: residence, isLoading } = useQuery({
    queryKey: ["residence", residenceId],
    queryFn: () => getResidence(residenceId),
    enabled: !isNaN(residenceId),
  });

  if (isLoading || !residence) {
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

  return (
    <ScrollView style={{ flex: 1, backgroundColor: theme.layerBase.background }}>
      {residence.image_url && (
        <Image source={{ uri: residence.image_url }} style={{ width: "100%", height: 250 }} resizeMode="cover" />
      )}

      <View style={{ padding: theme.space["200"] }}>
        <Text variant="heading-two" style={{ marginBottom: theme.space["100"] }}>
          {residence.title}
        </Text>
        <Text variant="heading-two" color={theme.link.default} style={{ marginBottom: theme.space["200"] }}>
          {residence.price}
        </Text>

        <Card style={{ marginBottom: theme.space["200"] }}>
          {[
            { label: "City", value: residence.city },
            { label: "Type", value: residence.property_type },
            { label: "Bedrooms", value: residence.bedrooms?.toString() },
            { label: "Area", value: residence.area_sqm ? `${residence.area_sqm} m2` : null },
            { label: "Website", value: residence.website },
          ].map(
            (d) =>
              d.value && (
                <View
                  key={d.label}
                  style={{
                    flexDirection: "row",
                    justifyContent: "space-between",
                    paddingVertical: theme.space["100"],
                  }}
                >
                  <Text color={theme.text.secondary}>{d.label}</Text>
                  <Text variant="label">{d.value}</Text>
                </View>
              ),
          )}
        </Card>

        <Button variant="primary" onPress={() => Linking.openURL(residence.detail_url)}>
          View on website
        </Button>
      </View>
    </ScrollView>
  );
}
