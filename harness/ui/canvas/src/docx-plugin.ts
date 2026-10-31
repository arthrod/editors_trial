import type Editor from '@hufe921/canvas-editor'
import importDocx from '@docx-plugin'

/**
 * Thin wrapper around the official `@hufe921/canvas-editor-plugin-docx`
 * import routine (same author / same workspace as the editor core).
 *
 * We deliberately import only `importDocx` and not the plugin's `index.ts`,
 * because `index.ts` also pulls in `exportDocx` -> the `docx` npm package,
 * which is not needed for a render-only study and only slows the dev server
 * down.
 */
export default function docxPlugin(editor: Editor) {
  const command = editor.command as unknown as {
    executeImportDocx: (options: { arrayBuffer: ArrayBuffer }) => void
  }
  command.executeImportDocx = importDocx(editor.command)
}
