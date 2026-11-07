// genspark-ai/genoffice round trip through the editor model.
//
// This mirrors packages/cli/src/formats/docx.ts openDocument()/saveDocument() but
// imports the renderer modules directly, because that CLI module pulls in the
// @genoffice/ui React barrel (and its CSS) which has no meaning outside a bundler.
//
//   parseDocx(bytes)            -> docx-engine
//   blocksToPmDoc(blocks)       -> apps/docs/src/renderer/editor/convert.ts  (the editor model)
//   Editor.setContent(...)      -> the real Tiptap editor
//   pmDocToSavePlan(doc, blocks)-> the selective-save plan
//   saveDocx(parsed, blocks)    -> docx-engine writer
//
// This file is CommonJS on purpose: the repo's TS sources load through tsx's CJS
// require path, and mixing that with a dynamic import() would give two distinct
// copies of @tiptap/core -> "Adding different instances of a keyed plugin".
//
// usage: node --import ../../harness/css-stub.mjs --import ./node_modules/tsx/dist/loader.mjs \
//          ../../harness/genoffice.cts <in.docx> <out.docx>
const { readFileSync, writeFileSync } = require('node:fs');
const { join, resolve } = require('node:path');

const REPO = join(__dirname, '..', 'repos', 'genoffice');

async function main() {
  const inPath = resolve(process.argv[2]);
  const outPath = resolve(process.argv[3]);

  // 1. DOM first: ProseMirror sniffs the environment at module load time.
  const { ensureDom } = require(`${REPO}/packages/cli/src/dom.ts`);
  await ensureDom();

  // The repo compiles .tsx with the automatic JSX runtime, but tsx's CommonJS path
  // emits classic JSX (React.createElement) for the @genoffice/ui barrel that the
  // editor extensions pull in. Providing the React global satisfies that emitted code.
  const ReactMod = require('react');
  globalThis.React = ReactMod.default ?? ReactMod;

  // 2. Engine + renderer.
  const { parseDocx, saveDocx, readSections } = require('@genoffice/docx-engine');
  const { Editor } = require('@tiptap/core');
  const { editorExtensions } = require(`${REPO}/apps/docs/src/renderer/editor/extensions.ts`);
  const { blocksToPmDoc, pmDocToSavePlan } = require(
    `${REPO}/apps/docs/src/renderer/editor/convert.ts`
  );

  const bytes = new Uint8Array(readFileSync(inPath));

  // 3. Import into the editor model.
  const t0 = performance.now();
  const parsed = await parseDocx(bytes);
  const editor = new Editor({
    element: document.createElement('div'),
    extensions: editorExtensions,
  });
  editor.commands.setContent(blocksToPmDoc(parsed.blocks, readSections(parsed)) as never);
  const t1 = performance.now();
  console.log(`PERF model_ready_ms=${(t1 - t0).toFixed(6)}`);

  // 4. Export back out (no edits -> the selective-save plan should keep original blocks).
  const plan = pmDocToSavePlan(editor.getJSON() as never, parsed.blocks);
  console.log(`[genoffice] plan kinds: ${JSON.stringify(plan.saveBlocks.map((b) => b.kind))}`);
  const ts0 = performance.now();
  const out = await saveDocx(parsed, plan.saveBlocks);
  const ts1 = performance.now();
  console.log(`PERF save_ms=${(ts1 - ts0).toFixed(6)}`);
  writeFileSync(outPath, out);
  console.log(`[genoffice] wrote ${out.byteLength} bytes`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
