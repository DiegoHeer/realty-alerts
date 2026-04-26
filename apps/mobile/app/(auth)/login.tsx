import { useState } from "react";
import { View, Text, TextInput, Pressable, Alert, ActivityIndicator } from "react-native";
import { Link } from "expo-router";
import { useAuthStore } from "@/stores/authStore";

export default function LoginScreen() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const signIn = useAuthStore((s) => s.signIn);

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
    <View style={{ flex: 1, justifyContent: "center", padding: 24, backgroundColor: "#f9fafb" }}>
      <Text style={{ fontSize: 28, fontWeight: "700", marginBottom: 32, textAlign: "center" }}>
        Realty Alerts
      </Text>

      <TextInput
        placeholder="Email"
        value={email}
        onChangeText={setEmail}
        keyboardType="email-address"
        autoCapitalize="none"
        style={inputStyle}
      />

      <TextInput
        placeholder="Password"
        value={password}
        onChangeText={setPassword}
        secureTextEntry
        style={inputStyle}
      />

      <Pressable
        onPress={handleLogin}
        disabled={loading}
        style={{
          backgroundColor: "#2563eb",
          padding: 16,
          borderRadius: 8,
          alignItems: "center",
          marginTop: 8,
        }}
      >
        {loading ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <Text style={{ color: "#fff", fontWeight: "600", fontSize: 16 }}>Sign in</Text>
        )}
      </Pressable>

      <Link href="/(auth)/register" asChild>
        <Pressable style={{ marginTop: 16, alignItems: "center" }}>
          <Text style={{ color: "#2563eb" }}>Don&apos;t have an account? Register</Text>
        </Pressable>
      </Link>
    </View>
  );
}

const inputStyle = {
  backgroundColor: "#fff",
  borderWidth: 1,
  borderColor: "#d1d5db",
  borderRadius: 8,
  padding: 14,
  marginBottom: 12,
  fontSize: 16,
};
