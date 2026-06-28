import { View, Image, Pressable } from "react-native";
import { useRouter } from "expo-router";
import { Card } from "./ui/Card";
import { Text } from "./ui/Text";
import { useTheme } from "@/theme/useTheme";
import type { Residence } from "@/types";

interface Props {
  residence: Residence;
}

export function ResidenceCard({ residence }: Props) {
  const router = useRouter();
  const theme = useTheme();

  const meta = [
    residence.city,
    residence.property_type,
    residence.bedrooms ? `${residence.bedrooms} bed` : null,
    residence.area_sqm ? `${residence.area_sqm} m²` : null,
  ].filter((v): v is string => Boolean(v));

  return (
    <Pressable
      onPress={() => router.push(`/residence/${residence.id}`)}
      style={{ marginBottom: theme.space["150"] }}
    >
      <Card padding="none" style={{ overflow: "hidden" }}>
        {residence.image_url && (
          <Image
            source={{ uri: residence.image_url }}
            style={{ width: "100%", height: 180 }}
            resizeMode="cover"
          />
        )}
        <View style={{ padding: theme.space["150"] }}>
          <Text variant="heading-three">{residence.title}</Text>
          <Text
            variant="heading-three"
            color={theme.link.default}
            style={{ marginTop: theme.space["050"] }}
          >
            {residence.price}
          </Text>
          <View style={{ flexDirection: "row", flexWrap: "wrap", gap: theme.space["100"], marginTop: theme.space["050"] }}>
            {meta.map((m, i) => (
              <Text key={i} variant="body-small" color={theme.text.secondary}>
                {m}
              </Text>
            ))}
          </View>
        </View>
      </Card>
    </Pressable>
  );
}
