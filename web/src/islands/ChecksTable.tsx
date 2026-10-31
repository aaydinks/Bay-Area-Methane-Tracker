import { useMemo, useState } from 'react';

export interface CheckRow {
  id: string;
  date: string; // ISO date
  dateLabel: string;
  dateConfidence: string;
  site: string;
  siteHref: string;
  typeLabel: string;
  typeIcon: string;
  repairKind: string | null;
  colour: string; // red, orange, yellow, green, grey
  badge: string; // the result label, or "Not yet tested" / "Result held back"
  call: string | null;
  changeMed: number | null;
  changeLo: number | null;
  changeHi: number | null;
  deMed: number | null;
  deLo: number | null;
  deHi: number | null;
  evidence: string | null;
  pDecrease: number | null;
  size: string | null;
  nBefore: number | null;
  nAfter: number | null;
  mdePct: number | null;
  sourceTitle: string;
  sourceUrl: string | null;
  sourcePage: string | null;
  description: string;
  plainReading: string | null;
}

interface Props {
  rows: CheckRow[];
}

const ICONS: Record<string, string> = {
  red: 'M8 2 15 14H1z',
  orange: 'M8 1l7 7-7 7-7-7z',
  yellow: 'M8 2a6 6 0 1 1 0 12A6 6 0 0 1 8 2z',
  green: 'M1 3h14L8 14z',
  grey: 'M8 2.5a5.5 5.5 0 1 1 0 11 5.5 5.5 0 0 1 0-11zm0 2a3.5 3.5 0 1 0 0 7 3.5 3.5 0 0 0 0-7z',
};
const COLOUR_ORDER: Record<string, number> = { red: 0, orange: 1, yellow: 2, green: 3, grey: 4 };
const COLOUR_LABEL: Record<string, string> = {
  red: 'Severe increase, strong evidence',
  orange: 'Moderate increase, strong evidence',
  yellow: 'Increase, small or uncertain',
  green: 'No increase indicated',
  grey: 'Not enough data or not tested',
};

type SortKey = 'date' | 'site' | 'type' | 'result' | 'change' | 'evidence' | 'passes' | 'mde';

const pct = (x: number | null) => (x == null ? '–' : `${x > 0 ? '+' : ''}${x.toFixed(0)}%`);
const num = (x: number | null) => (x == null ? '–' : x.toLocaleString('en-US', { maximumSignificantDigits: 3 }));

function Badge({ colour, label }: { colour: string; label: string }) {
  return (
    <span className={`badge ${colour}`}>
      <svg viewBox="0 0 16 16" aria-hidden="true" focusable="false" fill="currentColor"><path d={ICONS[colour] ?? ICONS.grey} /></svg>
      {label}
    </span>
  );
}

function Details({ r }: { r: CheckRow }) {
  return (
    <>
      {r.plainReading && <p className="reading">{r.plainReading}</p>}
      <dl className="facts">
        <dt>Record</dt>
        <dd>{r.typeLabel}{r.repairKind ? ` (${r.repairKind})` : ''}, dated {r.dateLabel} ({r.dateConfidence}).</dd>
        <dt>What it says</dt>
        <dd>{r.description}</dd>
        {r.changeMed != null && (
          <>
            <dt>Change</dt>
            <dd>{pct(r.changeMed)} (90% range {pct(r.changeLo)} to {pct(r.changeHi)}); in tonnes a year: {num(r.deMed)} ({num(r.deLo)} to {num(r.deHi)}), where a positive figure is a reduction.</dd>
          </>
        )}
        <dt>Evidence</dt>
        <dd>{r.evidence ?? '–'}{r.pDecrease != null ? `, probability of a decrease ${r.pDecrease.toFixed(2)}` : ''}{r.size ? `; size: ${r.size}` : ''}</dd>
        <dt>Passes before / after</dt>
        <dd>{r.nBefore == null ? '–' : `${r.nBefore} / ${r.nAfter}`}</dd>
        <dt>Smallest drop the test could see</dt>
        <dd>{r.mdePct != null ? `${r.mdePct.toFixed(0)}%` : r.call ? 'none of the tested drops' : '–'}</dd>
        <dt>Source</dt>
        <dd>
          {r.sourceUrl ? <a href={r.sourceUrl}><span data-wording="source-title">{r.sourceTitle}</span></a> : <span data-wording="source-title">{r.sourceTitle}</span>}
          {r.sourcePage ? ` (p. ${r.sourcePage})` : ''}
        </dd>
      </dl>
    </>
  );
}

