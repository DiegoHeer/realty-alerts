import { View, Text } from "react-native";

interface Props {
  status: "running" | "success" | "failed";
}

const COLORS = {
  running: { bg: "#fef3c7", text: "#92400e" },
  success: { bg: "#d1fae5", text: "#065f46" },
  failed: { bg: "#fee2e2", text: "#991b1b" },
};

export function StatusBadge({ status }: Props) {
  const color = COLORS[status];
  return (
    <View
      style={{
        backgroundColor: color.bg,
        paddingHorizontal: 8,
        paddingVertical: 4,
        borderRadius: 12,
      }}
    >
      <Text style={{ color: color.text, fontSize: 12, fontWeight: "600" }}>
        {status}
      </Text>
    </View>
  );
}
