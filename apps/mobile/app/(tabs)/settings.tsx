import { View, Pressable, Alert, ScrollView, ActivityIndicator } from "react-native";
import { useAuthStore } from "@/stores/authStore";
import { useScrapeRuns } from "@/hooks/useScrapeRuns";
import { StatusBadge } from "@/components/StatusBadge";
import { useThemeMode } from "@/theme/useThemeMode";
import { useTheme } from "@/theme/useTheme";
import { Text } from "@/components/ui/Text";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import type { ThemeMode } from "@/theme/types";

const MODES: { label: string; value: ThemeMode }[] = [
  { label: "System", value: "system" },
  { label: "Light", value: "light" },
  { label: "Dark", value: "dark" },
];

export function ThemeModeSelector() {
  const { mode, setMode } = useThemeMode();
  const theme = useTheme();
  return (
    <View style={{ flexDirection: "row", gap: theme.space["100"] }}>
      {MODES.map(({ label, value }) => (
        <Pressable
          key={value}
          onPress={() => setMode(value)}
          style={{
            paddingHorizontal: theme.space["150"],
            paddingVertical: theme.space["100"],
            borderRadius: theme.radius["100"],
            backgroundColor: mode === value ? theme.layerTwo.background : "transparent",
            borderWidth: 1,
            borderColor: theme.layerBase.border,
          }}
        >
          <Text variant="label">{label}</Text>
        </Pressable>
      ))}
    </View>
  );
}

export default function SettingsScreen() {
  const { user, signOut } = useAuthStore();
  const { data: scrapeRuns, isLoading } = useScrapeRuns();
  const theme = useTheme();

  const handleSignOut = () => {
    Alert.alert("Sign out", "Are you sure?", [
      { text: "Cancel", style: "cancel" },
      { text: "Sign out", style: "destructive", onPress: signOut },
    ]);
  };

  // Get latest run per website
  const latestRuns = scrapeRuns
    ? Object.values(
        scrapeRuns.reduce(
          (acc, run) => {
            if (!acc[run.website] || run.started_at > acc[run.website].started_at) {
              acc[run.website] = run;
            }
            return acc;
          },
          {} as Record<string, (typeof scrapeRuns)[0]>,
        ),
      )
    : [];

  const sectionLabelStyle = {
    marginBottom: theme.space["100"],
    marginTop: theme.space["300"],
    textTransform: "uppercase" as const,
  };

  return (
    <ScrollView
      style={{ flex: 1, backgroundColor: theme.layerBase.background }}
      contentContainerStyle={{ padding: theme.space["200"] }}
    >
      {/* Account */}
      <Text variant="label" color={theme.text.secondary} style={{ marginBottom: theme.space["100"], textTransform: "uppercase" }}>
        Account
      </Text>
      <Card>
        <Text variant="body">{user?.email ?? "No email"}</Text>
      </Card>

      {/* Scrape Status */}
      <Text variant="label" color={theme.text.secondary} style={sectionLabelStyle}>
        Scraper Status
      </Text>
      <Card>
        {isLoading ? (
          <ActivityIndicator color={theme.link.default} />
        ) : latestRuns.length === 0 ? (
          <Text color={theme.text.tertiary}>No scrape runs yet</Text>
        ) : (
          latestRuns.map((run) => (
            <View
              key={run.website}
              style={{
                flexDirection: "row",
                justifyContent: "space-between",
                alignItems: "center",
                paddingVertical: theme.space["100"],
              }}
            >
              <Text variant="label" style={{ textTransform: "capitalize" }}>
                {run.website.replace("_", " ")}
              </Text>
              <View style={{ flexDirection: "row", alignItems: "center", gap: theme.space["100"] }}>
                <Text variant="body-small" color={theme.text.secondary}>
                  {run.new_listings_count} new
                </Text>
                <StatusBadge status={run.status} />
              </View>
            </View>
          ))
        )}
      </Card>

      {/* Appearance */}
      <Text variant="label" color={theme.text.secondary} style={sectionLabelStyle}>
        Appearance
      </Text>
      <Card>
        <ThemeModeSelector />
      </Card>

      {/* Sign Out */}
      <Button variant="destructive" onPress={handleSignOut} style={{ marginTop: theme.space["400"] }}>
        Sign out
      </Button>
    </ScrollView>
  );
}
