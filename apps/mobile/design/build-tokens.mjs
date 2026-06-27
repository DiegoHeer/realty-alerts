import { promises as fs } from "node:fs";
import path from "node:path";
import StyleDictionary from "style-dictionary";
import { register, permutateThemes, expandTypesMap } from "@tokens-studio/sd-transforms";

const ROOT = path.dirname(new URL(import.meta.url).pathname);
const SETS = path.join(ROOT, "sets");

register(StyleDictionary);

const raw = JSON.parse(await fs.readFile(path.join(ROOT, "tokens.json"), "utf8"));
const manifest = JSON.parse(await fs.readFile(path.join(SETS, "_manifest.json"), "utf8"));

// permutateThemes -> { "<themeName>": ["Set A", "Set B", ...], ... }
const themes = permutateThemes(raw.$themes, { separator: "_" });

// expo-google-fonts family names by numeric weight (the 4 weights loaded in _layout
// and the only ones the 8 typography styles use).
const WEIGHT_TO_FAMILY = {
  "400": "PlusJakartaSans_400Regular",
  "500": "PlusJakartaSans_500Medium",
  "600": "PlusJakartaSans_600SemiBold",
  "700": "PlusJakartaSans_700Bold",
};

// "8px" -> 8, "0" -> 0, "1.5" -> 1.5 ; leaves colors (#.. / rgba(..)) and font
// names untouched (they are never pure-numeric).
function coerceNumber(value) {
  if (typeof value === "string" && /^-?\d*\.?\d+(px)?$/.test(value)) {
    return parseFloat(value);
  }
  return value;
}

// Detect a Tokens Studio typography composite value.
function isTypographyValue(v) {
  return (
    v &&
    typeof v === "object" &&
    !Array.isArray(v) &&
    "fontFamilies" in v &&
    "fontWeights" in v &&
    "fontSizes" in v &&
    "lineHeights" in v
  );
}

// Composite typography -> RN TextStyle.
function toTextStyle(v) {
  const weight = String(v.fontWeights);
  const fontFamily = WEIGHT_TO_FAMILY[weight];
  if (!fontFamily) {
    throw new Error(`Unmapped font weight "${weight}" — add it to WEIGHT_TO_FAMILY and load it in _layout.tsx`);
  }
  const fontSize = parseFloat(v.fontSizes);
  const multiplier = parseFloat(v.lineHeights);
  return { fontFamily, fontSize, lineHeight: Math.round(fontSize * multiplier) };
}

// Adapt a single resolved leaf value to its RN-ready form.
function adaptLeaf(value) {
  if (isTypographyValue(value)) return toTextStyle(value);
  return coerceNumber(value);
}

// "rgba(15, 30, 63, 0.12)" -> { shadowColor: "rgb(15, 30, 63)", shadowOpacity: 0.12 }.
// Opaque / non-rgba colors keep full opacity.
function parseShadowColor(color) {
  const m = /^rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*([\d.]+)\s*)?\)$/.exec(color);
  if (m) {
    const [, r, g, b, a] = m;
    return { shadowColor: `rgb(${r}, ${g}, ${b})`, shadowOpacity: a === undefined ? 1 : parseFloat(a) };
  }
  return { shadowColor: color, shadowOpacity: 1 };
}

// Detect an (expanded) box-shadow composite leaf.
function isShadowValue(v) {
  return (
    v &&
    typeof v === "object" &&
    !Array.isArray(v) &&
    "offsetX" in v &&
    "blur" in v &&
    "inset" in v &&
    "color" in v
  );
}

// Outer box-shadow -> RN shadow object. `spread` is dropped (RN has none) and
// inset/inner shadows return undefined so the key is omitted (RN can't render
// them; consuming one then becomes a compile error).
function toRNShadow(v) {
  if (v.inset) return undefined;
  const { shadowColor, shadowOpacity } = parseShadowColor(v.color);
  return {
    shadowColor,
    shadowOpacity,
    shadowOffset: { width: v.offsetX, height: v.offsetY },
    shadowRadius: v.blur,
    elevation: Math.round(v.blur),
  };
}

// Recursively turn an SD nested token tree into a plain {key: resolvedValue} object.
function plain(node) {
  if (node && typeof node === "object" && "value" in node) return adaptLeaf(node.value);
  if (node && typeof node === "object" && "$value" in node) return adaptLeaf(node.$value);
  const out = {};
  for (const k of Object.keys(node)) {
    if (k.startsWith("$") || k === "filePath" || k === "isSource" || k === "original" || k === "name" || k === "attributes" || k === "path") continue;
    const v = node[k];
    if (v && typeof v === "object") {
      const pv = plain(v);
      if (pv === undefined) continue; // dropped (e.g. an inset/inner shadow)
      if (typeof pv === "object" && !Array.isArray(pv) && Object.keys(pv).length === 0) continue; // prune emptied containers
      out[k] = pv;
    }
  }
  // The SD `expand` step splits composite tokens into child tokens, so a
  // typography or box-shadow composite arrives here as an assembled object.
  if (isTypographyValue(out)) return toTextStyle(out);
  if (isShadowValue(out)) return toRNShadow(out);
  return out;
}

// Build each theme, collecting its resolved nested object.
const built = {};
for (const [themeName, setNames] of Object.entries(themes)) {
  const source = setNames.map((n) => path.join(SETS, manifest[n])).filter(Boolean);
  const sd = new StyleDictionary({
    source,
    preprocessors: ["tokens-studio"],
    expand: { typesMap: expandTypesMap },
    platforms: {
      js: { transformGroup: "tokens-studio", transforms: ["name/camel"] },
    },
  });
  const platform = await sd.getPlatformTokens("js");
  built[themeName] = plain(platform.tokens);
}

console.log("Built themes:", Object.keys(built).join(", "));

// Map raw permutateThemes names (e.g. "Global_Realty AI_Light"/"..._Dark") to stable exports.
function exportNameFor(rawName) {
  if (/(^|_)Dark($|_)/i.test(rawName)) return "darkTheme";
  if (/(^|_)Light($|_)/i.test(rawName)) return "lightTheme";
  return null;
}

const remapped = {};
for (const [rawName, obj] of Object.entries(built)) {
  const exportName = exportNameFor(rawName);
  if (!exportName) {
    console.warn("Skipping theme with no light/dark mapping:", rawName);
    continue;
  }
  if (remapped[exportName]) {
    throw new Error(`Multiple themes mapped to ${exportName}; refine exportNameFor().`);
  }
  remapped[exportName] = obj;
}

if (!remapped.lightTheme || !remapped.darkTheme) {
  throw new Error(`Expected both lightTheme and darkTheme; got: ${Object.keys(remapped).join(", ")}`);
}

// Emit one TS module with stable, deterministic ordering.
const header =
  "// AUTO-GENERATED by design/build-tokens.mjs — DO NOT EDIT.\n" +
  "// Regenerate with: npm run tokens:build\n\n";
const body = ["lightTheme", "darkTheme"]
  .map((name) => `export const ${name} = ${JSON.stringify(remapped[name], null, 2)} as const;`)
  .join("\n\n");
await fs.writeFile(path.join(ROOT, "..", "src", "theme", "tokens.generated.ts"), header + body + "\n");
console.log("Wrote src/theme/tokens.generated.ts");
