import { Editor, type Extensions, type JSONContent } from '@tiptap/core'
import { Highlight as BaseHighlight } from '@tiptap/extension-highlight'
import { TaskItem, TaskList } from '@tiptap/extension-list'
import Paragraph from '@tiptap/extension-paragraph'
import Subscript from '@tiptap/extension-subscript'
import Superscript from '@tiptap/extension-superscript'
import { Table, TableCell, TableHeader, TableRow } from '@tiptap/extension-table'
import TextAlign from '@tiptap/extension-text-align'
import Typography from '@tiptap/extension-typography'
import { UniqueID } from '@tiptap/extension-unique-id'
import { UndoRedo } from '@tiptap/extensions'
import StarterKit from '@tiptap/starter-kit'
import { Hyperlink } from '@docs.plus/extension-hyperlink'
import { HyperMultimediaKit, isMediaUrl } from '@docs.plus/extension-hypermultimedia'
import { Indent } from '@docs.plus/extension-indent'
import { InlineCode } from '@docs.plus/extension-inline-code'
import { Mermaid } from '@docs.plus/extension-mermaid'
import { Placeholder } from '@docs.plus/extension-placeholder'
import ShortUniqueId from 'short-unique-id'

// The webapp's own editor extensions (apps/webapp/src/components/TipTap/extensions).
// They are copied verbatim from the checkout so the demo editor has the same
// schema as the product: `paragraphStyle` on paragraphs, the `doc` node whose
// first child must be a heading, and the `highlight` mark with its `color`.
import { ParagraphStyle } from '../../src/apps/webapp/src/components/TipTap/extensions/paragraph-style'
import { TitleDocument } from '../../src/apps/webapp/src/components/TipTap/extensions/title-document'
import { Highlight } from '../../src/apps/webapp/src/components/TipTap/extensions/highlight'

const headingTableUid = new ShortUniqueId()

/**
 * The demo editor mirrors `apps/webapp/src/components/TipTap/TipTap.tsx`
 * (the pad editor), minus the parts that need a live server: collaboration,
 * chat, the slash menu, the find bar, heading folding, the media toolbar and
 * the lowlight code blocks. Every node and mark the product's schema declares
 * is registered, so an imported document validates against this schema.
 */
export const createExtensions = (): Extensions => [
  StarterKit.configure({
    // `TitleDocument` owns the `doc` node and `ParagraphStyle` owns `paragraph`.
    document: false,
    paragraph: false,
    // Undo/redo comes from the `UndoRedo` extension (no collaboration here).
    undoRedo: false,
    heading: { levels: [1, 2, 3, 4, 5, 6] },
    // Stored pad documents contain `link` marks, so `link` stays registered
    // (inert); `Hyperlink` owns every `<a>` the importer produces.
    link: {
      autolink: false,
      linkOnPaste: false,
      openOnClick: false,
      shouldAutoLink: () => false
    },
    // `Indent` owns Tab.
    listKeymap: false,
    trailingNode: false
  }),
  ParagraphStyle,
  TitleDocument,
  TaskList,
  TaskItem.configure({ nested: true }),
  UniqueID.configure({
    attributeName: 'toc-id',
    types: ['heading', 'hyperlink', 'table'],
    generateID: () => headingTableUid.stamp(16)
  }),
  Indent.configure({
    indentChars: '\t',
    allowedIndentContexts: [
      { textblock: 'paragraph', parent: 'doc' },
      { textblock: 'paragraph', parent: 'blockquote' },
      { textblock: 'heading', parent: 'doc' }
    ]
  }),
  InlineCode,
  Superscript,
  Subscript,
  TextAlign,
  Hyperlink.configure({
    protocols: ['ftp', 'mailto'],
    linkOnPaste: false,
    autolink: true,
    exitable: true,
    shouldAutoLink: (url: string) => !isMediaUrl(url)
  }),
  HyperMultimediaKit.configure({
    Image: { inline: true, allowBase64: true }
  }),
  Highlight,
  Typography,
  Table.configure({ resizable: true }),
  TableRow,
  TableHeader,
  TableCell,
  Placeholder.configure({ placeholder: 'Write something…' }),
  UndoRedo,
  Mermaid.configure({})
]

export const createEditor = (element: HTMLElement, content: JSONContent): Editor =>
  new Editor({
    element,
    extensions: createExtensions(),
    content,
    autofocus: false,
    editorProps: {
      attributes: {
        spellcheck: 'false',
        class: 'docsplus-prosemirror'
      }
    }
  })

export { BaseHighlight }
