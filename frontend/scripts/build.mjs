import { cp, mkdir } from "node:fs/promises";
import "./build-architecture.mjs";

const root = new URL("../", import.meta.url);
const output = new URL("dist/", root);
await mkdir(output, { recursive: true });
await cp(new URL("public/", root), output, { recursive: true });
await cp(new URL("data/", root), output, { recursive: true });
console.log("Built frontend/dist");
