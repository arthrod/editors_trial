/**
 * Plate.js DOCX editor - rendering study host.
 *
 * This is the editor under test, running for real:
 *   - `platejs` (Plate.js v54) compiled from the repo's TypeScript source,
 *   - the DOCX importer (`platejs/docx/import`) that the www demo uses,
 *   - the editor's own React rendering pipeline (`EditorRoot` + `EditorContent`).
 *
 * The document is fetched from `/corpus.docx`; the Playwright driver
 * intercepts that request and answers with the fixture bytes.
 */
import katex from 'katex';
import * as React from 'react';
import { createRoot } from 'react-dom/client';

import {
  BlockquotePlugin,
  BoldPlugin,
  CodeBlockPlugin,
  createEditor,
  EditorContent,
  EditorElement,
  EditorLeaf,
  EditorRoot,
  FontBackgroundColorPlugin,
  FontColorPlugin,
  FontFamilyPlugin,
  FontSizePlugin,
  HeadingPlugin,
  HighlightPlugin,
  HorizontalRulePlugin,
  IndentPlugin,
  ItalicPlugin,
  KbdPlugin,
  LineHeightPlugin,
  LinkPlugin,
  ListPlugin,
  ParagraphPlugin,
  ScriptPlugin,
  StrikethroughPlugin,
  TextAlignPlugin,
  UnderlinePlugin,
} from 'platejs/react';
import { importDocx } from 'platejs/docx/import';
import { CommentsPlugin } from 'platejs/comments/react';
import { FootnoteDefinitionPlugin, FootnotePlugin } from 'platejs/footnote/react';
import { EquationPlugin, InlineEquationPlugin } from 'platejs/math/react';
import { ImagePlugin } from 'platejs/media/react';
import { TableCellPlugin, TablePlugin, TableRowPlugin } from 'platejs/table/react';

import 'katex/dist/katex.min.css';

import './style.css';

/* ------------------------------------------------------------------ *
 * Element components
 *
 * Plate's base plugins own the schema; the React layer needs a
 * `component` per element type.  These are the same shapes the www
 * registry uses (table -> table > tbody > tr > td/th, equation via
 * katex, media via <img>).
 * ------------------------------------------------------------------ */

type ElementProps = Record<string, any>;

const ParagraphElement = (props: ElementProps) => (
  // Plate's own www registry renders the paragraph as a div (see
  // apps/www/src/registry/components/editor/paragraph.tsx): the list plugin
  // wraps an element's *children* in <ol>/<ul>, which is invalid inside <p>.
  <EditorElement {...props} className="doc-paragraph">
    {props.children}
  </EditorElement>
);

const TableElement = (props: ElementProps) => (
  <EditorElement {...props} as="table" className="doc-table">
    <tbody>{props.children}</tbody>
  </EditorElement>
);

const TableRowElement = (props: ElementProps) => (
  <EditorElement {...props} as="tr" className="doc-table-row">
    {props.children}
  </EditorElement>
);

const TableCellElement = (props: ElementProps) => {
  const isHeader = props.element.header === true;

  return (
    <EditorElement
      {...props}
      as={isHeader ? 'th' : 'td'}
      className={isHeader ? 'doc-table-cell doc-table-head' : 'doc-table-cell'}
    >
      {props.children}
    </EditorElement>
  );
};

const ImageElement = (props: ElementProps) => (
  <EditorElement {...props} as="figure" className="doc-image">
    <img
      alt={props.element.alt ?? ''}
      contentEditable={false}
      src={props.element.url}
      style={{ maxWidth: '100%' }}
    />
    {props.children}
  </EditorElement>
);

const EquationElement = (props: ElementProps) => {
  const latex = String(props.element.latex ?? props.element.value ?? '');

  let html = '';

  try {
    html = katex.renderToString(latex, {
      displayMode: true,
      throwOnError: false,
    });
  } catch (error) {
    html = `<code>${latex}</code>`;
  }

  return (
    <EditorElement {...props} as="div" className="doc-equation">
      <span dangerouslySetInnerHTML={{ __html: html }} />
      {props.children}
    </EditorElement>
  );
};

