'use client';

import { exportDocx } from 'platejs/docx/export';
import { createEditor, EditorContent, EditorRoot } from 'platejs/react';
import * as React from 'react';

import { EditorKit } from './editor/plugins';
import { useDocument } from './use-document';
import { DOCX_EXPORT_STYLES } from './kit/docx-export';
import { EditorStatic } from './kit/editor-static';
import { BaseEditorKit } from './kit/plugins-static';

const downloadBlob = (blob: Blob, filename: string) => {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');

  link.href = url;
  link.download = filename;
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
};

function DocxEditor({
  document,
  source,
}: {
  document: never;
  source: unknown;
}) {
  const [editor] = React.useState(() =>
    createEditor({
      initialValue: document,
      plugins: EditorKit,
    })
  );
  const [busy, setBusy] = React.useState(false);
  const [message, setMessage] = React.useState<string | null>(null);

  // The live editor is exposed on `window` so the document that was imported
  // can be read back through Plate's own API (editor.read(state => state.value()))
  // and not only through the rendered DOM.
  React.useEffect(() => {
    (window as unknown as { __plateEditor?: unknown }).__plateEditor = editor;
  }, [editor]);

  const onDownload = React.useCallback(async () => {
    setBusy(true);
    setMessage(null);

    try {
      const result = await exportDocx(editor as never, {
        component: EditorStatic,
        // The download still completes; the note below reports what was lost.
        lossPolicy: 'allow',
        presentation: BaseEditorKit,
        projection: 'accepted',
        source: source as never,
        stylesheet: DOCX_EXPORT_STYLES,
      });

      if (!result.ok) {
        setMessage(
          result.diagnostics.find(({ severity }) => severity === 'error')
            ?.message ?? 'The Word document could not be exported.'
        );

        return;
      }

      downloadBlob(result.blob, 'document.docx');

      const lost = result.diagnostics.filter(
        ({ severity, impact }) =>
          severity === 'warning' && impact !== 'lossless'
      ).length;

      setMessage(
        lost > 0
          ? `Exported with ${lost} warning${lost === 1 ? '' : 's'}.`
          : 'Exported.'
      );
    } catch (error) {
      setMessage(
        error instanceof Error ? error.message : 'The export failed.'
      );
    } finally {
      setBusy(false);
    }
  }, [editor, source]);

  return (
    <div className="demo-shell">
      <div className="demo-toolbar">
        <button
          className="demo-button"
          disabled={busy}
          onClick={onDownload}
          type="button"
        >
          {busy ? 'Exporting…' : 'Download .docx'}
        </button>
        {message ? <span className="demo-note">{message}</span> : null}
      </div>
      <div className="demo-content">
        <EditorRoot editor={editor}>
          <EditorContent className="demo-editor" />
        </EditorRoot>
      </div>
    </div>
  );
}

export function App() {
  const state = useDocument();

  React.useEffect(() => {
    (window as unknown as { __plateImport?: unknown }).__plateImport = state;
  }, [state]);

  if (state.status === 'loading') {
    return <div className="demo-status">Loading document.docx…</div>;
  }

  if (state.status === 'error') {
    return (
      <div className="demo-status demo-status-error">
        <p>{state.message}</p>
        <ul>
          {state.diagnostics.slice(0, 12).map((diagnostic, index) => (
            <li key={index}>
              [{diagnostic.severity}] {diagnostic.code}: {diagnostic.message}
            </li>
          ))}
        </ul>
      </div>
    );
  }

  return (
    <DocxEditor
      document={state.document as never}
      source={state.source}
    />
  );
}
