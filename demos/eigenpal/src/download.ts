export const DOCX_MIME =
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document';

export function createDocxBlob(bytes: ArrayBuffer | Uint8Array): Blob {
  const part = bytes instanceof Uint8Array ? bytes.slice().buffer : bytes;
  return new Blob([part], { type: DOCX_MIME });
}

export function downloadDocx(
  bytes: ArrayBuffer | Uint8Array,
  filename = 'document.docx'
): void {
  const blob = createDocxBlob(bytes);
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
}
