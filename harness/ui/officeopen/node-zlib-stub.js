/**
 * Browser stand-in for `node:zlib`.
 *
 * @office-open/core probes `await import("node:zlib")` at runtime and falls
 * back to its JavaScript deflate/inflate when the import fails (zip-native.ts).
 * Chromium refuses to load a module with the `node:` scheme and logs a CORS
 * error plus a failed request on every page load; this stub makes the import
 * resolve to an empty module, so the library's own feature check
 * (`typeof zlib.deflateRawSync !== "function"`) takes the same fallback path
 * without the console noise.
 */
export {};
