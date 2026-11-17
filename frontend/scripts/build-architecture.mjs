import { readFile, writeFile } from "node:fs/promises";
import { architectureSvg } from "../public/architecture.js";
const data = JSON.parse(await readFile(new URL("../data/raw-demo.json", import.meta.url), "utf8"));
await writeFile(new URL("../public/system-architecture.svg", import.meta.url), architectureSvg(data));
console.log("Generated architecture infographic SVG");
