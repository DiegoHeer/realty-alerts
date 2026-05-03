import { View, Text, Pressable, Alert, ScrollView, ActivityIndicator } from "react-native";
import { useAuthStore } from "@/stores/authStore";
import { useScrapeRuns } from "@/hooks/useScrapeRuns";
import { StatusBadge } from "@/components/StatusBadge";

export default function SettingsScreen() {
  const { user, signOut } = useAuthStore();
  const { data: scrapeRuns, isLoading } = useScrapeRuns();

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

  return (
    <ScrollView style={{ flex: 1, backgroundColor: "#f9fafb" }} contentContainerStyle={{ padding: 16 }}>
      {/* Account */}
      <Text style={{ fontSize: 13, fontWeight: "600", color: "#6b7280", marginBottom: 8, textTransform: "uppercase" }}>
        Account
      </Text>
      <View style={sectionStyle}>
        <Text style={{ fontSize: 16 }}>{user?.email ?? "No email"}</Text>
      </View>

      {/* Scrape Status */}
      <Text
        style={{
          fontSize: 13,
          fontWeight: "600",
          color: "#6b7280",
          marginBottom: 8,
          marginTop: 24,
          textTransform: "uppercase",
        }}
      >
        Scraper Status
      </Text>
      <View style={sectionStyle}>
        {isLoading ? (
          <ActivityIndicator />
        ) : latestRuns.length === 0 ? (
          <Text style={{ color: "#9ca3af" }}>No scrape runs yet</Text>
        ) : (
          latestRuns.map((run) => (
            <View
              key={run.website}
              style={{
                flexDirection: "row",
                justifyContent: "space-between",
                alignItems: "center",
                paddingVertical: 8,
              }}
            >
              <Text style={{ fontSize: 15, fontWeight: "500", textTransform: "capitalize" }}>
                {run.website.replace("_", " ")}
              </Text>
              <View style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
                <Text style={{ color: "#6b7280", fontSize: 13 }}>
                  {run.new_properties_count} new
                </Text>
                <StatusBadge status={run.status} />
              </View>
            </View>
          ))
        )}
      </View>

      {/* Sign Out */}
      <Pressable
        onPress={handleSignOut}
        style={{
          backgroundColor: "#fee2e2",
          padding: 16,
          borderRadius: 12,
          alignItems: "center",
          marginTop: 32,
        }}
      >
        <Text style={{ color: "#991b1b", fontWeight: "600", fontSize: 16 }}>Sign out</Text>
      </Pressable>
    </ScrollView>
  );
}

const sectionStyle = {
  backgroundColor: "#fff",
  borderRadius: 12,
  padding: 16,
  elevation: 1,
  shadowColor: "#000",
  shadowOffset: { width: 0, height: 1 },
  shadowOpacity: 0.05,
  shadowRadius: 2,
};
