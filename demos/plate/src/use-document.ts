'use client';

import * as React from 'react';

import { DocxImportPlugins } from './editor/base-plugins';

type DocxDiagnostic = {
  code: string;
  message: string;
  severity: string;
};

type ImportState =
  | { status: 'loading' }
  | { status: 'error'; message: string; diagnostics: readonly DocxDiagnostic[] }
  | {
      status: 'ready';
      document: unknown;
      source: unknown;
      diagnostics: readonly DocxDiagnostic[];
    };

/**
 * The document is fetched from the site's own folder and opened with Plate's
 * own DOCX import, the same call the app's own "Import from Word" button
 * makes: `importDocx(arrayBuffer, { lossPolicy, plugins, retainSource })`.
 */
const loadDocument = async (
  signal: AbortSignal
): Promise<ImportState> => {
  const [{ importDocx }, response] = await Promise.all([
    import('platejs/docx/import'),
    // Relative to this page, so the request stays inside the demo's own
    // folder however the host site mounts it.
    fetch('./document.docx', { signal }),
  ]);

  if (!response.ok) {
    throw new Error(`document.docx could not be fetched (${response.status}).`);
  }

  const buffer = await response.arrayBuffer();
  const result = await importDocx(buffer, {
    // 'allow' is the permissive half of the trial's round trip: Plate's
    // default loss policy ('reject') refuses this document, the trial's
    // measured pass imported it with 'allow'.
    lossPolicy: 'allow',
    plugins: DocxImportPlugins,
    retainSource: true,
  });

  if (!result.ok) {
    return {
      diagnostics: result.diagnostics,
      message:
        result.diagnostics.find(({ severity }) => severity === 'error')
          ?.message ?? 'The Word document could not be imported.',
      status: 'error',
    };
  }

  return {
    diagnostics: result.diagnostics,
    document: result.document,
    source: result.source ?? null,
    status: 'ready',
  };
};

export function useDocument(): ImportState {
  const [state, setState] = React.useState<ImportState>({ status: 'loading' });

  React.useEffect(() => {
    const controller = new AbortController();

    void loadDocument(controller.signal)
      .then(setState)
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;

        setState({
          diagnostics: [],
          message:
            error instanceof Error ? error.message : 'The document failed to load.',
          status: 'error',
        });
      });

    return () => controller.abort();
  }, []);

  return state;
}
