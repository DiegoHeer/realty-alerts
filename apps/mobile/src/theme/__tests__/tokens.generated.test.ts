import { lightTheme, darkTheme } from "../tokens.generated";

const HEX = /^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6,8})$/;

describe("generated themes", () => {
  it("expose distinct light and dark base backgrounds", () => {
    expect(lightTheme.layerBase.background).not.toBe(darkTheme.layerBase.background);
  });

  it("contain fully resolved colour values (no unresolved refs)", () => {
    const bg = lightTheme.layerBase.background;
    expect(typeof bg).toBe("string");
    expect(bg).not.toMatch(/[{}]/);
    expect(bg).toMatch(HEX);
  });

  it("share the same structural shape across light and dark", () => {
    expect(Object.keys(lightTheme).sort()).toEqual(Object.keys(darkTheme).sort());
  });
});
