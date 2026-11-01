import { StrictMode, useState } from 'react';
import { createRoot } from 'react-dom/client';
import {
  DocxEditor,
  useDocxEditor,
  useDocxSource,
  useEditorState,
} from '@docx-editor.dev/react';
import '../../src/packages/core/dist/editor.css';
import './styles.css';
import { downloadDocx } from './download.ts';

const DOCUMENT_URL = './document.docx';

function DownloadButton(): React.JSX.Element {
  const editor = useDocxEditor();
  const busy = useEditorState(
    (snapshot) => snapshot.isLoading || snapshot.isOpening === true
  );
  const [downloading, setDownloading] = useState(false);
  const [message, setMessage] = useState('');

  const onDownload = async (): Promise<void> => {
    if (!editor || busy || downloading) return;
    setDownloading(true);
    setMessage('');
    try {
      const bytes = await editor.save();
      downloadDocx(bytes, 'document.docx');
      setMessage('Downloaded document.docx');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'The document could not be saved.');
    } finally {
      setDownloading(false);
    }
  };

  return (
    <div className="demo-download">
      <button
        type="button"
        className="docx-toolbar__button demo-download__button"
        disabled={!editor || busy || downloading}
        aria-busy={downloading}
        onMouseDown={(event) => event.preventDefault()}
        onClick={() => void onDownload()}
      >
        Download .docx
      </button>
      <span className="demo-download__status" role="status" aria-live="polite">
        {message}
      </span>
    </div>
  );
}

function EditorFrame({ source }: { source: Uint8Array }): React.JSX.Element {
  return (
    <div className="demo-shell">
      <DocxEditor.Root
        document={source}
        mode="edit"
        // The default 'auto' fit stops at 50%, still wider than a phone. Same fit, lower floor.
        zoomMode={{ type: 'fit', fit: 'pageWidth', minZoom: 0.3, maxZoom: 1 }}
        onReady={(editor) => {
          document.documentElement.dataset.editorReady = 'true';
          Object.assign(window, { __EIGENPAL_EDITOR__: editor });
        }}
      >
        <DocxEditor.Toolbar>
          <DownloadButton />
        </DocxEditor.Toolbar>
        <DocxEditor.Viewport
          className="demo-viewport"
          style={{ flex: 1, minHeight: 0 }}
        >
          <DocxEditor.Content />
        </DocxEditor.Viewport>
      </DocxEditor.Root>
    </div>
  );
}

function App(): React.JSX.Element {
  const { document: source, error, isLoading } = useDocxSource(DOCUMENT_URL);

  if (error) {
    return (
      <main className="demo-state demo-state--error" role="alert">
        <h1>Document could not be opened</h1>
        <p>{error.message}</p>
      </main>
    );
  }

  if (isLoading || !source) {
    return (
      <main className="demo-state" role="status" aria-live="polite">
        <span className="demo-state__spinner" aria-hidden="true" />
        <p>Opening document.docx…</p>
      </main>
    );
  }

  return <EditorFrame source={source} />;
}

const root = document.getElementById('root');
if (root) {
  createRoot(root).render(
    <StrictMode>
      <App />
    </StrictMode>
  );
}
