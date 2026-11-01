/**
 * Bun loader plugin: resolve the www app's `@/` import alias so Plate's own
 * static presentation kit can be used from a headless harness.
 *
 * The kit lives in apps/www/src/registry/components/editor/*-static.tsx and is
 * the single biggest fidelity lever in the DOCX export: without a
 * `presentation` kit, exportDocx falls back to each plugin's own component
 * and the Base (non-React) plugins carry none, so tables, images and lists
 * degrade to plain divs.
 *
 * Three aliases are needed:
 *   @/registry/components/editor/X  -> the file in the www app
 *   @/lib/utils                    -> cn() = twMerge(clsx(...))
 *   @/components/ui/button         -> a plain <button>; the real one is a
 *                                     shadcn component that needs tailwind
 *                                     and cva, and only toc-static.tsx uses it
 */
import { plugin } from 'bun';
import { dirname, resolve } from 'node:path';

const WWW = '/Users/arthrod/temp/T/editors_trial/repos/plate/apps/www/src';
// The www kit imports these. They are pinned in apps/www/package.json and are
// not present in that checkout's node_modules. The harness installs the same
// versions and this loader hands markdown.tsx those copies.
const REMARK = '/Users/arthrod/temp/T/editors_trial/harness/plate/node_modules';

const SHIMS: Record<string, string> = {
  '@/lib/utils': `
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';
export function cn(...inputs) { return twMerge(clsx(inputs)); }
export type ClassValue = any;
`,
  '@/components/ui/button': `
import * as React from 'react';
export const Button = React.forwardRef(function Button(props, ref) {
  const { children, variant, size, ...rest } = props;
  return React.createElement('button', { ref, ...rest }, children);
});
export const buttonVariants = {};
`,
};

plugin({
  name: 'plate-www-aliases',
  setup(build) {
    build.onResolve({ filter: /^remark-(emoji|gfm|math)$/ }, (args) => {
      return { path: resolve(REMARK, args.path, 'index.js') };
    });

    build.onResolve({ filter: /^@\// }, (args) => {
      if (SHIMS[args.path]) {
        return { path: args.path, namespace: 'shim' };
      }
      if (args.path.startsWith('@/registry/components/editor/')) {
        const base = args.path.slice('@/registry/components/editor/'.length);
        return { path: resolve(WWW, 'registry/components/editor', base) };
      }
      if (args.path.startsWith('@/')) {
        return { path: resolve(WWW, args.path.slice(2)) };
      }
      return undefined;
    });

    build.onLoad({ filter: /.*/, namespace: 'shim' }, (args) => {
      return { contents: SHIMS[args.path], loader: 'ts' };
    });

    // the www kit's own relative imports can be extensionless .tsx
    build.onResolve({ filter: /^\.\.?\/.*$/ }, (args) => {
      if (args.path.startsWith('.')) return undefined;
      return undefined;
    });
  },
});
