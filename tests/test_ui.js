const assert = require('assert');
const fs = require('fs');
const { findings, summarize, repair, translateReport, detectLanguage, validatePython } = require('../site/analyzer.js');
const contract = JSON.parse(fs.readFileSync('tests/repair_contract.json', 'utf8'));

const html = fs.readFileSync('site/index.html', 'utf8');
assert.ok(html.includes('id="source"'));
assert.ok(html.includes('id="file"'));
assert.ok(html.includes('id="explain"'));
assert.ok(html.includes('id="translate"'));
assert.ok(html.includes('id="repair"'));
assert.ok(/src="analyzer\.js(?:\?[^\"]*)?"/.test(html));
assert.ok(html.includes('.java'));
assert.ok(html.includes('لا يوجد رابط دفع آلي مفعّل حاليًا'));
assert.ok(html.includes('mailto:reemsaif1911@gmail.com'));
assert.ok(html.includes('تركيب مستودع'));

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
assert.equal(detectLanguage('const value = 1;', 'sample.js').name, 'JavaScript');
assert.equal(detectLanguage('public class Demo {}', 'Demo.java').name, 'Java');
assert.equal(detectLanguage('#include <iostream>', 'main.cpp').name, 'C++');
assert.equal(summarize('const value = 1;', 'sample.js').repairSupported, false);
for (const testCase of contract) {
  const result = repair(testCase.source);
  const output = result.modified;
  for (const expected of testCase.must_include) assert.ok(output.includes(expected), testCase.name);
  for (const preserved of testCase.must_preserve) assert.ok(output.includes(preserved), testCase.name);
  if (testCase.name === 'comments-and-strings') assert.equal(result.changes.filter(change => change[3].includes('لم يتم تعديل eval')).length, 0);
}
const invalid = repair('value = (1\n');
assert.equal(invalid.modified, 'value = (1\n');
assert.ok(invalid.changes[0][3].includes('أقواس'));
const parsedCodes = [];
const fakeRuntime = () => Promise.resolve({
  globals: { set: (key, value) => { parsedCodes.push(value); } },
  runPython: () => { if (parsedCodes.at(-1).includes('broken(:')) throw new Error('invalid syntax'); }
});
Promise.all([validatePython('value = 1\n', fakeRuntime), validatePython('def broken(:\n', fakeRuntime)]).then(results => {
  assert.equal(results[0].valid, true);
  assert.equal(results[1].valid, false);
  assert.deepEqual(parsedCodes, ['value = 1\n', 'def broken(:\n']);
  console.log('ui logic tests passed');
}).catch(error => { console.error(error); process.exitCode = 1; });
