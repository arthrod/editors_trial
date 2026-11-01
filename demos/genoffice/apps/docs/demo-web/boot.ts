// GenOffice Docs in a browser, for benchmarks.law.
//
// The Docs app is an Electron renderer: everything it asks of the desktop goes through
// window.desktop (apps/docs/src/preload/index.ts). This page installs a stand-in before the
// app's own entry (../src/renderer/main.tsx) runs:
//   consumePendingOpenDocx  hands the app ./document.docx, as if it had been opened from disk
//   saveDocx / saveDocxAs   turn the bytes the app's own writer produced into a browser download
//   onMenuCommand           lets the Download button send the app its own "save-as" command
// Everything else answers with an empty default; nothing leaves the page.
import './desktop-stub'
import '../src/renderer/main.tsx'
