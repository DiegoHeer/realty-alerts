import { lightTheme, darkTheme } from "../tokens.generated";

describe("text-emphasis tokens", () => {
  it("exposes secondary/tertiary text tokens on both themes", () => {
    expect(lightTheme.text.secondary).toBe("#8a857e"); // {neutral.500}
    expect(lightTheme.text.tertiary).toBe("#a9a49c"); // {neutral.400}
    expect(darkTheme.text.secondary).toBe("#617d9e"); // {primary.400}
    expect(darkTheme.text.tertiary).toBe("#3d5c82"); // {primary.500}
  });

  it("adds a real, lower-emphasis hierarchy (not duplicates of primary text)", () => {
    expect(lightTheme.text.secondary).not.toBe(lightTheme.layerBase.text);
    expect(darkTheme.text.secondary).not.toBe(darkTheme.layerBase.text);
  });

  it("is theme-reactive (light differs from dark)", () => {
    expect(lightTheme.text.secondary).not.toBe(darkTheme.text.secondary);
    expect(lightTheme.text.tertiary).not.toBe(darkTheme.text.tertiary);
  });
});
