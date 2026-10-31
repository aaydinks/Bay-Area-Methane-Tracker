// Number and date formatting. Missing values show an en dash, never a zero.

export const MISSING = '–';

export function num(x: number | null | undefined, sig = 3): string {
  if (x === null || x === undefined || Number.isNaN(x)) return MISSING;
  if (x === 0) return '0';
  const digits = Math.max(0, sig - 1 - Math.floor(Math.log10(Math.abs(x))));
  return x.toLocaleString('en-US', { maximumFractionDigits: Math.min(digits, 6), minimumFractionDigits: 0 });
}

export function pct(x: number | null | undefined, digits = 0): string {
  if (x === null || x === undefined || Number.isNaN(x)) return MISSING;
  const sign = x > 0 ? '+' : '';
  return `${sign}${x.toFixed(digits)}%`;
}

export function range(lo: number | null | undefined, hi: number | null | undefined, unit = ''): string {
  if (lo === null || lo === undefined || hi === null || hi === undefined) return MISSING;
  const u = unit ? ` ${unit}` : '';
  return `${num(lo)} to ${num(hi)}${u}`;
}

export function date(iso: string | null | undefined): string {
  if (!iso) return MISSING;
  const d = new Date(iso.length === 10 ? `${iso}T00:00:00Z` : iso);
  if (Number.isNaN(d.getTime())) return MISSING;
  return d.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric', timeZone: 'UTC' });
}

export function month(iso: string | null | undefined): string {
  if (!iso) return MISSING;
  const d = new Date(`${iso.slice(0, 7)}-01T00:00:00Z`);
  return d.toLocaleDateString('en-US', { year: 'numeric', month: 'short', timeZone: 'UTC' });
}

export function shortSha(sha: string | null | undefined): string {
  return sha ? sha.slice(0, 7) : MISSING;
}
