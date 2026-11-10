/**
 * Bundles the host app together with the repo's own build of
 * @office-open/docx. Nothing under repos/ is written to: the build reads
 * packages/docx/dist/index.mjs, which was produced by `vp pack` in the repo.
 */
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import path from "node:path";

const here = path.dirname(fileURLToPath(import.meta.url));
const REPO = "/Users/arthrod/temp/T/editors_trial/repos/office-open";

// esbuild lives in the repo's node_modules (read-only use).
const require = createRequire(path.join(REPO, "package.json"));
const { build } = require("esbuild");

await build({
  entryPoints: [path.join(here, "app.js")],
  bundle: true,
  format: "esm",
  platform: "browser",
  target: "es2022",
  outfile: path.join(here, "bundle.js"),
  alias: {
    "@office-open/docx": path.join(REPO, "packages/docx/dist/index.mjs"),
    // The library probes node:zlib and falls back to JS when it is missing;
    // the stub keeps Chromium from logging a failed `node:` module load on
    // every page load. See node-zlib-stub.js.
    "node:zlib": path.join(here, "node-zlib-stub.js"),
  },
  logLevel: "info",
});
console.log("bundle written:", path.join(here, "bundle.js"));
