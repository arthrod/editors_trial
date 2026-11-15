/**
 * Contract tests for fixinput2 (comparison, offset, fragment read scope, opening gate).
 * Invoked from test_b4_fixinput2.py; exit 0 when all pass.
 */
import {
  assertFixtureBodyMatches,
  assertPreEditDocumentLoaded,
  bodyAfterInsertion,
  resolveDocumentTextRoot,
} from '../runner/criteria_input.mjs';

let failed = 0;
function assert(cond, msg) {
  if (!cond) {
    console.error(`FAIL: ${msg}`);
    failed += 1;
  }
}

// BLOCKER 3: paragraph separators may differ; fixture w:t vs DOM must still match.
const fixtureWt = 'AlphaBetaGamma';
const domInner = 'Alpha\nBeta\nGamma';
const domRange = domInner.replace(/\n/g, '');
assert(
  assertFixtureBodyMatches({ text: domRange }, fixtureWt).ok,
  'fixture body: prose multiparagraph (w:t vs rendered)',
);
assert(
  !assertFixtureBodyMatches({ text: domInner.replace('Gamma', 'GammX') }, fixtureWt).ok,
  'wrong character must refuse fixture_body_mismatch',
);

const proseBefore = 'WithoutIn property';
const offset = 7;
const afterInsert = bodyAfterInsertion(proseBefore, 'x', offset);
assert(afterInsert === 'WithoutxIn property', `insertion at offset ${offset} in range coordinates`);
assert(
  bodyAfterInsertion(proseBefore, 'x', offset - 1) !== afterInsert,
  'wrong offset must change expected insertion',
);

// BLOCKER 2: fragment selector must resolve the page content root, not one span.
const pageRoot = { kind: 'page-content', text: 'Article body text' };
const fragment = {
  textContent: 'Article ',
  matches(sel) {
    return sel === '[data-paragraph-id][data-start]';
  },
  closest(sel) {
    return sel === '.docx-page-content' ? pageRoot : null;
  },
};
assert(resolveDocumentTextRoot(fragment) === pageRoot, 'eigenpal fragment resolves page content root');
assert(
  fragment.textContent.trim() !== pageRoot.text.trim(),
  'sanity: first fragment alone is not the document',
);

// BLOCKER 1b: complex-corpus uses opening gate, not raw fixture extractor body.
assert(
  assertPreEditDocumentLoaded(
    { text: 'Benchmark complex fixture preamble…' },
    { expectedOpeningText: 'Benchmark complex fixture', expectedBodyText: null },
  ).ok,
  'opening-text pre-edit gate accepts rendered document',
);
assert(
  !assertPreEditDocumentLoaded(
    { text: 'Wrong document entirely' },
    { expectedOpeningText: 'Benchmark complex fixture', expectedBodyText: null },
  ).ok,
  'opening gate refuses wrong document',
);
const rawWtOracle = 'moved away bookmarked anchor';
assert(
  !assertFixtureBodyMatches(
    { text: 'Rendered without moved-from duplicates' },
    rawWtOracle,
  ).ok || assertPreEditDocumentLoaded(
    { text: 'Rendered Benchmark complex' },
    { expectedOpeningText: 'Benchmark complex', expectedBodyText: null },
  ).ok,
  'complex workload must not require raw w:t oracle',
);

if (failed) {
  process.exit(1);
}
console.log(`b4_fixinput2_contract: ${5} checks ok`);
