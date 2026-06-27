import { promises as fs } from "node:fs";
import path from "node:path";

const ROOT = path.dirname(new URL(import.meta.url).pathname);
const raw = JSON.parse(await fs.readFile(path.join(ROOT, "tokens.json"), "utf8"));

// Top-level keys that are token SETS (everything except Tokens Studio metadata).
const META = new Set(["$themes", "$metadata"]);
const setNames = Object.keys(raw).filter((k) => !META.has(k));

// Map each set name to a filesystem-safe filename (set names contain "/" and spaces).
const fileFor = (name) => name.replace(/[^a-zA-Z0-9]+/g, "_") + ".json";

await fs.mkdir(path.join(ROOT, "sets"), { recursive: true });
const manifest = {};
for (const name of setNames) {
  const file = fileFor(name);
  manifest[name] = file;
  await fs.writeFile(
    path.join(ROOT, "sets", file),
    JSON.stringify(raw[name], null, 2) + "\n",
  );
}
// manifest maps the canonical set name -> file, used by the build to resolve permutateThemes output.
await fs.writeFile(
  path.join(ROOT, "sets", "_manifest.json"),
  JSON.stringify(manifest, null, 2) + "\n",
);
console.log("Wrote", setNames.length, "set files:", setNames.join(", "));
