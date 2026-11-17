import { createServer } from "node:http";
import { createReadStream } from "node:fs";
import { stat } from "node:fs/promises";
import { extname } from "node:path";
import { fileURLToPath } from "node:url";

const root = new URL("../", import.meta.url);
const files = new Map([
  ["/", new URL("public/index.html", root)],
  ["/app.js", new URL("public/app.js", root)],
  ["/parts.js", new URL("public/parts.js", root)],
  ["/raw-demo.js", new URL("public/raw-demo.js", root)],
  ["/assignment.js", new URL("public/assignment.js", root)],
  ["/architecture.js", new URL("public/architecture.js", root)],
  ["/system-architecture.svg", new URL("public/system-architecture.svg", root)],
  ["/firmable-writeup.pdf", new URL("data/firmable-writeup.pdf", root)],
  ["/firmable-writeup.tex", new URL("data/firmable-writeup.tex", root)],
  ["/assignment-writeup.json", new URL("data/assignment-writeup.json", root)],
  ["/part-five.md", new URL("data/part-five.md", root)],
  ["/firmable-writeup.md", new URL("data/firmable-writeup.md", root)],
  ["/replay-charts.js", new URL("public/replay-charts.js", root)],
  ["/style.css", new URL("public/style.css", root)],
  ["/inter.woff2", new URL("public/inter.woff2", root)],
  ["/favicon.png", new URL("public/favicon.png", root)],
  ["/part-one.json", new URL("data/part-one.json", root)],
  ...["mapping.json", "identity.json", "profiles.json", "write-up.json", "discovery-audit.csv", "link-audit.csv",
    "raw-demo.json", "raw-mapping.json", "raw-identity.json", "raw-profiles.json", "raw-link-audit.csv"]
    .map(file => [`/${file}`, new URL(`data/${file}`, root)]),
]);
const types = {
  ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8", ".json": "application/json; charset=utf-8", ".woff2": "font/woff2",
  ".csv": "text/csv; charset=utf-8",
  ".md": "text/plain; charset=utf-8",
  ".png": "image/png",
  ".svg": "image/svg+xml",
  ".pdf": "application/pdf",
  ".tex": "text/plain; charset=utf-8",
};
const port = Number(process.env.PORT || 4173);

const server = createServer(async (req, res) => {
  if (req.method !== "GET" && req.method !== "HEAD") {
    res.writeHead(405, { Allow: "GET, HEAD" }).end();
    return;
  }
  const file = files.get(new URL(req.url, "http://localhost").pathname);
  if (!file) {
    res.writeHead(404).end("Page not found");
    return;
  }
  const path = fileURLToPath(file);
  try {
    const info = await stat(path);
    res.writeHead(200, { "Content-Type": types[extname(path)], "Content-Length": info.size, "Cache-Control": "no-cache" });
    if (req.method === "HEAD") res.end();
    else createReadStream(path).on("error", () => res.destroy()).pipe(res);
  } catch (error) {
    res.writeHead(error.code === "ENOENT" ? 404 : 500).end("File unavailable");
  }
});

server.listen(port, "127.0.0.1", () => console.log(`Firmable review at http://127.0.0.1:${port}`));
