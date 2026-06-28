import { View, Switch, Pressable } from "react-native";
import { Card } from "./ui/Card";
import { Text } from "./ui/Text";
import { useTheme } from "@/theme/useTheme";
import type { Filter } from "@/types";

interface Props {
  filter: Filter;
  onToggle: (id: number) => void;
  onPress: (id: number) => void;
}

export function FilterCard({ filter, onToggle, onPress }: Props) {
  const theme = useTheme();
  const details = [
    filter.city,
    filter.property_type,
    filter.min_price && `${filter.min_price}+`,
    filter.max_price && `max ${filter.max_price}`,
    filter.min_bedrooms && `${filter.min_bedrooms}+ bed`,
  ]
    .filter(Boolean)
    .join(" · ");

  return (
    <Pressable onPress={() => onPress(filter.id)} style={{ marginBottom: theme.space["150"] }}>
      <Card style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between" }}>
        <View style={{ flex: 1, marginRight: theme.space["150"] }}>
          <Text variant="heading-three">{filter.name}</Text>
          {details ? (
            <Text variant="body-small" color={theme.text.secondary} style={{ marginTop: theme.space["050"] }}>
              {details}
            </Text>
          ) : null}
        </View>
        <Switch value={filter.is_active} onValueChange={() => onToggle(filter.id)} />
      </Card>
    </Pressable>
  );
}
