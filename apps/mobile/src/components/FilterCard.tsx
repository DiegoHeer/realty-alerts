import { View, Text, Switch, Pressable } from "react-native";
import type { Filter } from "@/types";

interface Props {
  filter: Filter;
  onToggle: (id: number) => void;
  onPress: (id: number) => void;
}

export function FilterCard({ filter, onToggle, onPress }: Props) {
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
    <Pressable
      onPress={() => onPress(filter.id)}
      style={{
        backgroundColor: "#fff",
        borderRadius: 12,
        padding: 16,
        marginBottom: 12,
        flexDirection: "row",
        alignItems: "center",
        justifyContent: "space-between",
        elevation: 2,
        shadowColor: "#000",
        shadowOffset: { width: 0, height: 1 },
        shadowOpacity: 0.1,
        shadowRadius: 3,
      }}
    >
      <View style={{ flex: 1, marginRight: 12 }}>
        <Text style={{ fontSize: 16, fontWeight: "600", marginBottom: 4 }}>
          {filter.name}
        </Text>
        {details ? (
          <Text style={{ color: "#6b7280", fontSize: 13 }}>{details}</Text>
        ) : null}
      </View>
      <Switch
        value={filter.is_active}
        onValueChange={() => onToggle(filter.id)}
      />
    </Pressable>
  );
}
