'use client';

import {
  BaseFontBackgroundColorPlugin,
  BaseFontColorPlugin,
  BaseFontFamilyPlugin,
  BaseFontSizePlugin,
  BaseLineHeightPlugin,
  BaseTextAlignPlugin,
  BaseTextIndentPlugin,
  isOrderedList,
  ListType,
  PLUGINS,
  TrailingBlockPlugin,
} from 'platejs';
import {
  BlockquotePlugin,
  BoldPlugin,
  CodePlugin,
  EditorElement,
  EditorLeaf,
  HeadingPlugin,
  HighlightPlugin,
  HorizontalRulePlugin,
  ItalicPlugin,
  KbdPlugin,
  LinkPlugin,
  ListPlugin,
  ParagraphPlugin,
  ScriptPlugin,
  StrikethroughPlugin,
  UnderlinePlugin,
} from 'platejs/react';
import {
  TableCellPlugin,
  TablePlugin,
  TableRowPlugin,
} from 'platejs/table/react';
import { EquationPlugin, InlineEquationPlugin } from 'platejs/math/react';
import katex from 'katex';
import * as React from 'react';

import { cn } from '../kit/lib-utils';

/* ------------------------------------------------------------------ blocks */

export function ParagraphElement(
  props: React.ComponentProps<typeof EditorElement>
) {
  return <EditorElement {...props} className="demo-p" />;
}

export function HeadingElement(
  props: React.ComponentProps<typeof EditorElement>
) {
  const level = (props as { element?: { level?: number } }).element?.level ?? 1;
  const Tag = `h${Math.min(6, Math.max(1, level))}` as 'h1';

  return <EditorElement {...props} as={Tag} className="demo-heading" />;
}

export function BlockquoteElement(
  props: React.ComponentProps<typeof EditorElement>
) {
  return <EditorElement {...props} as="blockquote" className="demo-quote" />;
}

export function HrElement(props: React.ComponentProps<typeof EditorElement>) {
  return (
    <EditorElement {...props}>
      <div contentEditable={false}>
        <hr className="demo-hr" />
      </div>
    </EditorElement>
  );
}

/* ------------------------------------------------------------------- marks */

export function BoldLeaf(props: React.ComponentProps<typeof EditorLeaf>) {
  return <EditorLeaf {...props} as="strong" />;
}

export function ItalicLeaf(props: React.ComponentProps<typeof EditorLeaf>) {
  return <EditorLeaf {...props} as="em" />;
}

export function UnderlineLeaf(props: React.ComponentProps<typeof EditorLeaf>) {
  return <EditorLeaf {...props} as="u" />;
}

export function StrikethroughLeaf(
  props: React.ComponentProps<typeof EditorLeaf>
) {
  return <EditorLeaf {...props} as="s" />;
}

export function CodeLeaf(props: React.ComponentProps<typeof EditorLeaf>) {
  return <EditorLeaf {...props} as="code" className="demo-code" />;
}

export function HighlightLeaf(props: React.ComponentProps<typeof EditorLeaf>) {
  return <EditorLeaf {...props} as="mark" />;
}

export function KbdLeaf(props: React.ComponentProps<typeof EditorLeaf>) {
  return <EditorLeaf {...props} as="kbd" className="demo-kbd" />;
}

export function ScriptLeaf(props: React.ComponentProps<typeof EditorLeaf>) {
  const script = (props as { leaf?: { script?: string } }).leaf?.script;

  return (
    <EditorLeaf {...props} as={script === 'sub' ? 'sub' : 'sup'} />
  );
}

/* -------------------------------------------------------------------- list */

function ListShell(
  props: React.ComponentProps<typeof EditorElement> & {
    listStyle?: string;
    listType?: string;
  }
) {
  const { children, listStyle, listType } = props;
  const element = (props as { element?: { listType?: string } }).element ?? {};
  const ordered = isOrderedList(element as never);
  const Tag = (ordered ? 'ol' : 'ul') as 'ul';

  return (
    <Tag
      className="demo-list"
      style={{ listStyleType: listStyle ?? 'disc' }}
    >
      <li className="demo-li">{children}</li>
    </Tag>
  );
}

/* ------------------------------------------------------------------- table */

export function TableElement(props: React.ComponentProps<typeof EditorElement>) {
  return (
    <EditorElement {...props} className="demo-table-wrap">
      <table className="demo-table">
        <tbody>{props.children}</tbody>
      </table>
    </EditorElement>
  );
}

export function TableRowElement(
  props: React.ComponentProps<typeof EditorElement>
) {
  return <EditorElement {...props} as="tr" />;
}

export function TableCellElement(
  props: React.ComponentProps<typeof EditorElement>
) {
  const element = (props as { element?: { header?: boolean } }).element ?? {};

  return (
    <EditorElement
      {...props}
      as={element.header ? 'th' : 'td'}
      className={cn('demo-cell', element.header && 'demo-cell-header')}
    />
  );
}

