import { Tabs } from "expo-router";
import { useTheme } from "@/theme/useTheme";

export default function TabLayout() {
  const theme = useTheme();
  return (
    <Tabs
      screenOptions={{
        tabBarActiveTintColor: theme.link.default,
        headerStyle: { backgroundColor: theme.layerBase.background },
      }}
    >
      <Tabs.Screen
        name="index"
        options={{ title: "Home", tabBarLabel: "Home" }}
      />
      <Tabs.Screen
        name="filters"
        options={{ title: "Filters", tabBarLabel: "Filters" }}
      />
      <Tabs.Screen
        name="settings"
        options={{ title: "Settings", tabBarLabel: "Settings" }}
      />
    </Tabs>
  );
}
