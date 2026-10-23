const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const { test } = require('node:test');
const source = fs.readFileSync(__dirname + '/index.html', 'utf8').match(/<script>([\s\S]*?)<\/script>/)[1];

function dashboard(raw) {
  const elements = new Map();
  const element = id => {
    if (!elements.has(id)) elements.set(id, { innerHTML: '', textContent: '', title: '', classList: { toggle(name, state) { this[name] = state; } } });
    return elements.get(id);
  };
  const context = vm.createContext({ Intl, Date, console, document: { querySelector: element },
    fetch: async () => ({ ok: true, text: async () => raw }), setInterval() {} });
  vm.runInContext(source, context);
  return { context, element };
}

test('age, stale boundary and Beijing timestamps are independent of device timezone', () => {
  const { context } = dashboard('');
  const evaluate = expression => vm.runInContext(expression, context);
  assert.equal(evaluate('timestampMs("2026-10-15T06:06:31.164224")'), Date.parse('2026-10-15T06:06:31.164+08:00'));
  assert.equal(evaluate('time("2026-10-14T22:06:31Z")'), '2026-10-15 06:06:31');
  assert.equal(evaluate('dataAge("2026-10-15T06:06:31", timestampMs("2026-10-23T09:06:31")).text'), '(- 8 day 3 hour)');
  assert.equal(evaluate('dataAge("2026-10-15T06:00:00", timestampMs("2026-10-15T17:59:59")).stale'), false);
  assert.equal(evaluate('dataAge("2026-10-15T06:00:00", timestampMs("2026-10-15T18:00:00")).stale'), true);
  assert.equal(evaluate('dataAge("2099-01-01T00:00:00").text'), '(时间异常)');
});

test('old records show red age inline; invalid records do not replace valid electricity', async () => {
  const { element } = dashboard([
    JSON.stringify({ timestamp: '2026-10-15T06:06:31', remaining_electricity: 147.74 }),
    JSON.stringify({ timestamp: 'invalid', remaining_electricity: 999 }),
    JSON.stringify({ timestamp: '2099-01-01T00:00:00', remaining_electricity: null }),
    'malformed JSON'
  ].join('\n'));
  await new Promise(resolve => setImmediate(resolve));
  assert.match(element('#content').innerHTML, /147\.74/);
  assert.match(element('#content').innerHTML, /2026-10-15 06:06:31 <span id=data-age/);
  assert.equal(element('#data-age').classList.stale, true);
  assert.match(element('#electricity-label').textContent, /数据已过期/);
});