export default function ChecksTable({ rows }: Props) {
  const [sortKey, setSortKey] = useState<SortKey>('date');
  const [dir, setDir] = useState<1 | -1>(-1);
  const [site, setSite] = useState('all');
  const [type, setType] = useState('all');
  const [colour, setColour] = useState('all');
  const [open, setOpen] = useState<Set<string>>(new Set());

  const sites = useMemo(() => [...new Set(rows.map((r) => r.site))].sort(), [rows]);
  const types = useMemo(() => [...new Set(rows.map((r) => r.typeLabel))].sort(), [rows]);

  const shown = useMemo(() => {
    const list = rows.filter((r) => (site === 'all' || r.site === site) && (type === 'all' || r.typeLabel === type) && (colour === 'all' || r.colour === colour));
    const value = (r: CheckRow): string | number => {
      switch (sortKey) {
        case 'date': return r.date;
        case 'site': return r.site;
        case 'type': return r.typeLabel;
        case 'result': return COLOUR_ORDER[r.colour] ?? 9;
        case 'change': return r.changeMed ?? Number.NEGATIVE_INFINITY;
        case 'evidence': return r.pDecrease ?? -1;
        case 'passes': return (r.nBefore ?? 0) + (r.nAfter ?? 0);
        case 'mde': return r.mdePct ?? 999;
      }
    };
    return list.sort((a, b) => {
      const va = value(a), vb = value(b);
      if (va < vb) return -1 * dir;
      if (va > vb) return 1 * dir;
      return 0;
    });
  }, [rows, site, type, colour, sortKey, dir]);

  const sortBy = (key: SortKey) => {
    if (key === sortKey) setDir(dir === 1 ? -1 : 1);
    else {
      setSortKey(key);
      setDir(key === 'date' ? -1 : 1);
    }
  };
  const toggle = (id: string) => {
    const next = new Set(open);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setOpen(next);
  };
  const header = (key: SortKey, label: string, numeric = false) => (
    <th scope="col" className={numeric ? 'num' : undefined} aria-sort={sortKey === key ? (dir === 1 ? 'ascending' : 'descending') : 'none'}>
      <button type="button" onClick={() => sortBy(key)}>
        {label} <span className="dir" aria-hidden="true">{sortKey === key ? (dir === 1 ? '▲' : '▼') : '↕'}</span>
      </button>
    </th>
  );

  return (
    <div>
      <form className="checks-filters" aria-label="Filter the checks" onSubmit={(e) => e.preventDefault()}>
        <label>Landfill
          <select value={site} onChange={(e) => setSite(e.target.value)}>
            <option value="all">All</option>
            {sites.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </label>
        <label>Record
          <select value={type} onChange={(e) => setType(e.target.value)}>
            <option value="all">All</option>
            {types.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
        </label>
        <label>Result
          <select value={colour} onChange={(e) => setColour(e.target.value)}>
            <option value="all">All</option>
            {Object.entries(COLOUR_LABEL).map(([c, l]) => <option key={c} value={c}>{l}</option>)}
          </select>
        </label>
      </form>
      <p className="checks-count" aria-live="polite">{shown.length} of {rows.length} checks shown.</p>

      <div className="only-wide">
        {/* A wide table scrolls sideways; the region must be reachable from the keyboard. */}
        {/* eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex */}
        <div className="table-wrap" tabIndex={0} role="region" aria-label="Past checks">
          <table className="checks-table">
            <thead>
              <tr>
                <th scope="col"><span className="visually-hidden">Details</span></th>
                {header('date', 'Date')}
                {header('site', 'Landfill')}
                {header('type', 'Record')}
                {header('result', 'Result')}
                {header('change', 'Change', true)}
                {header('evidence', 'Evidence')}
                {header('passes', 'Passes before / after', true)}
                {header('mde', 'Smallest drop the test could see', true)}
              </tr>
            </thead>
            <tbody>
              {shown.map((r) => (
                <RowPair key={r.id} r={r} open={open.has(r.id)} onToggle={() => toggle(r.id)} />
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <ul className="checks-cards only-narrow">
        {shown.map((r) => (
          <li key={r.id}>
            <details>
              <summary className={r.colour}>
                <span className="title">{r.dateLabel} · {r.site} · {r.typeLabel}</span>
              </summary>
              <div className="body">
                <Badge colour={r.colour} label={r.badge} />
                <Details r={r} />
                <p><a href={r.siteHref}>Landfill page</a></p>
              </div>
            </details>
          </li>
        ))}
      </ul>
    </div>
  );
}

function RowPair({ r, open, onToggle }: { r: CheckRow; open: boolean; onToggle: () => void }) {
  return (
    <>
      <tr>
        <td>
          <button type="button" className="expand" aria-expanded={open} aria-controls={`detail-${r.id}`} onClick={onToggle} aria-label={`${open ? 'Hide' : 'Show'} details for ${r.site}, ${r.dateLabel}`}>
            <span aria-hidden="true">{open ? '−' : '+'}</span>
          </button>
        </td>
        <td>{r.dateLabel}<br /><span className="muted">{r.dateConfidence}</span></td>
        <th scope="row"><a href={r.siteHref}>{r.site}</a></th>
        <td>{r.typeLabel}{r.repairKind ? ` (${r.repairKind})` : ''}</td>
        <td className="result"><Badge colour={r.colour} label={r.badge} /></td>
        <td className="num">{r.changeMed == null ? '–' : <>{pct(r.changeMed)}<br /><span className="muted">{pct(r.changeLo)} to {pct(r.changeHi)}</span></>}</td>
        <td>{r.evidence ?? '–'}{r.pDecrease != null && <><br /><span className="muted">P(decrease) {r.pDecrease.toFixed(2)}</span></>}</td>
        <td className="num">{r.nBefore == null ? '–' : `${r.nBefore} / ${r.nAfter}`}</td>
        <td className="num">{r.mdePct != null ? `${r.mdePct.toFixed(0)}%` : r.call ? 'none of the tested drops' : '–'}</td>
      </tr>
      {open && (
        <tr className="detail" id={`detail-${r.id}`}>
          <td colSpan={9}><Details r={r} /></td>
        </tr>
      )}
    </>
  );
}
