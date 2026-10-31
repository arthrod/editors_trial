/**
 * Dump the node tree Plate's DOCX import produces for the corpus.
 * Read-only diagnostic: nothing is written.
 *
 * usage: bun --preload ./aliases.ts dump_import.ts <input.docx>
 */
import './setup_dom';

import { readFileSync } from 'node:fs';

const PLATE = '/Users/arthrod/temp/T/editors_trial/repos/plate/repos-placeholder';
const SRC = '/Users/arthrod/temp/T/editors_trial/repos/plate/packages/platejs/src';

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
  let mod: any;
  try {
    mod = await import(`${SRC}/${file}`);
  } catch (e: any) {
    console.log(`MISSING ${file}: ${e?.message ?? e}`);
    continue;
  }
  for (const n of names) {
    if (mod[n]) plugins.push(mod[n]);
    else console.log(`MISSING export ${file} -> ${n}`);
  }
}

const { importDocx } = await import(`${SRC}/docx/import/index.ts`);
const bytes = readFileSync(process.argv[2]);
const ab = bytes.buffer.slice(
  bytes.byteOffset,
  bytes.byteOffset + bytes.byteLength
) as ArrayBuffer;

const res: any = await importDocx(ab, { lossPolicy: 'allow', plugins, retainSource: false });
console.log(`ok: ${res.ok}`);
console.log(`comments: ${res.comments?.length ?? 0}`);
if (res.comments?.length) {
  console.log(JSON.stringify(res.comments, null, 1).slice(0, 3000));
}

const text = (n: any): string => {
  if (typeof n?.text === 'string') return n.text;
  if (Array.isArray(n?.children)) return n.children.map(text).join('');
  return '';
};

const dump = (n: any, depth = 0): void => {
  const pad = '  '.repeat(depth);
  const type = n?.type ?? '(text)';
  const keys = Object.keys(n ?? {})
    .filter((k) => !['children', 'text', 'type'].includes(k))
    .slice(0, 6);
  const extra = keys.length
    ? ' ' +
      JSON.stringify(
        Object.fromEntries(keys.map((k) => [k, n[k]])),
      ).slice(0, 220)
    : '';
  console.log(`${pad}<${type}>${extra} :: ${JSON.stringify(text(n)).slice(0, 120)}`);
  if (Array.isArray(n?.children)) for (const c of n.children) dump(c, depth + 1);
};

dump(res.document);
