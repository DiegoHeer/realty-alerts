import { useState } from "react";
import { View, Text, TextInput, Pressable, ScrollView, Alert, ActivityIndicator } from "react-native";
import { useRouter } from "expo-router";
import { useCreateFilter } from "@/hooks/useFilters";

export default function CreateFilterScreen() {
  const router = useRouter();
  const createFilter = useCreateFilter();

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

  return (
    <ScrollView
      style={{ flex: 1, backgroundColor: "#f9fafb" }}
      contentContainerStyle={{ padding: 16 }}
    >
      <Text style={labelStyle}>Name *</Text>
      <TextInput style={inputStyle} value={name} onChangeText={setName} placeholder="e.g. Amsterdam apartments" />

      <Text style={labelStyle}>City</Text>
      <TextInput style={inputStyle} value={city} onChangeText={setCity} placeholder="e.g. Amsterdam" />

      <View style={{ flexDirection: "row", gap: 12 }}>
        <View style={{ flex: 1 }}>
          <Text style={labelStyle}>Min price</Text>
          <TextInput
            style={inputStyle}
            value={minPrice}
            onChangeText={setMinPrice}
            keyboardType="numeric"
            placeholder="200000"
          />
        </View>
        <View style={{ flex: 1 }}>
          <Text style={labelStyle}>Max price</Text>
          <TextInput
            style={inputStyle}
            value={maxPrice}
            onChangeText={setMaxPrice}
            keyboardType="numeric"
            placeholder="500000"
          />
        </View>
      </View>

      <Text style={labelStyle}>Property type</Text>
      <TextInput style={inputStyle} value={propertyType} onChangeText={setPropertyType} placeholder="apartment, house" />

      <Text style={labelStyle}>Min bedrooms</Text>
      <TextInput
        style={inputStyle}
        value={minBedrooms}
        onChangeText={setMinBedrooms}
        keyboardType="numeric"
        placeholder="2"
      />

      <Pressable
        onPress={handleSubmit}
        disabled={createFilter.isPending}
        style={{
          backgroundColor: "#2563eb",
          padding: 16,
          borderRadius: 8,
          alignItems: "center",
          marginTop: 16,
        }}
      >
        {createFilter.isPending ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <Text style={{ color: "#fff", fontWeight: "600", fontSize: 16 }}>Create filter</Text>
        )}
      </Pressable>
    </ScrollView>
  );
}

const labelStyle = {
  fontSize: 14,
  fontWeight: "600" as const,
  color: "#374151",
  marginBottom: 4,
  marginTop: 12,
};

const inputStyle = {
  backgroundColor: "#fff",
  borderWidth: 1,
  borderColor: "#d1d5db",
  borderRadius: 8,
  padding: 14,
  fontSize: 16,
};
