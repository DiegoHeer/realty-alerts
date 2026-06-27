import { StyleSheet, Text as RNText } from "react-native";
import { renderWithTheme } from "@/test/renderWithTheme";
import { useThemedStyles } from "../useThemedStyles";
import { lightTheme } from "../tokens.generated";

function Probe() {
  const styles = useThemedStyles((t) => ({
    box: { color: t.layerBase.text, padding: t.space["100"] },
  }));
  return (
    <RNText testID="p" style={styles.box}>
      x
    </RNText>
  );
}

describe("useThemedStyles", () => {
  it("builds StyleSheet styles from the active theme", async () => {
    const { getByTestId } = await renderWithTheme(<Probe />);
    const flat = StyleSheet.flatten(getByTestId("p").props.style);
    expect(flat.color).toBe(lightTheme.layerBase.text);
    expect(flat.padding).toBe(lightTheme.space["100"]);
  });
});
