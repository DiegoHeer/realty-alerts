import { useState } from "react";
import { View, Alert, ActivityIndicator, Pressable } from "react-native";
import { Link } from "expo-router";
import { Text } from "@/components/ui/Text";
import { Input } from "@/components/ui/Input";
import { useTheme } from "@/theme/useTheme";
import { useAuthStore } from "@/stores/authStore";

export default function RegisterScreen() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const signUp = useAuthStore((s) => s.signUp);
  const theme = useTheme();

  const handleRegister = async () => {
    if (!email || !password) return;
    setLoading(true);
    try {
      await signUp(email, password);
      Alert.alert("Success", "Check your email for a confirmation link.");
    } catch (error: any) {
      Alert.alert("Registration failed", error.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <View style={{ flex: 1, justifyContent: "center", padding: theme.space["300"], backgroundColor: theme.layerBase.background }}>
      <Text variant="heading-one" style={{ marginBottom: theme.space["400"], textAlign: "center" }}>
        Create Account
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
        onPress={handleRegister}
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
          <Text variant="label" color={theme.buttonPrimary.text.default}>Register</Text>
        )}
      </Pressable>

      <Link href="/(auth)/login" asChild>
        <Pressable style={{ marginTop: theme.space["200"], alignItems: "center" }}>
          <Text color={theme.link.default}>Already have an account? Sign in</Text>
        </Pressable>
      </Link>
    </View>
  );
}