const InlineEquationElement = (props: ElementProps) => {
  const latex = String(props.element.latex ?? props.element.value ?? '');

  let html = '';

  try {
    html = katex.renderToString(latex, {
      displayMode: false,
      throwOnError: false,
    });
  } catch (error) {
    html = `<code>${latex}</code>`;
  }

  return (
    <EditorLeaf {...props} as="span" className="doc-equation-inline">
      <span dangerouslySetInnerHTML={{ __html: html }} />
    </EditorLeaf>
  );
};

const LinkElement = (props: ElementProps) => (
  <EditorElement {...props} as="a" className="doc-link">
    {props.children}
  </EditorElement>
);

/* ------------------------------------------------------------------ *
 * Plugin set
 *
 * Mirrors apps/www/src/registry/examples/docx-demo.tsx: the www
 * `EditorKit` (minus the fixed toolbar) plus the DOCX paste plugin.
 * ------------------------------------------------------------------ */

const plugins = [
  ParagraphPlugin.configure({ component: ParagraphElement }),
  HeadingPlugin,
  BlockquotePlugin,
  HorizontalRulePlugin,

  BoldPlugin,
  ItalicPlugin,
  UnderlinePlugin,
  StrikethroughPlugin,
  HighlightPlugin,
  KbdPlugin,
  ScriptPlugin,

  ListPlugin,
  IndentPlugin,
  TextAlignPlugin,
  FontColorPlugin,
  FontBackgroundColorPlugin,
  FontFamilyPlugin,
  FontSizePlugin,
  LineHeightPlugin,

  TablePlugin.configure({ component: TableElement }),
  TableRowPlugin.configure({ component: TableRowElement }),
  TableCellPlugin.configure({ component: TableCellElement }),

  ImagePlugin.configure({ component: ImageElement }),
  EquationPlugin.configure({ component: EquationElement }),
  InlineEquationPlugin.configure({ component: InlineEquationElement }),
  LinkPlugin.configure({ component: LinkElement }),
  FootnotePlugin,
  FootnoteDefinitionPlugin,
  CommentsPlugin,
  CodeBlockPlugin,
] as const;

type Status = {
  state: 'loading' | 'ok' | 'error';
  message: string;
  details?: string;
};

function App() {
  const [editor, setEditor] = React.useState<any>(null);
  const [status, setStatus] = React.useState<Status>({
    state: 'loading',
    message: 'Loading corpus…',
  });

  React.useEffect(() => {
    let cancelled = false;

    const run = async () => {
      try {
        const response = await fetch('/corpus.docx');

        if (!response.ok) {
          throw new Error(`HTTP ${response.status} for /corpus.docx`);
        }

        const buffer = await response.arrayBuffer();
        const result: any = await importDocx(buffer, {
          lossPolicy: 'allow',
          plugins: plugins as any,
          retainSource: false,
        });

        if (cancelled) return;

        if (!result.ok) {
          const error = result.diagnostics.find(
            (d: any) => d.severity === 'error'
          );

          setStatus({
            state: 'error',
            message: error?.message ?? 'The Word document could not be imported.',
            details: JSON.stringify(result.diagnostics, null, 1),
          });

          return;
        }

        const imported = createEditor({
          initialValue: result.document.children,
          plugins: plugins as any,
          userId: 'alice',
        });

        setEditor(imported);

        const warnings = result.diagnostics.filter(
          (d: any) => d.severity === 'warning'
        );

        setStatus({
          state: 'ok',
          message:
            `Imported ${result.document.children.length} blocks; ` +
            `${result.comments.length} comment(s); ` +
            `${warnings.length} warning(s).`,
          details: warnings
            .map((d: any) => `[${d.feature ?? d.code}] ${d.message}`)
            .join('\n'),
        });
      } catch (error: any) {
        if (cancelled) return;

        setStatus({
          state: 'error',
          message: String(error?.message ?? error),
          details: String(error?.stack ?? ''),
        });
      }
    };

    void run();

    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="app">
      <header className="app-bar">
        <strong>Plate.js</strong>
        <span className="app-bar-sub">platejs 54.0.0-beta.1 &middot; DOCX import</span>
        <span className={`status status-${status.state}`}>{status.message}</span>
      </header>
      <main className="app-body">
        {editor ? (
          <EditorRoot editor={editor}>
            <EditorContent className="doc-content" />
          </EditorRoot>
        ) : null}
      </main>
      {status.details ? (
        <details className="app-details">
          <summary>import diagnostics</summary>
          <pre>{status.details}</pre>
        </details>
      ) : null}
    </div>
  );
}

createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