/* -------------------------------------------------------------------- link */

export function LinkElement(props: React.ComponentProps<typeof EditorElement>) {
  const element = (props as { element?: { url?: string } }).element ?? {};

  return (
    <EditorElement
      {...props}
      as="a"
      className="demo-link"
      attributes={{
        ...props.attributes,
        href: element.url ?? '#',
        rel: 'noreferrer noopener',
        target: '_blank',
      }}
    />
  );
}

/* ---------------------------------------------------------------- equation */

const renderLatex = (latex: string, displayMode: boolean) =>
  katex.renderToString(latex, {
    displayMode,
    errorColor: '#cc0000',
    fleqn: false,
    leqno: false,
    macros: { '\\f': '#1f(#2)' },
    output: 'htmlAndMathml',
    strict: 'warn',
    throwOnError: false,
    trust: false,
  });

export function EquationElement(
  props: React.ComponentProps<typeof EditorElement>
) {
  const element = (props as { element?: { latex?: string } }).element ?? {};
  const latex = element.latex ?? '';

  return (
    <EditorElement {...props} className="demo-equation">
      {latex ? (
        <span
          // KaTeX output is generated with trust disabled, from the
          // equation's own LaTeX source.
          dangerouslySetInnerHTML={{ __html: renderLatex(latex, true) }}
        />
      ) : null}
      {props.children}
    </EditorElement>
  );
}

export function InlineEquationElement(
  props: React.ComponentProps<typeof EditorElement>
) {
  const element = (props as { element?: { latex?: string } }).element ?? {};
  const latex = element.latex ?? '';

  return (
    <EditorElement {...props} className="demo-equation-inline">
      {latex ? (
        <span
          dangerouslySetInnerHTML={{ __html: renderLatex(latex, false) }}
        />
      ) : null}
      {props.children}
    </EditorElement>
  );
}

/* ------------------------------------------------------------------- kit */

export const EditorKit = [
  ParagraphPlugin.configure({ component: ParagraphElement }),
  HeadingPlugin.configure({ component: HeadingElement }),
  BlockquotePlugin.configure({ component: BlockquoteElement }),
  HorizontalRulePlugin.configure({ component: HrElement }),

  BoldPlugin.configure({ component: BoldLeaf }),
  ItalicPlugin.configure({ component: ItalicLeaf }),
  UnderlinePlugin.configure({ component: UnderlineLeaf }),
  StrikethroughPlugin.configure({ component: StrikethroughLeaf }),
  CodePlugin.configure({ component: CodeLeaf }),
  HighlightPlugin.configure({ component: HighlightLeaf }),
  KbdPlugin.configure({ component: KbdLeaf }),
  ScriptPlugin.configure({ component: ScriptLeaf }),

  ListPlugin.configure({
    inject: {
      isElement: true,
      nodeProps: {
        nodeKey: 'listType',
        query: ({ nodeProps }) => {
          const { element } = nodeProps;

          return (
            element?.listType === ListType.Bulleted && !isOrderedList(element)
          );
        },
        transformProps: ({ element, props }) => ({
          ...props,
          role: 'listitem',
          style: {
            ...props.style,
            display: 'list-item',
            listStyleType: element?.listStyle,
          },
        }),
      },
    },
    slots: {
      wrapNodeChildren: (props) => {
        const element = (props as { element?: { listType?: string } })
          .element ?? {};

        if (!element.listType || element.listType === ListType.Bulleted) {
          return undefined;
        }

        return function ListWrapper(innerProps) {
          return (
            <ListShell
              {...innerProps}
              listStyle={element.listStyle}
              listType={element.listType}
            />
          );
        };
      },
    },
    targetPlugins: [
      PLUGINS.heading,
      PLUGINS.paragraph,
      PLUGINS.blockquote,
      PLUGINS.codeBlock,
    ],
  }),

  TablePlugin.configure({ component: TableElement }),
  TableRowPlugin.configure({ component: TableRowElement }),
  TableCellPlugin.configure({ component: TableCellElement }),

  LinkPlugin.configure({ component: LinkElement }),

  EquationPlugin.configure({ component: EquationElement }),
  InlineEquationPlugin.configure({ component: InlineEquationElement }),

  BaseTextAlignPlugin.configure({
    targetPlugins: [PLUGINS.heading, PLUGINS.paragraph],
  }),
  BaseLineHeightPlugin.configure({
    targetPlugins: [PLUGINS.heading, PLUGINS.paragraph],
  }),
  BaseFontColorPlugin,
  BaseFontBackgroundColorPlugin,
  BaseFontFamilyPlugin,
  BaseFontSizePlugin,
  BaseTextIndentPlugin,

  TrailingBlockPlugin,
] as const;
