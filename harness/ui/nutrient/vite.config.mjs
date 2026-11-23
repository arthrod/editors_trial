import { defineConfig } from 'vite';

// Serves the host page on 5226 for Report E2's browser lanes. The viewer itself
// is not bundled: main.js loads the pinned version from Nutrient's own CDN, as
// the sister site does (installing the npm package would mean accepting its
// evaluation agreement, which nobody has done).
export default defineConfig({
  server: { port: 5226, strictPort: true, host: '127.0.0.1' },
});
