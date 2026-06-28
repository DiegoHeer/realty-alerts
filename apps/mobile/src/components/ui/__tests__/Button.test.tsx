import { StyleSheet } from "react-native";
import { fireEvent } from "@testing-library/react-native";
import { renderWithTheme } from "@/test/renderWithTheme";
import { Button } from "../Button";
import { lightTheme } from "@/theme/tokens.generated";

describe("Button", () => {
  it("renders the label with primary default colours", async () => {
    const { getByText, getByTestId } = await renderWithTheme(
      <Button testID="btn" onPress={() => {}}>
        Save
      </Button>,
    );
    expect(getByText("Save")).toBeTruthy();
    const root = StyleSheet.flatten(getByTestId("btn").props.style);
    expect(root.backgroundColor).toBe(lightTheme.buttonPrimary.background.default);
    expect(root.borderRadius).toBe(lightTheme.radius.full);
    const label = StyleSheet.flatten(getByText("Save").props.style);
    expect(label.color).toBe(lightTheme.buttonPrimary.text.default);
  });

  it("uses secondary palette for the secondary variant", async () => {
    const { getByText } = await renderWithTheme(
      <Button variant="secondary" onPress={() => {}}>
        Go
      </Button>,
    );
    const label = StyleSheet.flatten(getByText("Go").props.style);
    expect(label.color).toBe(lightTheme.buttonSecondary.text.default);
  });

  it("applies disabled colours and does not fire onPress when disabled", async () => {
    const onPress = jest.fn();
    const { getByText, getByTestId } = await renderWithTheme(
      <Button testID="btn" disabled onPress={onPress}>
        Save
      </Button>,
    );
    const root = StyleSheet.flatten(getByTestId("btn").props.style);
    expect(root.backgroundColor).toBe(lightTheme.buttonPrimary.background.disabled);
    const label = StyleSheet.flatten(getByText("Save").props.style);
    expect(label.color).toBe(lightTheme.buttonPrimary.text.disabled);
    fireEvent.press(getByTestId("btn"));
    expect(onPress).not.toHaveBeenCalled();
  });

  it("renders the destructive variant with feedback.error colours", async () => {
    const { getByText, getByTestId } = await renderWithTheme(
      <Button testID="btn" variant="destructive" onPress={() => {}}>
        Delete
      </Button>,
    );
    const root = StyleSheet.flatten(getByTestId("btn").props.style);
    expect(root.backgroundColor).toBe(lightTheme.feedback.error.background);
    const label = StyleSheet.flatten(getByText("Delete").props.style);
    expect(label.color).toBe(lightTheme.feedback.error.text);
  });

  it("blocks onPress when a destructive button is disabled", async () => {
    const onPress = jest.fn();
    const { getByTestId } = await renderWithTheme(
      <Button testID="btn" variant="destructive" disabled onPress={onPress}>
        Delete
      </Button>,
    );
    fireEvent.press(getByTestId("btn"));
    expect(onPress).not.toHaveBeenCalled();
  });
});
