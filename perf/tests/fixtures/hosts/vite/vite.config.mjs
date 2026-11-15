// No local install: the production wrapper resolves Vite from harness/ui.
export default {
  root: '/this-root-must-be-overridden',
  cacheDir: '/this-cache-must-be-overridden',
  build: { outDir: '/this-output-must-be-overridden' },
  plugins: [{ name: 'b1-preserved-plugin', transformIndexHtml(html) {
    return html.replace('</title>', ' production-config-preserved</title>');
  } }],
};
