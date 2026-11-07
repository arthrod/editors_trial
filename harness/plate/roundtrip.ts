/**
 * Plate.js DOCX round trip over the adversarial corpus.
 *
 * Plate v54's DOCX engine is a headless-capable import/export pair:
 *
 *   importDocx(arrayBuffer, { plugins, lossPolicy, retainSource })
 *     -> { ok, document, comments, diagnostics, source }
 *
 *   exportDocx(editor, { projection, source, lossPolicy, presentation, stylesheet })
 *     -> { ok, blob, diagnostics }
 *
 * Two switches decide what actually happens:
 *
 *   lossPolicy   'reject' (Plate's default) REFUSES a document it cannot
 *                represent losslessly. 'allow' returns it with diagnostics.
 *   retainSource keeps the admitted source package so an UNCHANGED document
 *                can be exported byte-exactly and an edited one can be
 *                exported source-aware. Exact reuse is only admitted when
 *                every part sits in the closed passive vocabulary.
 *
 * `presentation` is the biggest fidelity lever: without a static kit, export
 * falls back to each plugin's own component, and the Base (non-React)
 * plugins carry none - tables, images and lists degrade to plain divs. This
 * harness uses Plate's own kit from apps/www.
 *
 * usage: bun --preload ./aliases.ts roundtrip.ts <input.docx> <output.docx>
 */
import './setup_dom';

import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const HARNESS_DIR = dirname(fileURLToPath(import.meta.url));
const PLATE = join(HARNESS_DIR, '../../repos/plate/packages/platejs/src');
const WWW = join(HARNESS_DIR, '../../repos/plate/apps/www/src/registry/components/editor');

const load = async (p: string) => import(p);

// ---------------------------------------------------------------- plugins
// The DOCX-relevant base plugins: the library-level (framework-agnostic)
// ones, which carry the schema and the HTML format maps the DOCX pipeline
// consumes. The www app composes its own kits on top of these.
const PLUGIN_MODULES: Record<string, string[]> = {
  'lib/plugins/paragraph/BaseParagraphPlugin.ts': ['BaseParagraphPlugin'],
  'features/basic-nodes/lib/BaseHeadingPlugins.ts': ['BaseHeadingPlugin'],
  'features/basic-nodes/lib/BaseBlockPlugins.ts': [
    'BaseBlockquotePlugin',
    'BaseHorizontalRulePlugin',
  ],
  'features/basic-nodes/lib/BaseMarkPlugins.ts': [
    'BaseBoldPlugin',
    'BaseItalicPlugin',
    'BaseUnderlinePlugin',
    'BaseStrikethroughPlugin',
    'BaseCodePlugin',
    'BaseHighlightPlugin',
    'BaseKbdPlugin',
    'BaseScriptPlugin',
  ],
  'features/basic-styles/lib/BaseStylePlugins.ts': [
    'BaseFontColorPlugin',
    'BaseFontBackgroundColorPlugin',
    'BaseFontFamilyPlugin',
    'BaseFontSizePlugin',
    'BaseLineHeightPlugin',
    'BaseTextAlignPlugin',
    'BaseTextIndentPlugin',
  ],
  'features/table/lib/BaseTablePlugin.ts': [
    'BaseTablePlugin',
    'BaseTableRowPlugin',
    'BaseTableCellPlugin',
  ],
  'features/link/lib/BaseLinkPlugin.ts': ['BaseLinkPlugin'],
  'features/media/lib/image/BaseImagePlugin.ts': ['BaseImagePlugin'],
  'features/media/lib/BaseMediaPlugin.ts': [
    'BaseAudioPlugin',
    'BaseVideoPlugin',
    'BaseFilePlugin',
  ],
  'features/media/lib/media-embed/BaseMediaEmbedPlugin.ts': ['BaseMediaEmbedPlugin'],
  'features/list/lib/BaseListPlugin.ts': ['BaseListPlugin'],
  'features/code-block/lib/BaseCodeBlockPlugin.ts': ['BaseCodeBlockPlugin'],
  'features/indent/lib/BaseIndentPlugin.ts': ['BaseIndentPlugin'],
  'features/mention/lib/BaseMentionPlugin.ts': ['BaseMentionPlugin'],
  'features/toc/lib/BaseTocPlugin.ts': ['BaseTocPlugin'],
  'features/footnote/lib/BaseFootnotePlugin.ts': [
    'BaseFootnotePlugin',
    'BaseFootnoteDefinitionPlugin',
  ],
  'features/comments/BaseCommentsPlugin.ts': ['BaseCommentsPlugin'],
  'features/callout/lib/BaseCalloutPlugin.ts': ['BaseCalloutPlugin'],
  'features/layout/lib/BaseColumnPlugin.ts': [
    'BaseColumnGroupPlugin',
    'BaseColumnItemPlugin',
  ],
  'features/details/lib/BaseDetailsPlugin.ts': [
    'BaseDetailsPlugin',
    'BaseDetailsSummaryPlugin',
  ],
  'features/date/lib/BaseDatePlugin.ts': ['BaseDatePlugin'],
  'features/upload/lib/BaseUploadPlugin.ts': ['BaseUploadPlugin'],
  'math/lib/BaseEquationPlugin.ts': [
    'BaseEquationPlugin',
    'BaseInlineEquationPlugin',
  ],
};

