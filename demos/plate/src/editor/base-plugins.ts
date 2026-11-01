'use client';

/**
 * The exact plugin set the trial harness used for the DOCX import.
 *
 * `harness/plate/roundtrip.ts` built its plugin list from the library-level
 * (framework-agnostic) plugins of packages/platejs/src and passed it to
 * `importDocx(buffer, { plugins, lossPolicy, retainSource })`. Those plugins
 * carry the schema and the HTML format maps the DOCX pipeline consumes; the
 * React plugins are thin `toReactPlugin(Base…)` wrappers around them, so the
 * imported tree is the same either way.
 *
 * The list below is the harness list, one entry per line-group, with the
 * module it came from as a comment.
 */
import {
  BaseBlockquotePlugin,
  BaseBoldPlugin,
  BaseCodeBlockPlugin,
  BaseCodePlugin,
  BaseFontBackgroundColorPlugin,
  BaseFontColorPlugin,
  BaseFontFamilyPlugin,
  BaseFontSizePlugin,
  BaseHeadingPlugin,
  BaseHighlightPlugin,
  BaseHorizontalRulePlugin,
  BaseIndentPlugin,
  BaseItalicPlugin,
  BaseKbdPlugin,
  BaseLinkPlugin,
  BaseListPlugin,
  BaseLineHeightPlugin,
  BaseParagraphPlugin,
  BaseScriptPlugin,
  BaseStrikethroughPlugin,
  BaseTextAlignPlugin,
  BaseTextIndentPlugin,
  BaseUnderlinePlugin,
} from 'platejs';
import { BaseCalloutPlugin } from 'platejs/callout';
import { BaseCommentsPlugin } from 'platejs/comments';
import { BaseDatePlugin } from 'platejs/date';
import { BaseDetailsPlugin, BaseDetailsSummaryPlugin } from 'platejs/details';
import { BaseColumnGroupPlugin, BaseColumnItemPlugin } from 'platejs/layout';
import {
  BaseAudioPlugin,
  BaseFilePlugin,
  BaseImagePlugin,
  BaseMediaEmbedPlugin,
  BaseVideoPlugin,
} from 'platejs/media';
import { BaseMentionPlugin } from 'platejs/mention';
import {
  BaseEquationPlugin,
  BaseInlineEquationPlugin,
} from 'platejs/math';
import { BaseTableCellPlugin, BaseTablePlugin, BaseTableRowPlugin } from 'platejs/table';
import { BaseTocPlugin } from 'platejs/toc';
import { BaseUploadPlugin } from 'platejs/upload';
import { BaseFootnoteDefinitionPlugin, BaseFootnotePlugin } from 'platejs/footnote';

export const DocxImportPlugins = [
  BaseParagraphPlugin,

  BaseHeadingPlugin,

  BaseBlockquotePlugin,
  BaseHorizontalRulePlugin,
  BaseIndentPlugin,

  BaseBoldPlugin,
  BaseItalicPlugin,
  BaseUnderlinePlugin,
  BaseStrikethroughPlugin,
  BaseCodePlugin,
  BaseHighlightPlugin,
  BaseKbdPlugin,
  BaseLinkPlugin,
  BaseListPlugin,
  BaseScriptPlugin,

  BaseFontColorPlugin,
  BaseFontBackgroundColorPlugin,
  BaseFontFamilyPlugin,
  BaseFontSizePlugin,
  BaseLineHeightPlugin,
  BaseTextAlignPlugin,
  BaseTextIndentPlugin,

  BaseTablePlugin,
  BaseTableRowPlugin,
  BaseTableCellPlugin,

  BaseLinkPlugin,

  BaseImagePlugin,
  BaseAudioPlugin,
  BaseVideoPlugin,
  BaseFilePlugin,
  BaseMediaEmbedPlugin,

  BaseListPlugin,

  BaseCodeBlockPlugin,

  BaseIndentPlugin,

  BaseMentionPlugin,

  BaseTocPlugin,

  BaseFootnotePlugin,
  BaseFootnoteDefinitionPlugin,

  BaseCommentsPlugin,

  BaseCalloutPlugin,

  BaseColumnGroupPlugin,
  BaseColumnItemPlugin,

  BaseDetailsPlugin,
  BaseDetailsSummaryPlugin,

  BaseDatePlugin,

  BaseUploadPlugin,

  BaseEquationPlugin,
  BaseInlineEquationPlugin,
] as const;
