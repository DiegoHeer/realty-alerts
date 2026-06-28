import { FlatList, View, Pressable, RefreshControl, ActivityIndicator } from "react-native";
import { useRouter } from "expo-router";
import { useFilters, useToggleFilter } from "@/hooks/useFilters";
import { FilterCard } from "@/components/FilterCard";
import { Text } from "@/components/ui/Text";
import { useTheme } from "@/theme/useTheme";

export default function FiltersScreen() {
  const { data: filters, isLoading, refetch, isRefetching } = useFilters();
  const toggleMutation = useToggleFilter();
  const router = useRouter();
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
    <View style={{ flex: 1, backgroundColor: theme.layerBase.background }}>
      <FlatList
        data={filters}
        keyExtractor={(item) => String(item.id)}
        renderItem={({ item }) => (
          <FilterCard
            filter={item}
            onToggle={(id) => toggleMutation.mutate(id)}
            onPress={(id) => router.push(`/filter/${id}`)}
          />
        )}
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
            <Text color={theme.text.secondary}>No filters yet.</Text>
            <Text variant="body-small" color={theme.text.tertiary} style={{ marginTop: theme.space["050"] }}>
              Create a filter to get notified about new listings.
            </Text>
          </View>
        }
      />

      <Pressable
        onPress={() => router.push("/filter/create")}
        style={{
          position: "absolute",
          bottom: theme.space["300"],
          right: theme.space["300"],
          backgroundColor: theme.buttonPrimary.background.default,
          width: 56,
          height: 56,
          borderRadius: theme.radius.full,
          alignItems: "center",
          justifyContent: "center",
          ...theme.shadow.outer.soft.md,
        }}
      >
        <Text color={theme.buttonPrimary.text.default} style={{ fontSize: 28, lineHeight: 30 }}>
          +
        </Text>
      </Pressable>
    </View>
  );
}
