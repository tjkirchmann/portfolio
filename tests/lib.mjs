// Tiny assertion log shared by the self-test files.
export const results = [];
export function check(id, name, ok, detail = '') {
  results.push({ id, name, ok: !!ok, detail });
  console.log(`${ok ? 'PASS' : 'FAIL'}  [${id}] ${name}${detail ? `  (${detail})` : ''}`);
  return !!ok;
}
export function skip(id, name, why) {
  results.push({ id, name, ok: true, skipped: true, detail: why });
  console.log(`SKIP  [${id}] ${name}  (${why})`);
}
export const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
