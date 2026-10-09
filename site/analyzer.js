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
    const functions = [...code.matchAll(/^\s*def\s+([A-Za-z_]\w*)/gm)].map(match => match[1]);
    const classes = [...code.matchAll(/^\s*class\s+([A-Za-z_]\w*)/gm)].map(match => match[1]);
    return { language: 'Python (تقدير واجهة محلية)', lines: lines.length, imports, functions, classes, findings: findings(code) };
  }

  function repair(code) {
    let lines = code.split(/\r?\n/), changes = [], needsAst = false;
    lines = lines.map((line, i) => {
      let out = line;
      const reps = [[/\bxrange\b/g, 'range', 'استبدال xrange بـ range في Python 3.'], [/\braw_input\s*\(/g, 'input(', 'استبدال raw_input بـ input في Python 3.'], [/\bunicode\s*\(/g, 'str(', 'استبدال unicode بـ str في Python 3.']];
      reps.forEach(([repl, to, why]) => { const next = out.replace(repl, to); if (next !== out) { changes.push([i + 1, out, next, why]); out = next; } });
      if (/\beval\s*\(/.test(out)) { const next = out.replace(/\beval\s*\(/, 'ast.literal_eval('); changes.push([i + 1, out, next, 'استبدال eval بـ ast.literal_eval لتجنب تنفيذ كود غير موثوق.']); out = next; needsAst = true; }
      if (/\bexec\s*\(/.test(out)) changes.push([i + 1, out, out, 'لم يتم تعديل exec تلقائيًا؛ يحتاج إعادة تصميم آمنة.']);
      return out;
    });
    if (needsAst && !/^\s*import\s+ast\b/m.test(lines.join('\n'))) { lines.unshift('import ast'); changes.unshift([1, '', 'import ast', 'إضافة الاستيراد المطلوب.']); }
    return { modified: lines.join('\n'), changes };
  }

  function translateReport(summary) {
    const labels = { language: 'اللغة المتوقعة', lines: 'عدد الأسطر', imports: 'عدد الاستيرادات', functions: 'الدوال', classes: 'الأصناف' };
    return { ...summary, labels, note: 'هذه ترجمة قواعدية للتقرير إلى العربية وليست ترجمة ذكاء اصطناعي لفهم المعنى.' };
  }

  function esc(value) { return String(value).replace(/[&<>"']/g, match => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' }[match])); }

  if (typeof window !== 'undefined') {
    const source = document.querySelector('#source');
    const result = document.querySelector('#result');
    const status = document.querySelector('#status');
    const file = document.querySelector('#file');
    const renderFindings = (items, title) => { result.innerHTML = `<strong>${title}</strong><p>${items.length ? `تم العثور على ${items.length} ملاحظة:` : 'لم نجد ملاحظات ضمن القواعد الحالية.'}</p>` + items.map(x => `<div class="change"><b>السطر ${x.n} — ${x.rule}</b><br>${x.text}<br><span class="muted">الاقتراح: ${x.suggestion}</span></div>`).join(''); };
    file.addEventListener('change', event => { const selected = event.target.files[0]; if (!selected) return; const reader = new FileReader(); reader.onload = () => { source.value = reader.result; status.textContent = `تم تحميل ${selected.name}. اضغطي شرح أو إصلاح.`; }; reader.readAsText(selected); });
    document.querySelector('#explain').onclick = () => { const summary = summarize(source.value); result.innerHTML = `<strong>شرح بنيوي للكود</strong><p>اللغة: ${summary.language}<br>عدد الأسطر: ${summary.lines}<br>الاستيرادات: ${summary.imports}<br>الدوال: ${summary.functions.length ? summary.functions.join('، ') : 'لا توجد'}<br>الأصناف: ${summary.classes.length ? summary.classes.join('، ') : 'لا توجد'}</p>`; renderFindings(summary.findings, 'ملاحظات القواعد'); status.textContent = 'اكتمل الشرح البنيوي المحلي.'; };
    document.querySelector('#translate').onclick = () => { const translated = translateReport(summarize(source.value)); result.innerHTML = `<strong>ترجمة التقرير</strong><p>${translated.note}</p><p>اللغة المتوقعة: ${translated.language}<br>عدد الأسطر: ${translated.lines}<br>الدوال: ${translated.functions.length ? translated.functions.join('، ') : 'لا توجد'}<br>الأصناف: ${translated.classes.length ? translated.classes.join('، ') : 'لا توجد'}</p>`; renderFindings(translated.findings, 'القواعد مترجمة إلى العربية'); status.textContent = 'اكتملت ترجمة التقرير القاعدية.'; };
    document.querySelector('#repair').onclick = () => { const code = source.value; if (!code.trim()) { status.textContent = 'الصقي الكود أولًا.'; return; } const repaired = repair(code); result.innerHTML = `<strong>الكود الأصلي</strong><pre class="status">${esc(code)}</pre><strong>الكود المعدل</strong><pre class="status">${esc(repaired.modified)}</pre><h3>سبب كل تغيير (${repaired.changes.length})</h3>` + repaired.changes.map(change => `<div class="change"><b>السطر ${change[0]}</b><span class="muted"> — ${esc(change[3])}</span><code>قبل: ${esc(change[1])}\nبعد: ${esc(change[2])}</code></div>`).join(''); status.textContent = repaired.changes.length ? 'تم إنشاء إصلاحات قابلة للمراجعة.' : 'لم توجد إصلاحات آلية.'; };
  }

  if (typeof module !== 'undefined') module.exports = { findings, summarize, repair, translateReport };
})();
