import { FlatList, View, RefreshControl, ActivityIndicator } from "react-native";
import { useResidences } from "@/hooks/useResidences";
import { ResidenceCard } from "@/components/ResidenceCard";
import { Text } from "@/components/ui/Text";
import { useTheme } from "@/theme/useTheme";

export default function HomeScreen() {
  const { data: residences, isLoading, refetch, isRefetching } = useResidences();
  const theme = useTheme();

  if (isLoading) {
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
    <FlatList
      style={{ backgroundColor: theme.layerBase.background }}
      data={residences}
      keyExtractor={(item) => String(item.id)}
      renderItem={({ item }) => <ResidenceCard residence={item} />}
      contentContainerStyle={{ padding: theme.space["200"] }}
      refreshControl={
        <RefreshControl
          refreshing={isRefetching}
          onRefresh={refetch}
          tintColor={theme.link.default}
          colors={[theme.link.default]}
        />
      }
      ListEmptyComponent={
        <View style={{ alignItems: "center", paddingTop: 60 }}>
          <Text color={theme.text.secondary}>No listings yet.</Text>
          <Text variant="body-small" color={theme.text.tertiary} style={{ marginTop: theme.space["050"] }}>
            Listings will appear once the scraper runs.
          </Text>
        </View>
      }
    />
  );
}
