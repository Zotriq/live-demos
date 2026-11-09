// Run one n8n Code node's JavaScript outside n8n, with the globals it uses ($input, $, $now).
// stdin: {"code": "...", "input": [...], "nodes": {"Node name": [...]}, "today": "YYYY-MM-DD"}
// stdout: the node's output items (json only)
const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;
let raw = '';
for await (const chunk of process.stdin) raw += chunk;
const { code, input = [], nodes = {}, today } = JSON.parse(raw);
const wrap = (json) => ({ json });
const items = input.map(wrap);
const $input = { first: () => items[0], all: () => items };
const $ = (name) => {
  if (!(name in nodes)) throw new Error(`node "${name}" has no data`);
  const its = nodes[name].map(wrap);
  return { first: () => its[0], all: () => its };
};
const $now = { toISODate: () => today, toISO: () => `${today}T10:00:00.000Z` };
try {
  const out = await new AsyncFunction('$input', '$', '$now', code)($input, $, $now);
  process.stdout.write(JSON.stringify(out.map((i) => i.json)));
} catch (e) {
  process.stderr.write(e.message);
  process.exit(1);
}
