// Optional authoring tool; the generated PNG is checked in, so serving needs no dependency.
// npm install --prefix tmp/architecture-render --no-save --package-lock=false @resvg/resvg-js
// node frontend/scripts/render-architecture-png.mjs
import {createRequire} from "node:module";
import {readFile,writeFile} from "node:fs/promises";
import "./build-architecture.mjs";
const require=createRequire(new URL("../../tmp/architecture-render/package.json",import.meta.url));
const {Resvg}=require("@resvg/resvg-js");
const svg=await readFile(new URL("../public/system-architecture.svg",import.meta.url),"utf8");
const png=new Resvg(svg,{fitTo:{mode:"width",value:2560},font:{loadSystemFonts:true,defaultFontFamily:"Arial"}}).render().asPng();
await writeFile(new URL("../public/system-architecture.png",import.meta.url),png);
console.log(`Rendered architecture PNG: 2560 × 4520, ${png.length} bytes`);
