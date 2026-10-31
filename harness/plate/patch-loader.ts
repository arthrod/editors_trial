/**
 * Bun loader plugin: surface the error that Plate's package reader swallows.
 *
 * internal/docxPackage.ts wraps every non-DocxPackageError into
 * "DOCX package structure is invalid.", which hides the real cause. This
 * plugin rewrites the throw IN MEMORY ONLY - the repository is untouched.
 */
import { plugin } from 'bun';

plugin({
  name: 'patch-docx-package-error',
  setup(build) {
    build.onLoad(
      { filter: /docx[\\/]internal[\\/]docxPackage\.ts$/ },
      async (args) => {
        const src = await Bun.file(args.path).text();
        const patched = src.replace(
          "throw invalidPackage('DOCX package structure is invalid.');",
          "console.error('=== RAW PLATE PACKAGE ERROR ===');\n" +
            "    console.error('name:', error && error.constructor && error.constructor.name);\n" +
            "    console.error('message:', error && error.message);\n" +
            "    console.error('stack:', error && error.stack);\n" +
            "    throw error;"
        );
        return { contents: patched, loader: 'ts' };
      }
    );
  },
});
