// Time steps for the map's plume timeline: every month (or quarter) from the first plume to the
// last, including the empty ones, so playing through them never skips time.

export type StepKind = 'month' | 'quarter';

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

/** "2024-03" from an ISO date or time; empty when the input has no month. */
export function monthOf(iso: string): string {
  return /^\d{4}-\d{2}/.test(iso) ? iso.slice(0, 7) : '';
}

/** "2024-Q1" for a month key such as "2024-03". */
export function quarterOf(month: string): string {
  const [y, m] = month.split('-').map(Number);
  return `${y}-Q${Math.floor((m - 1) / 3) + 1}`;
}

/** Every month key from `first` to `last`, both included. */
export function monthsBetween(first: string, last: string): string[] {
  const out: string[] = [];
  let [y, m] = first.split('-').map(Number);
  const [ly, lm] = last.split('-').map(Number);
  while (y < ly || (y === ly && m <= lm)) {
    out.push(`${y}-${String(m).padStart(2, '0')}`);
    m += 1;
    if (m > 12) {
      m = 1;
      y += 1;
    }
  }
  return out;
}

/** The ordered step keys for a set of plume dates. */
export function stepsFor(dates: string[], kind: StepKind): string[] {
  const months = dates.map(monthOf).filter(Boolean).sort();
  if (!months.length) return [];
  const all = monthsBetween(months[0], months[months.length - 1]);
  return kind === 'month' ? all : [...new Set(all.map(quarterOf))];
}

/** The step a plume date falls in. */
export function stepOf(iso: string, kind: StepKind): string {
  const m = monthOf(iso);
  return kind === 'month' || !m ? m : quarterOf(m);
}

/** "March 2024" for a month step; "Jan to Mar 2024" for a quarter step. */
export function stepLabel(key: string, kind: StepKind): string {
  if (kind === 'month') {
    const [y, m] = key.split('-').map(Number);
    return new Date(Date.UTC(y, m - 1, 1)).toLocaleDateString('en-US', { month: 'long', year: 'numeric', timeZone: 'UTC' });
  }
  const [y, q] = key.split('-Q').map(Number);
  return `${MONTHS[(q - 1) * 3]} to ${MONTHS[(q - 1) * 3 + 2]} ${y}`;
}

/** "Mar 2023" for a month key, for the span shown with "All dates". */
export function shortMonth(key: string): string {
  const [y, m] = key.split('-').map(Number);
  return `${MONTHS[m - 1]} ${y}`;
}

/** The first month a step covers, used to keep the reader's place when the step size changes. */
export function firstMonthOf(key: string, kind: StepKind): string {
  if (kind === 'month') return key;
  const [y, q] = key.split('-Q').map(Number);
  return `${y}-${String((q - 1) * 3 + 1).padStart(2, '0')}`;
}
