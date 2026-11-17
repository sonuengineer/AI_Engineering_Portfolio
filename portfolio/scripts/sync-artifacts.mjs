// Copies REAL artifacts from the three project folders into the site:
//  - screenshots:   <project>/docs/screenshots/*.png         -> public/screenshots/<project>/
//  - benchmarks:    <project>/docs/benchmarks/*.json          -> src/data/generated/artifacts.json
//  - interview:     <project>/interview-preparation/questions.json -> src/data/generated/interview.json
// Nothing is invented: if an artifact does not exist, the site shows that it is missing.
import { copyFileSync, existsSync, mkdirSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const site = join(here, "..");
const root = join(site, "..");
const PROJECTS = ["nexus-ai", "datawise-ai", "evalops-ai"];
const gen = join(site, "src", "data", "generated");
mkdirSync(gen, { recursive: true });

const artifacts = {};
const screenshots = {};
const interview = {};
for (const p of PROJECTS) {
  const shotDir = join(root, p, "docs", "screenshots");
  screenshots[p] = [];
  if (existsSync(shotDir)) {
    const out = join(site, "public", "screenshots", p);
    mkdirSync(out, { recursive: true });
    for (const f of readdirSync(shotDir).filter((f) => /\.(png|jpe?g|webp)$/i.test(f)).sort()) {
      copyFileSync(join(shotDir, f), join(out, f));
      screenshots[p].push(`/screenshots/${p}/${f}`);
    }
  }
  const benchDir = join(root, p, "docs", "benchmarks");
  artifacts[p] = {};
  if (existsSync(benchDir)) {
    for (const f of readdirSync(benchDir).filter((f) => f.endsWith(".json")).sort()) {
      try { artifacts[p][f] = JSON.parse(readFileSync(join(benchDir, f), "utf8")); }
      catch (e) { console.warn(`skip invalid JSON ${p}/${f}: ${e.message}`); }
    }
  }
  const q = join(root, p, "interview-preparation", "questions.json");
  interview[p] = existsSync(q) ? JSON.parse(readFileSync(q, "utf8")) : null;
}
const cross = join(root, "interview-preparation", "cross-project.json");
interview["cross-project"] = existsSync(cross) ? JSON.parse(readFileSync(cross, "utf8")) : null;

writeFileSync(join(gen, "artifacts.json"), JSON.stringify({ artifacts, screenshots }, null, 2));
writeFileSync(join(gen, "interview.json"), JSON.stringify(interview));
const counts = Object.fromEntries(Object.entries(interview).map(([k, v]) => [k, v?.questions?.length ?? 0]));
console.log("synced", { screenshots: Object.fromEntries(Object.entries(screenshots).map(([k, v]) => [k, v.length])), interview: counts });
