import { useMemo, useState } from 'react';

// Every landfill in the build as one table: filter by region and by how closely a landfill is
// followed, sort by any column. A landfill without a usable estimate carries no figure and is
// never ranked: sorting by the estimate keeps those rows after the ranked ones, in name order.

export interface SiteRow {
  id: string;
  name: string;
  href: string;
  place: string;
  county: string;
  region: string;
  regionLabel: string;
  studied: boolean;
  usablePasses: number | null;
  plumeDays: number | null;
  /** ``screening``: the figure comes from the screening fit, not the update's main fit. */
  estimate: { med: number; lo: number; hi: number; provisional: boolean; screening: boolean } | null;
  /** What to say in place of a figure: "Not enough data yet" or "No estimate yet". */
  note: string;
  /** Why there is not enough data, when the model gave a reason. */
  reason: string | null;
}

interface Props {
  rows: SiteRow[];
  regions: { id: string; label: string }[];
}

type SortKey = 'name' | 'place' | 'region' | 'passes' | 'days' | 'estimate';

const num = (x: number | null) => (x == null ? '–' : x.toLocaleString('en-US', { maximumSignificantDigits: 3 }));
const byName = (a: SiteRow, b: SiteRow) => a.name.localeCompare(b.name);

function Estimate({ r }: { r: SiteRow }) {
  if (!r.estimate) return <span className="muted">{r.note}{r.reason && <><br /><span className="reason">{r.reason}</span></>}</span>;
  return (
    <>
      {num(r.estimate.med)} t/yr
      <br />
      <span className="muted">{num(r.estimate.lo)} to {num(r.estimate.hi)}{r.estimate.provisional ? ' · provisional' : ''}{r.estimate.screening ? ' · screening fit' : ''}</span>
    </>
  );
}

export default function SitesTable({ rows, regions }: Props) {
  const [sortKey, setSortKey] = useState<SortKey>('estimate');
  const [dir, setDir] = useState<1 | -1>(-1);
  const [region, setRegion] = useState('all');
  const [tier, setTier] = useState('all');

  const hasRegions = regions.length > 1;
  const hasTiers = rows.some((r) => r.studied) && rows.some((r) => !r.studied);

  const shown = useMemo(() => {
    const list = rows.filter((r) => (region === 'all' || r.region === region) && (tier === 'all' || (tier === 'studied') === r.studied));
    const value = (r: SiteRow): string | number => {
      switch (sortKey) {
        case 'name': return r.name;
        case 'place': return `${r.county} ${r.place}`;
        case 'region': return r.regionLabel;
        case 'passes': return r.usablePasses ?? -1;
        case 'days': return r.plumeDays ?? -1;
        case 'estimate': return r.estimate?.med ?? 0;
      }
    };
    return list.sort((a, b) => {
      // No estimate, no rank: these rows stay last whichever way the column is sorted.
      if (sortKey === 'estimate' && Boolean(a.estimate) !== Boolean(b.estimate)) return a.estimate ? -1 : 1;
      if (sortKey === 'estimate' && !a.estimate) return byName(a, b);
      const va = value(a), vb = value(b);
      if (va < vb) return -1 * dir;
      if (va > vb) return 1 * dir;
      return byName(a, b);
    });
  }, [rows, region, tier, sortKey, dir]);

  const sortBy = (key: SortKey) => {
    if (key === sortKey) setDir(dir === 1 ? -1 : 1);
    else {
      setSortKey(key);
      setDir(['passes', 'days', 'estimate'].includes(key) ? -1 : 1);
    }
  };
  const header = (key: SortKey, label: string, numeric = false) => (
    <th scope="col" className={numeric ? 'num' : undefined} aria-sort={sortKey === key ? (dir === 1 ? 'ascending' : 'descending') : 'none'}>
      <button type="button" onClick={() => sortBy(key)}>
        {label} <span className="dir" aria-hidden="true">{sortKey === key ? (dir === 1 ? '▲' : '▼') : '↕'}</span>
      </button>
    </th>
  );
  const ranked = shown.filter((r) => r.estimate).length;

  return (
    <div>
      {(hasRegions || hasTiers) && (
        <form className="sites-filters" aria-label="Filter the landfills" onSubmit={(e) => e.preventDefault()}>
          {hasRegions && (
            <label>Region
              <select value={region} onChange={(e) => setRegion(e.target.value)}>
                <option value="all">All regions</option>
                {regions.map((r) => <option key={r.id} value={r.id}>{r.label}</option>)}
              </select>
            </label>
          )}
          {hasTiers && (
            <label>Show
              <select value={tier} onChange={(e) => setTier(e.target.value)}>
                <option value="all">All landfills</option>
                <option value="studied">Studied in depth</option>
                <option value="screened">Screened</option>
              </select>
            </label>
          )}
        </form>
      )}
      <p className="sites-count" aria-live="polite">
        {shown.length} of {rows.length} landfills shown, {ranked} with an estimate.
      </p>

      <div className="sites-wide">
        {/* A wide table scrolls sideways; the region must be reachable from the keyboard. */}
        {/* eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex */}
        <div className="table-wrap" tabIndex={0} role="region" aria-label="Landfills">
          <table className="sites-table">
            <thead>
              <tr>
                {header('name', 'Landfill')}
                {header('place', 'City and county')}
                {hasRegions && header('region', 'Region')}
                {header('passes', 'Usable passes', true)}
                {header('days', 'Plume days', true)}
                {header('estimate', 'Estimate and 90% range', true)}
              </tr>
            </thead>
            <tbody>
              {shown.map((r) => (
                <tr key={r.id}>
                  <th scope="row">
                    <a href={r.href}>{r.name}</a>
                    {hasTiers && r.studied && <><br /><span className="muted">Studied in depth</span></>}
                  </th>
                  <td>{r.place}</td>
                  {hasRegions && <td>{r.regionLabel}</td>}
                  <td className="num">{num(r.usablePasses)}</td>
                  <td className="num">{num(r.plumeDays)}</td>
                  <td className="num estimate"><Estimate r={r} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <ul className="sites-cards sites-narrow">
        {shown.map((r) => (
          <li key={r.id}>
            <h3><a href={r.href}>{r.name}</a></h3>
            <p className="muted">{r.place}{hasRegions ? ` · ${r.regionLabel}` : ''}{hasTiers && r.studied ? ' · studied in depth' : ''}</p>
            <p>{num(r.usablePasses)} usable {r.usablePasses === 1 ? 'pass' : 'passes'} · {num(r.plumeDays)} plume {r.plumeDays === 1 ? 'day' : 'days'}</p>
            <p><Estimate r={r} /></p>
          </li>
        ))}
      </ul>
    </div>
  );
}
