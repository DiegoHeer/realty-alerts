import { useState } from "react";
import { View, Pressable, ScrollView, Alert, ActivityIndicator } from "react-native";
import { useRouter } from "expo-router";
import { useCreateFilter } from "@/hooks/useFilters";
import { Text } from "@/components/ui/Text";
import { Input } from "@/components/ui/Input";
import { useTheme } from "@/theme/useTheme";

export default function CreateFilterScreen() {
  const router = useRouter();
  const createFilter = useCreateFilter();
  const theme = useTheme();

  const [name, setName] = useState("");
  const [city, setCity] = useState("");
  const [minPrice, setMinPrice] = useState("");
  const [maxPrice, setMaxPrice] = useState("");
  const [propertyType, setPropertyType] = useState("");
  const [minBedrooms, setMinBedrooms] = useState("");

  const handleSubmit = async () => {
    if (!name.trim()) {
      Alert.alert("Error", "Filter name is required");
      return;
    }

    try {
      await createFilter.mutateAsync({
        name: name.trim(),
        city: city.trim() || undefined,
        min_price: minPrice ? parseInt(minPrice) : undefined,
        max_price: maxPrice ? parseInt(maxPrice) : undefined,
        property_type: propertyType.trim() || undefined,
        min_bedrooms: minBedrooms ? parseInt(minBedrooms) : undefined,
      });
      router.back();
    } catch (error: any) {
      Alert.alert("Error", error.message);
    }
  };

  const labelStyle = {
    marginBottom: theme.space["050"],
    marginTop: theme.space["150"],
  };

  return (
    <ScrollView
      style={{ flex: 1, backgroundColor: theme.layerBase.background }}
      contentContainerStyle={{ padding: theme.space["200"] }}
    >
      <Text variant="label" color={theme.layerOne.text} style={labelStyle}>
        Name *
      </Text>
      <Input value={name} onChangeText={setName} placeholder="e.g. Amsterdam apartments" />

      <Text variant="label" color={theme.layerOne.text} style={labelStyle}>
        City
      </Text>
      <Input value={city} onChangeText={setCity} placeholder="e.g. Amsterdam" />

      <View style={{ flexDirection: "row", gap: theme.space["150"] }}>
        <View style={{ flex: 1 }}>
          <Text variant="label" color={theme.layerOne.text} style={labelStyle}>
            Min price
          </Text>
          <Input value={minPrice} onChangeText={setMinPrice} keyboardType="numeric" placeholder="200000" />
        </View>
        <View style={{ flex: 1 }}>
          <Text variant="label" color={theme.layerOne.text} style={labelStyle}>
            Max price
          </Text>
          <Input value={maxPrice} onChangeText={setMaxPrice} keyboardType="numeric" placeholder="500000" />
        </View>
      </View>

      <Text variant="label" color={theme.layerOne.text} style={labelStyle}>
        Property type
      </Text>
      <Input value={propertyType} onChangeText={setPropertyType} placeholder="apartment, house" />

      <Text variant="label" color={theme.layerOne.text} style={labelStyle}>
        Min bedrooms
      </Text>
      <Input value={minBedrooms} onChangeText={setMinBedrooms} keyboardType="numeric" placeholder="2" />

      <Pressable
        onPress={handleSubmit}
        disabled={createFilter.isPending}
        style={{
          backgroundColor: theme.buttonPrimary.background.default,
          padding: theme.space["200"],
          borderRadius: theme.radius.full,
          alignItems: "center",
          marginTop: theme.space["200"],
        }}
      >
        {createFilter.isPending ? (
          <ActivityIndicator color={theme.buttonPrimary.text.default} />
        ) : (
          <Text variant="label" color={theme.buttonPrimary.text.default}>
            Create filter
          </Text>
        )}
      </Pressable>
    </ScrollView>
  );
}
