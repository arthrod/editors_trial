// Load the original config with Vite's in-memory runner: no timestamped
// bundled config or node_modules/.vite-temp write in the read-only host.
import path from 'node:path';
import { pathToFileURL } from 'node:url';

export default async function wrapper(environment) {
  const { loadConfigFromFile } = await import(pathToFileURL(process.env.B1_VITE_MODULE).href);
  const root = process.env.B1_HOST_ROOT;
  const output = process.env.B1_BUILD_ROOT;
  const loaded = await loadConfigFromFile(environment, process.env.B1_HOST_CONFIG, root, undefined, undefined, 'runner');
  if (!loaded) throw new Error('Host config did not load');
  const config = loaded.config;
  const build = { ...config.build, outDir: path.join(output, 'dist'), emptyOutDir: true };
  if (process.env.B1_HOST_ID === 'apryse') {
    build.rollupOptions = { ...build.rollupOptions, input: path.join(root, 'perf.html') };
  }
  return { ...config, root, cacheDir: path.join(output, 'cache'), build };
}
