import { lightTheme, darkTheme } from "../tokens.generated";

describe("RN-ready theme", () => {
  it("exposes spacing/radius/font-size as numbers, not px-strings", () => {
    expect(typeof lightTheme.space["100"]).toBe("number");
    expect(lightTheme.space["100"]).toBe(8);
    expect(typeof lightTheme.radius["100"]).toBe("number");
    expect(lightTheme.radius["100"]).toBe(8);
    expect(typeof lightTheme["font-size"].md).toBe("number");
    expect(lightTheme["font-size"].md).toBe(16);
    // bare numeric strings (no px) coerce too, e.g. radius.none "0" -> 0
    expect(typeof lightTheme.radius.none).toBe("number");
    expect(lightTheme.radius.none).toBe(0);
  });

  it("exposes typography as RN TextStyle objects", () => {
    expect(lightTheme.type.body).toEqual({
      fontFamily: "PlusJakartaSans_400Regular",
      fontSize: 16,
      lineHeight: 24,
    });
    expect(lightTheme.type.display.fontFamily).toBe("PlusJakartaSans_700Bold");
    expect(lightTheme.type["heading-one"].fontFamily).toBe("PlusJakartaSans_600SemiBold");
    expect(lightTheme.type.label.fontFamily).toBe("PlusJakartaSans_500Medium");
  });

  it("has no leftover px-string dimension values anywhere", () => {
    const json = JSON.stringify(lightTheme) + JSON.stringify(darkTheme);
    expect(json).not.toMatch(/"\d+(\.\d+)?px"/);
  });
});
