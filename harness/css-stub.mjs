// Node module-resolution hook: stub out .css/.scss imports.
// GenOffice's @genoffice/ui barrel pulls in './ai-skills.css', which tsx cannot parse
// outside a bundler. This hook resolves any .css specifier to an empty JS module
// without touching the repository.
import { registerHooks } from 'node:module';
import { pathToFileURL } from 'node:url';

const EMPTY = pathToFileURL('/Users/arthrod/temp/T/editors_trial/harness/empty-module.mjs').href;

registerHooks({
  resolve(specifier, context, nextResolve) {
    if (specifier.endsWith('.css') || specifier.endsWith('.scss') || specifier.endsWith('.sass')) {
      return { url: EMPTY, shortCircuit: true, format: 'module' };
    }
    return nextResolve(specifier, context);
  },
});
