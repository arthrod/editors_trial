/**
 * Which defect classes does Plate's importer detect?
 *
 * Import each single-defect corpus and report the verdict and the diagnostic
 * codes. Plate's importer either accepts the document (with warnings) or
 * refuses it; the refusal codes say WHY.
 *
 * usage: bun --preload ./aliases.ts defect_probe.ts <dir-with-dNN.docx>
 */
import './setup_dom';

import { readFileSync } from 'node:fs';
import { readdirSync } from 'node:fs';

const PLATE = '/Users/arthrod/temp/T/editors_trial/repos/plate/packages/platejs/src';

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

const plugins: any[] = [];
for (const [file, names] of Object.entries(PLUGIN_MODULES)) {
  const mod: any = await import(`${PLATE}/${file}`);
  for (const n of names) plugins.push(mod[n]);
}

const { importDocx } = await import(`${PLATE}/docx/import/index.ts`);

const dir = process.argv[2];
const files = readdirSync(dir)
  .filter((f) => f.endsWith('.docx'))
  .sort();

console.log('file        verdict   errors  codes');
for (const f of files) {
  const bytes = readFileSync(`${dir}/${f}`);
  const ab = bytes.buffer.slice(
    bytes.byteOffset,
    bytes.byteOffset + bytes.byteLength
  ) as ArrayBuffer;
  const r = await importDocx(ab, {
    lossPolicy: 'allow',
    plugins,
    retainSource: true,
  });
  const codes: Record<string, number> = {};
  for (const d of r.diagnostics) codes[d.code] = (codes[d.code] ?? 0) + 1;
  const errors = r.diagnostics.filter((d: any) => d.severity === 'error').length;
  const verdict = r.ok ? 'ACCEPTED' : 'REFUSED';
  console.log(
    `${f.padEnd(11)} ${verdict.padEnd(9)} ${String(errors).padStart(4)}   ${JSON.stringify(codes)}`
  );
  if (!r.ok) {
    for (const d of r.diagnostics.filter((x: any) => x.severity === 'error').slice(0, 3)) {
      console.log(`             -> ${d.code}: ${d.message}`);
    }
  }
}