async function buildPlugins() {
  const plugins: any[] = [];
  const missing: string[] = [];
  for (const [file, names] of Object.entries(PLUGIN_MODULES)) {
    let mod: any;
    try {
      mod = await load(`${PLATE}/${file}`);
    } catch (e: any) {
      missing.push(`${file}: ${e?.message ?? e}`);
      continue;
    }
    for (const n of names) {
      const p = mod[n];
      if (!p) {
        missing.push(`${file} -> ${n} not exported`);
        continue;
      }
      plugins.push(p);
    }
  }
  return { plugins, missing };
}

// The static presentation kit: Plate's own, from the www app.
async function buildPresentation() {
  const kitFiles = [
    'basic-blocks-static',
    'basic-marks-static',
    'block-list-static',
    'blockquote-static',
    'callout-static',
    'caption-static',
    'code-block-static',
    'code-static',
    'column-static',
    'date-static',
    'details-static',
    'font-static',
    'footnote-static',
    'heading-static',
    'highlight-static',
    'horizontal-rule-static',
    'indent-static',
    'kbd-static',
    'link-static',
    'list-static',
    'math-static',
    'media-audio-static',
    'media-embed-static',
    'media-file-static',
    'media-image-static',
    'media-static',
    'media-video-static',
    'mention-static',
    'paragraph-static',
    'table-static',
    'toc-static',
  ];
  const kit: any[] = [];
  const missing: string[] = [];
  for (const f of kitFiles) {
    try {
      const mod = await load(`${WWW}/${f}.tsx`);
      for (const [k, v] of Object.entries(mod)) {
        // Each *-static.tsx exports a Kit: an array of plugins configured with
        // their static React component. `presentation` takes plugins, not
        // components - passing a raw component throws "Editor plugins must be
        // created by definePlugin".
        if (Array.isArray(v)) kit.push(...v);
      }
    } catch (e: any) {
      missing.push(`${f}: ${e?.message ?? e}`);
    }
  }
  return { kit, missing };
}

// ------------------------------------------------------------------- main
const [, , inPath, outPath] = process.argv;

const { plugins, missing } = await buildPlugins();
const { kit, missing: kitMissing } = await buildPresentation();
if (missing.length || kitMissing.length) {
  console.log('RESOLUTION PROBLEMS:');
  for (const m of [...missing, ...kitMissing]) console.log('  ' + m);
}
console.log(`plugins: ${plugins.length}, presentation components: ${kit.length}`);

let DOCX_EXPORT_STYLES = '';
try {
  const mod = await load(`${WWW}/docx-export.tsx`);
  DOCX_EXPORT_STYLES = mod.DOCX_EXPORT_STYLES ?? '';
  console.log(`stylesheet: ${DOCX_EXPORT_STYLES.length} chars`);
} catch (e: any) {
  console.log(`stylesheet unavailable: ${e?.message}`);
}

const { importDocx } = await load(`${PLATE}/docx/import/index.ts`);
const { exportDocx } = await load(`${PLATE}/docx/export/index.ts`);
const { createEditor } = await load(`${PLATE}/index.tsx`);

const bytes = readFileSync(inPath);
const ab = () =>
  bytes.buffer.slice(
    bytes.byteOffset,
    bytes.byteOffset + bytes.byteLength
  ) as ArrayBuffer;

const show = (label: string, ds: readonly any[], limit = 40) => {
  console.log(`\n=== ${label} ===`);
  console.log(`diagnostics: ${ds.length}`);
  const codes: Record<string, number> = {};
  for (const d of ds) codes[d.code] = (codes[d.code] ?? 0) + 1;
  console.log('codes: ' + JSON.stringify(codes));
  const errors = ds.filter((d) => d.severity === 'error');
  console.log(`errors: ${errors.length}`);
  for (const d of ds.slice(0, limit)) {
    console.log(`  [${d.severity}] ${d.code}: ${d.message}`);
  }
};

