import { SuperDoc } from 'superdoc';
import 'superdoc/style.css';

const exportButton = document.querySelector<HTMLButtonElement>('#export-docx');

if (!exportButton) throw new Error('The export button is missing.');

const superdoc = new SuperDoc({
  selector: '#editor',
  document: '/sample.docx',
  onReady: () => {
    performance.mark('superdoc-model-ready');
    exportButton.disabled = false;
    requestAnimationFrame(() => {
      const surface = document.querySelector('#editor .superdoc__document');
      if (surface) {
        performance.mark('superdoc-first-usable');
      }
    });
  },
  onContentError: ({ error }) => {
    console.error('SuperDoc could not open the document.', error);
  },
  onException: ({ error }) => {
    console.error('SuperDoc could not open the document.', error);
  },
});

exportButton.addEventListener('click', async () => {
  exportButton.disabled = true;
  try {
    await superdoc.export({ exportType: ['docx'], exportedName: 'sample-edited' });
  } catch (error) {
    console.error('SuperDoc could not export the document.', error);
  } finally {
    exportButton.disabled = false;
  }
});
