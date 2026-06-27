import { lightTheme, darkTheme } from "../tokens.generated";

describe("RN shadow tokens", () => {
  it("transforms outer soft shadows into RN shadow objects", () => {
    expect(lightTheme.shadow.outer.soft.sm).toEqual({
      shadowColor: "rgb(15, 30, 63)",
      shadowOpacity: 0.12,
      shadowOffset: { width: 0, height: 2 },
      shadowRadius: 4,
      elevation: 4,
    });
  });

  it("derives elevation from blur and drops spread/inset/offsetX", () => {
    const md = lightTheme.shadow.outer.soft.md;
    expect(md.elevation).toBe(8);
    expect(md.shadowRadius).toBe(8);
    expect(md).not.toHaveProperty("spread");
    expect(md).not.toHaveProperty("inset");
    expect(md).not.toHaveProperty("offsetX");
  });

  it("omits inner/inset shadows entirely (fail-loud at compile time)", () => {
    expect((lightTheme.shadow as Record<string, unknown>).inner).toBeUndefined();
    expect((darkTheme.shadow as Record<string, unknown>).inner).toBeUndefined();
  });

  it("leaves no raw web shadow keys anywhere in the theme", () => {
    const json = JSON.stringify(lightTheme) + JSON.stringify(darkTheme);
    expect(json).not.toMatch(/"offsetX"|"inset"|"spread"/);
  });
});
