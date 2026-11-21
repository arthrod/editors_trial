import { defineConfig } from 'vite';

// Serves the host page on 5214. The engines run in a module Worker that the
// core package starts from a URL relative to its own chunk, and the fonts
// package fetches each face from its own assets; both are left out of Vite's
// dependency pre-bundling so those relative URLs keep pointing at the packages.
export default defineConfig({
  optimizeDeps: {
    exclude: ['@betteroffice/docx', '@betteroffice/docx-react', '@betteroffice/docx-i18n', '@betteroffice/fonts'],
    // The excluded packages' CommonJS dependencies still need pre-bundling.
    include: [
      'react', 'react-dom', 'react-dom/client', 'react/jsx-runtime',
      '@betteroffice/docx-react > @radix-ui/react-select',
      '@betteroffice/docx-react > clsx',
      '@betteroffice/docx-react > sonner',
    ],
  },
  server: { port: 5214, strictPort: true, host: '127.0.0.1' },
});
