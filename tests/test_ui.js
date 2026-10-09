const assert = require('assert');
const fs = require('fs');
const { findings, summarize, repair, translateReport } = require('../site/analyzer.js');

const html = fs.readFileSync('site/index.html', 'utf8');
assert.ok(html.includes('id="source"'));
assert.ok(html.includes('id="file"'));
assert.ok(html.includes('id="explain"'));
assert.ok(html.includes('id="translate"'));
assert.ok(html.includes('id="repair"'));
assert.ok(html.includes('src="analyzer.js"'));

const source = "import os\nvalue = xrange(3)\nresult = eval(\"'ok'\")\n";
const summary = summarize(source);
assert.equal(summary.imports, 1);
assert.deepEqual(summary.functions, []);
assert.ok(summary.findings.some(item => item.rule === 'تنفيذ ديناميكي'));

const repaired = repair(source);
assert.ok(repaired.modified.includes('import ast'));
assert.ok(repaired.modified.includes('range(3)'));
assert.ok(repaired.modified.includes('ast.literal_eval'));
assert.ok(repaired.changes.every(change => change.length === 4));

const translated = translateReport(summary);
assert.ok(translated.note.includes('ليست ترجمة ذكاء اصطناعي'));
assert.ok(findings('print("ok")').length === 0);
console.log('ui logic tests passed');
