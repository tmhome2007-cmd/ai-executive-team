import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import ts from 'typescript';
import Module from 'node:module';
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const filename = path.resolve(__dirname, '../app/lib/review-summary.ts');
const compiled = ts.transpileModule(fs.readFileSync(filename, 'utf8'), {compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
const m = new Module(filename); m._compile(compiled, filename);
const {reviewSummary} = m.exports;
const cases = [
 ['empty', '', {findings:[],unknowns:[],next:[]}],
 ['supplied evidence', '**Findings**\n- Source #4 reports four checks passed.\n**Unknowns**\n- Cause unknown.\n**Next action**\n- Read the failed check log.', {findings:['Source #4 reports four checks passed.'],unknowns:['Cause unknown.'],next:['Read the failed check log.']}],
 ['conflict', '# Supported findings\nSource #1 says four passed; source #2 says three.\n# Unresolved questions\nSources conflict.\n# Next action\nResolve source mismatch before execution.', {findings:['Source #1 says four passed; source #2 says three.'],unknowns:['Sources conflict.'],next:['Resolve source mismatch before execution.']}],
 ['missing prerequisites', '**Proposed next test**\nPrerequisites: Original due time missing.\nSteps: Do not run until due time is supplied.', {findings:[],unknowns:['Original due time missing.'],next:['Do not run until due time is supplied.']}],
 ['legacy', 'A long unstructured answer without section headings.', {findings:[],unknowns:[],next:[]}],
];
for (const [name,text,expected] of cases) {
 const result = reviewSummary(text);
 for (const key of ['findings','unknowns','next']) assert.deepEqual(result[key],expected[key],name);
}
assert.deepEqual(reviewSummary('**constructor**\nBad bucket\n**__proto__**\nBad bucket').findings,[]);
assert.ok(reviewSummary('The owner approved execution.').warnings.some(x=>x.includes('cannot establish')));
const unsafe = '**Findings**\n<script>alert(1)</script>';
assert.equal(reviewSummary(unsafe).findings[0],'<script>alert(1)</script>'); // Renderer must keep this as text.
assert.equal(reviewSummary('**Findings**\n'+Array(10).fill('A'.repeat(400)).join('\n')).findings[0].length,291);
assert.ok(reviewSummary('**Next action**\n- Read records.\n- Ask owner.\n- Check sources.\n- Blocked until original conditions supplied.').warnings.some(x=>x.includes('Blocked')));
console.log('PASS: empty, supplied, conflicting, missing-prerequisite, legacy, consent, text-safety and bounded-excerpt cases');

const historical = reviewSummary('**Next action**\nPractice candidate only: Documentation service. Owner selection required.\n**Next research step**\nFind recent buyer requests.');
assert.deepEqual(historical.next, ['Documentation service. Owner selection required.', 'Find recent buyer requests.']);
const proposalFile = path.resolve(__dirname, '../app/lib/business-proposals.ts');
const proposalModule = new Module(proposalFile);
proposalModule._compile(ts.transpileModule(fs.readFileSync(proposalFile, 'utf8'), {compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText, proposalFile);
const { businessProposals } = proposalModule.exports;
const urls = ['https://example.org/public-page', 'https://docs.example.com/x', 'https://public.example/x', 'https://github.com/orgs/community/discussions'];
const suggestions = businessProposals(urls.map(url => 'Proposed public source (not read): '+url+' — Unknown contents').join('\n'));
assert.equal(suggestions.withheld, 3);
assert.equal(suggestions.sources.length, 1);
console.log('PASS: historical next actions and placeholder source controls');
