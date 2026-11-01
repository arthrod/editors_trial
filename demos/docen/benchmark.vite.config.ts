import { fileURLToPath, URL } from "node:url";

import { defineConfig } from "vite";

const editorRoot = fileURLToPath(new URL(".", import.meta.url));

export default defineConfig({
  root: fileURLToPath(new URL("./benchmark", import.meta.url)),
  base: "./",
  resolve: {
    alias: {
      "@docen/core/geometry": fileURLToPath(new URL("../core/src/geometry/index.ts", import.meta.url)),
      "@docen/core/paint": fileURLToPath(new URL("../core/src/paint/index.ts", import.meta.url)),
      "@docen/core": fileURLToPath(new URL("../core/src/index.ts", import.meta.url)),
      "@docen/layout": fileURLToPath(new URL("../layout/src/index.ts", import.meta.url)),
      "@docen/pptx": fileURLToPath(new URL("../pptx/src/index.ts", import.meta.url)),
      "@docen/editor": fileURLToPath(new URL("./src/index.ts", import.meta.url)),
    },
  },
  build: {
    outDir: fileURLToPath(new URL("../../../dist", import.meta.url)),
    emptyOutDir: true,
    target: "es2022",
    minify: "esbuild",
    sourcemap: false,
    chunkSizeWarningLimit: 10_000,
    rollupOptions: {
      input: fileURLToPath(new URL("./benchmark/index.html", import.meta.url)),
    },
  },
  server: {
    open: false,
  },
  // Keep the config's editor root available for path-based tooling.
  define: {
    __DOCEN_EDITOR_ROOT__: JSON.stringify(editorRoot),
  },
});