// Bomb runs set EDITOR_CONFIG=suggested. That is the round trip documented in
// content/docs/(plugins)/(serializing)/docx.mdx: BaseEditorKit, retainSource,
// and the default loss policy, which is reject. A refused import or export
// writes no file. The permissive second pass below is only for the fidelity
// corpus, where the question was what survives, not what the default does.
if (process.env.EDITOR_CONFIG === 'suggested') {
  const { BaseEditorKit } = await load(`${WWW}/plugins-static.ts`);
  const suggestedPlugins = [...BaseEditorKit];
  console.log(`suggested BaseEditorKit plugins: ${suggestedPlugins.length}`);
  const imported = await importDocx(ab(), {
    plugins: suggestedPlugins,
    retainSource: true,
  });
  console.log(`suggested import ok: ${imported.ok}`);
  show('suggested import', imported.diagnostics ?? [], 40);
  if (!imported.ok) {
    console.log('suggested import refused the file. no export was written.');
    process.exit(1);
  }
  const suggestedEditor = createEditor({
    plugins: suggestedPlugins,
    initialValue: imported.document as any,
  });
  const suggestedExport = await exportDocx(suggestedEditor as any, {
    projection: 'review',
    source: imported.source ?? null,
    presentation: suggestedPlugins,
  });
  console.log(`suggested export ok: ${suggestedExport.ok}`);
  if (!suggestedExport.ok) {
    show('suggested export', suggestedExport.diagnostics ?? [], 40);
    console.log('suggested export refused the file. no export was written.');
    process.exit(1);
  }
  const suggestedOut = Buffer.from(await suggestedExport.blob.arrayBuffer());
  mkdirSync(dirname(outPath), { recursive: true });
  writeFileSync(outPath, suggestedOut);
  console.log(`suggested export wrote ${suggestedOut.byteLength} bytes`);
  process.exit(0);
}

// 1) Plate's own default loss policy: reject
const strict = await importDocx(ab(), {
  lossPolicy: 'reject',
  plugins,
  retainSource: true,
});
console.log(`\n=== IMPORT (lossPolicy: 'reject' - Plate's default) ===`);
console.log(`ok: ${strict.ok}`);
if (!strict.ok) {
  show('strict import diagnostics', strict.diagnostics, 40);
} else {
  show('strict import diagnostics', strict.diagnostics, 40);
  console.log(`comments: ${strict.comments.length}`);
  console.log(`source retained: ${strict.source !== null}`);
}

// 2) permissive import, then export
const tLoad0 = performance.now();
const permissive = await importDocx(ab(), {
  lossPolicy: 'allow',
  plugins,
  retainSource: true,
});
if (!permissive.ok) {
  console.log('\n=== IMPORT (lossPolicy: allow) ALSO FAILED ===');
  for (const d of permissive.diagnostics.slice(0, 25)) {
    console.log(`  [${d.severity}] ${d.code}: ${d.message}`);
  }
  process.exit(2);
}
show('IMPORT (lossPolicy: allow)', permissive.diagnostics, 45);
console.log(`comments: ${permissive.comments.length}`);
console.log(`source retained: ${permissive.source !== null}`);

const editor = createEditor({
  plugins,
  initialValue: permissive.document as any,
});
const tLoad1 = performance.now();
console.log(`PERF model_ready_ms=${(tLoad1 - tLoad0).toFixed(6)}`);

const tSave0 = performance.now();
const exported = await exportDocx(editor as any, {
  projection: 'accepted',
  source: permissive.source ?? null,
  lossPolicy: 'allow',
  presentation: kit.length ? (kit as any) : undefined,
  stylesheet: DOCX_EXPORT_STYLES || undefined,
});
const tSave1 = performance.now();
console.log(`PERF save_ms=${(tSave1 - tSave0).toFixed(6)}`);

console.log(`\n=== EXPORT ===`);
console.log(`ok: ${exported.ok}`);
if (!exported.ok) {
  for (const d of exported.diagnostics.slice(0, 30)) {
    console.log(`  [${d.severity}] ${d.code}: ${d.message}`);
  }
  process.exit(3);
}
show('export diagnostics', exported.diagnostics, 45);

const out = Buffer.from(await exported.blob.arrayBuffer());
mkdirSync(dirname(outPath), { recursive: true });
writeFileSync(outPath, out);
console.log(`\nWROTE ${outPath} (${out.length} bytes)`);
console.log(`input was ${bytes.length} bytes; identical: ${out.equals(bytes)}`);
