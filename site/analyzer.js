(() => {
  function findings(code) {
    const rows = [];
    const lines = code.split(/\r?\n/);
    lines.forEach((line, i) => {
      const n = i + 1;
      if (/\b(eval|exec)\s*\(/i.test(line)) rows.push({ n, rule: 'تنفيذ ديناميكي', text: 'قد ينفذ كودًا غير موثوق.', suggestion: 'استخدمي ast.literal_eval للحالات الحرفية أو أعيدي تصميم التدفق.' });
      if (/\b(api[_-]?key|secret|token)\s*[=:]\s*[\'\"][A-Za-z0-9_\-/+=]{12,}/i.test(line)) rows.push({ n, rule: 'سر محتمل', text: 'قد يحتوي السطر على مفتاح أو سر.', suggestion: 'انقلي السر إلى متغيرات البيئة أو GitHub Secrets.' });
      if (/TODO|FIXME/.test(line)) rows.push({ n, rule: 'مهمة مؤجلة', text: 'يوجد تعليق يحتاج متابعة.', suggestion: 'حوّليه إلى Issue أو عالجيه.' });
      if (line.length > 120) rows.push({ n, rule: 'سطر طويل', text: 'السطر أطول من 120 حرفًا.', suggestion: 'قسّميه إلى أسطر أو دالة مساعدة.' });
    });
    return rows;
  }

  function summarize(code) {
    const lines = code.split(/\r?\n/);
    const imports = lines.filter(line => /^\s*(import|from)\s+/.test(line)).length;
    const functionDetails = [...code.matchAll(/^\s*def\s+([A-Za-z_]\w*)\s*\(([^)]*)\)/gm)].map(match => ({ name: match[1], signature: `${match[1]}(${match[2]})`, explanation: `دالة باسم ${match[1]} تستقبل ${match[2].trim() ? 'المعاملات المحددة' : 'لا معاملات'}.` }));
    const functions = functionDetails.map(item => item.name);
    const classes = [...code.matchAll(/^\s*class\s+([A-Za-z_]\w*)/gm)].map(match => match[1]);
    return { language: 'Python (تقدير واجهة محلية)', lines: lines.length, imports, functions, functionDetails, classes, findings: findings(code) };
  }

  function maskPython(code) {
    let out = '', quote = null, triple = false, escaped = false;
    for (let i = 0; i < code.length; i += 1) {
      const ch = code[i], next = code.slice(i, i + 3);
      if (!quote && ch === '#') { while (i < code.length && code[i] !== '\n') { out += ' '; i += 1; } i -= 1; continue; }
      if (quote) {
        if (triple && next === quote.repeat(3)) { out += '   '; i += 2; quote = null; triple = false; escaped = false; continue; }
        if (!triple && ch === quote && !escaped) { out += ' '; quote = null; escaped = false; continue; }
        out += ch === '\n' ? '\n' : ' '; escaped = ch === '\\' && !escaped; if (ch !== '\\') escaped = false; continue;
      }
      if (ch === "'" || ch === '"') { triple = next === ch.repeat(3); quote = ch; out += triple ? '   ' : ' '; if (triple) i += 2; continue; }
      out += ch;
    }
    return out;
  }

  function repair(code) {
    let lines = code.split(/\r?\n/), changes = [], needsAst = false;
    const masked = maskPython(code).split(/\r?\n/);
    lines = lines.map((line, i) => {
      let out = line, mask = masked[i] || '';
      const reps = [[/\bxrange\b/g, 'range', 'استبدال xrange بـ range في Python 3.'], [/\braw_input\b(?=\s*\()/g, 'input', 'استبدال raw_input بـ input في Python 3.'], [/\bunicode\b(?=\s*\()/g, 'str', 'استبدال unicode بـ str في Python 3.']];
      reps.forEach(([repl, to, why]) => { let match; repl.lastIndex = 0; while ((match = repl.exec(mask)) !== null) { const next = out.slice(0, match.index) + to + out.slice(match.index + match[0].length); changes.push([i + 1, out, next, why]); out = next; mask = mask.slice(0, match.index) + ' '.repeat(match[0].length) + mask.slice(match.index + match[0].length); } });
      const evalMatch = /\beval\s*\(\s*(?:(['"])(?:\\.|(?!\1)[\s\S])*\1|[-+]?\d+(?:\.\d+)?|True|False|None)\s*\)/.exec(line);
      let safeEvalReplaced = false;
      if (evalMatch && mask.slice(evalMatch.index, evalMatch.index + 4) === 'eval') { const evalIndex = evalMatch.index; const next = out.slice(0, evalIndex) + 'ast.literal_eval' + out.slice(evalIndex + 4); changes.push([i + 1, out, next, 'استبدال eval بـ ast.literal_eval للحالات الحرفية فقط.']); out = next; needsAst = true; safeEvalReplaced = true; }
      if (!safeEvalReplaced && /\beval\s*\(/.test(mask)) changes.push([i + 1, out, out, 'لم يتم تعديل eval تلقائيًا لأن المدخل ليس literal آمنًا.']);
      if (/\bexec\s*\(/.test(mask)) changes.push([i + 1, out, out, 'لم يتم تعديل exec تلقائيًا؛ يحتاج إعادة تصميم آمنة.']);
      return out;
    });
    if (needsAst && !/^\s*import\s+ast\b/m.test(lines.join('\n'))) { lines.unshift('import ast'); changes.unshift([1, '', 'import ast', 'إضافة الاستيراد المطلوب.']); }
    const stack = [], pairs = { ')': '(', ']': '[', '}': '{' };
    for (const ch of maskPython(lines.join('\n'))) { if ('([{'.includes(ch)) stack.push(ch); else if (')]}'.includes(ch) && stack.pop() !== pairs[ch]) return { modified: code, changes: [[1, code, code, 'رُفض الإصلاح لأن البنية الناتجة تحتوي أقواسًا غير متوازنة.']] }; }
    if (stack.length) return { modified: code, changes: [[1, code, code, 'رُفض الإصلاح لأن البنية الناتجة تحتوي أقواسًا غير متوازنة.']] };
    return { modified: lines.join('\n'), changes };
  }

  function translateReport(summary) {
    const labels = { language: 'اللغة المتوقعة', lines: 'عدد الأسطر', imports: 'عدد الاستيرادات', functions: 'الدوال', classes: 'الأصناف' };
    return { ...summary, labels, note: 'هذه ترجمة قواعدية للتقرير إلى العربية وليست ترجمة ذكاء اصطناعي لفهم المعنى.' };
  }

  let pyodidePromise;
  function validatePython(code) {
    pyodidePromise ||= import('https://cdn.jsdelivr.net/pyodide/v0.26.2/full/pyodide.mjs')
      .then(module => module.loadPyodide())
      .then(pyodide => { pyodide.globals.set('source_code', code); pyodide.runPython('import ast\nast.parse(source_code)'); return { available: true, valid: true }; })
      .catch(error => ({ available: false, valid: false, error: String(error && error.message || error) }));
    return pyodidePromise;
  }

  function esc(value) { return String(value).replace(/[&<>"']/g, match => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' }[match])); }

  if (typeof window !== 'undefined') {
    const source = document.querySelector('#source');
    const result = document.querySelector('#result');
    const status = document.querySelector('#status');
    const file = document.querySelector('#file');
    const renderFindings = (items, title) => { result.innerHTML = `<strong>${title}</strong><p>${items.length ? `تم العثور على ${items.length} ملاحظة:` : 'لم نجد ملاحظات ضمن القواعد الحالية.'}</p>` + items.map(x => `<div class="change"><b>السطر ${x.n} — ${x.rule}</b><br>${x.text}<br><span class="muted">الاقتراح: ${x.suggestion}</span></div>`).join(''); };
    file.addEventListener('change', event => { const selected = event.target.files[0]; if (!selected) return; const reader = new FileReader(); reader.onload = () => { source.value = reader.result; status.textContent = `تم تحميل ${selected.name}. اضغطي شرح أو إصلاح.`; }; reader.readAsText(selected); });
    document.querySelector('#explain').onclick = () => { const summary = summarize(source.value); const functions = summary.functionDetails.length ? summary.functionDetails.map(item => `<li><code>${esc(item.signature)}</code> — ${item.explanation}</li>`).join('') : '<li>لا توجد دوال معرفة.</li>'; result.innerHTML = `<strong>شرح عربي بنيوي</strong><p>اللغة: ${summary.language}<br>عدد الأسطر: ${summary.lines}<br>عدد الاستيرادات: ${summary.imports}<br>الأصناف: ${summary.classes.length ? summary.classes.join('، ') : 'لا توجد'}</p><h3>وظائف الدوال</h3><ul>${functions}</ul><p class="muted">الشرح يحدد البنية والقاعدة وسبب الخطأ؛ لا يدّعي فهمًا دلاليًا توليديًا.</p>`; renderFindings(summary.findings, 'سبب كل ملاحظة وكيفية تجنبها'); status.textContent = 'اكتمل الشرح البنيوي المحلي.'; };
    document.querySelector('#translate').onclick = () => { const translated = translateReport(summarize(source.value)); result.innerHTML = `<strong>ترجمة التقرير</strong><p>${translated.note}</p><p>اللغة المتوقعة: ${translated.language}<br>عدد الأسطر: ${translated.lines}<br>الدوال: ${translated.functions.length ? translated.functions.join('، ') : 'لا توجد'}<br>الأصناف: ${translated.classes.length ? translated.classes.join('، ') : 'لا توجد'}</p>`; renderFindings(translated.findings, 'القواعد مترجمة إلى العربية'); status.textContent = 'اكتملت ترجمة التقرير القاعدية.'; };
    document.querySelector('#repair').onclick = async () => { const code = source.value; if (!code.trim()) { status.textContent = 'الصقي الكود أولًا.'; return; } status.textContent = 'جارٍ التحقق من صلاحية الكود المعدل عبر محلّل Python...'; const repaired = repair(code); const validation = await validatePython(repaired.modified); if (!validation.available || !validation.valid) { result.innerHTML = `<strong>لم يتم عرض الإصلاح كنسخة صالحة</strong><p class="note">${validation.available ? 'فشل فحص صياغة Python؛ تم الاحتفاظ بالكود الأصلي.' : 'تعذر تحميل محلّل Python داخل المتصفح؛ لم نعرض التعديل على أنه صالح.'}</p><pre class="status">${esc(code)}</pre><p class="muted">التفاصيل: ${esc(validation.error || 'خطأ صياغة')}</p>`; status.textContent = 'تم رفض عرض الإصلاح حتى يمر فحص Python.'; return; } result.innerHTML = `<strong>الكود الأصلي</strong><pre class="status">${esc(code)}</pre><strong>الكود المعدل — اجتاز فحص Python</strong><pre class="status">${esc(repaired.modified)}</pre><h3>سبب كل تغيير (${repaired.changes.length})</h3>` + repaired.changes.map(change => `<div class="change"><b>السطر ${change[0]}</b><span class="muted"> — ${esc(change[3])}</span><code>قبل: ${esc(change[1])}\nبعد: ${esc(change[2])}</code></div>`).join(''); status.textContent = repaired.changes.length ? 'تم التحقق من الإصلاح عبر Python ويمكن مراجعته.' : 'الكود صالح ولم توجد إصلاحات آلية.'; };
  }

  if (typeof module !== 'undefined') module.exports = { findings, summarize, repair, translateReport };
})();
