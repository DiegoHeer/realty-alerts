import { useState } from "react";
import { View, Alert, ActivityIndicator, Pressable } from "react-native";
import { Link } from "expo-router";
import { Text } from "@/components/ui/Text";
import { Input } from "@/components/ui/Input";
import { useTheme } from "@/theme/useTheme";
import { useAuthStore } from "@/stores/authStore";

export default function LoginScreen() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const signIn = useAuthStore((s) => s.signIn);
  const theme = useTheme();

  const handleLogin = async () => {
    if (!email || !password) return;
    setLoading(true);
    try {
      await signIn(email, password);
    } catch (error: any) {
      Alert.alert("Login failed", error.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <View style={{ flex: 1, justifyContent: "center", padding: theme.space["300"], backgroundColor: theme.layerBase.background }}>
      <Text variant="heading-one" style={{ marginBottom: theme.space["400"], textAlign: "center" }}>
        Realty Alerts
      </Text>

      <Input
        placeholder="Email"
        value={email}
        onChangeText={setEmail}
        keyboardType="email-address"
        autoCapitalize="none"
        style={{ marginBottom: theme.space["150"] }}
      />
      <Input
        placeholder="Password"
        value={password}
        onChangeText={setPassword}
        secureTextEntry
        style={{ marginBottom: theme.space["150"] }}
      />

      <Pressable
        onPress={handleLogin}
        disabled={loading}
        style={{
          backgroundColor: theme.buttonPrimary.background.default,
          padding: theme.space["200"],
          borderRadius: theme.radius.full,
          alignItems: "center",
          marginTop: theme.space["100"],
        }}
      >
        {loading ? (
          <ActivityIndicator color={theme.buttonPrimary.text.default} />
        ) : (
          <Text variant="label" color={theme.buttonPrimary.text.default}>Sign in</Text>
        )}
      </Pressable>

      <Link href="/(auth)/register" asChild>
        <Pressable style={{ marginTop: theme.space["200"], alignItems: "center" }}>
          <Text color={theme.link.default}>Don&apos;t have an account? Register</Text>
        </Pressable>
      </Link>
    </View>
  );
}
