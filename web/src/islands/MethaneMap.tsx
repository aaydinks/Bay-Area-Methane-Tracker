import type { FeatureCollection } from 'geojson';
import { type GeoJSONSource, type LayerSpecification, Map as MapLibreMap, Marker, NavigationControl, ScaleControl, setWorkerUrl } from 'maplibre-gl';
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url';
import 'maplibre-gl/dist/maplibre-gl.css';
import { useEffect, useMemo, useRef, useState } from 'react';

setWorkerUrl(workerUrl);

const STYLES = { light: 'https://tiles.openfreemap.org/styles/positron', dark: 'https://tiles.openfreemap.org/styles/dark' };
const SOURCES = [
  { id: 'carbonmapper', label: 'Carbon Mapper' },
  { id: 'emit-v2', label: 'NASA EMIT' },
  { id: 's2-local', label: 'Sentinel-2' },
];
const INSTRUMENTS = [
  { id: 'tanager1', label: 'Tanager-1' },
  { id: 'aircraft', label: 'Aircraft' },
  { id: 'emit', label: 'EMIT' },
  { id: 'sentinel2', label: 'Sentinel-2' },
];
const SHAPES: Record<string, string> = {
  clipboard: '<path d="M5 2h6v2h2v11H3V4h2z" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M6 1h4v3H6z"/>',
  document: '<path d="M3 1h7l3 3v11H3z" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M5 8h6M5 11h6" stroke="currentColor" stroke-width="1.4"/>',
  wrench: '<path d="M10.5 1.5a4 4 0 0 0-3.8 5.3L1.5 12l2.5 2.5 5.2-5.2A4 4 0 0 0 14.5 5l-2.3 2.3-2.5-2.5z"/>',
  satellite: '<path d="M2 6l4-4 3 3-4 4zM7 11l4-4 3 3-4 4z"/><path d="M6.5 6.5l3 3" stroke="currentColor" stroke-width="1.6"/>',
  dot: '<circle cx="8" cy="8" r="3"/>',
  lock: '<rect x="3" y="7" width="10" height="8" rx="1.5"/><path d="M5 7V5a3 3 0 0 1 6 0v2" fill="none" stroke="currentColor" stroke-width="1.6"/>',
};

export interface SiteSummary {
  site_id: string;
  name: string;
  href: string;
  lon: number;
  lat: number;
  provisional: boolean;
  status: string | null;
  usable_passes: number;
  plume_days: number;
  plume_days_per_usable_pass: number | null;
  estimate: { med: number; lo: number; hi: number } | null;
  estimate_status: string | null;
  latest: { colour: string; label: string; icon: string; type_label: string; held: boolean } | null;
}

interface Props {
  sites: SiteSummary[];
  isPublic: boolean;
  dataThrough: string | null;
  availableSources: string[];
}

type FC = FeatureCollection;
const EMPTY: FC = { type: 'FeatureCollection', features: [] };

function monthKey(iso: string) {
  return iso.slice(0, 7);
}
function monthLabel(key: string) {
  const [y, m] = key.split('-').map(Number);
  return new Date(Date.UTC(y, m - 1, 1)).toLocaleDateString('en-US', { month: 'short', year: 'numeric', timeZone: 'UTC' });
}
function currentTheme(): 'light' | 'dark' {
  return document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'light';
}
function fmt(x: number | null | undefined) {
  if (x == null) return '–';
  return x.toLocaleString('en-US', { maximumSignificantDigits: 3 });
}

function addLayers(map: MapLibreMap) {
  for (const id of ['boundaries', 'sites', 'neighbours', 'passes', 'plumes']) {
    if (!map.getSource(id)) map.addSource(id, { type: 'geojson', data: EMPTY });
  }
  const specs: LayerSpecification[] = [
    { id: 'boundaries-line', type: 'line', source: 'boundaries', paint: { 'line-color': '#7a848e', 'line-width': 1, 'line-dasharray': [2, 2] } },
    { id: 'sites-fill', type: 'fill', source: 'sites', paint: { 'fill-color': '#0b6b5b', 'fill-opacity': 0.12 } },
    { id: 'sites-line', type: 'line', source: 'sites', filter: ['!', ['to-boolean', ['get', 'provisional']]], paint: { 'line-color': '#0b6b5b', 'line-width': 2 } },
    { id: 'sites-line-provisional', type: 'line', source: 'sites', filter: ['to-boolean', ['get', 'provisional']], paint: { 'line-color': '#0b6b5b', 'line-width': 2, 'line-dasharray': [3, 2] } },
    {
      id: 'passes-circle', type: 'circle', source: 'passes',
      paint: {
        'circle-radius': ['interpolate', ['linear'], ['get', 'usable_passes'], 0, 6, 50, 18, 500, 44],
        'circle-color': '#0b57a4', 'circle-opacity': 0.18, 'circle-stroke-color': '#0b57a4', 'circle-stroke-width': 1.5,
      },
    },
    { id: 'neighbours-point', type: 'circle', source: 'neighbours', paint: { 'circle-radius': 6, 'circle-color': '#6b4e9b', 'circle-stroke-color': '#ffffff', 'circle-stroke-width': 1.5 } },
    {
      id: 'plumes-heat', type: 'heatmap', source: 'plumes', maxzoom: 15,
      paint: {
        'heatmap-weight': 1,
        'heatmap-intensity': ['interpolate', ['linear'], ['zoom'], 7, 0.6, 13, 2],
        'heatmap-radius': ['interpolate', ['linear'], ['zoom'], 7, 10, 13, 40],
        'heatmap-opacity': ['interpolate', ['linear'], ['zoom'], 11, 0.85, 14, 0.4],
        'heatmap-color': ['interpolate', ['linear'], ['heatmap-density'], 0, 'rgba(11,107,91,0)', 0.2, 'rgba(11,107,91,0.35)', 0.5, '#e8b421', 0.8, '#d4621c', 1, '#a4161a'],
      },
    },
    {
      id: 'plumes-point', type: 'circle', source: 'plumes', minzoom: 10,
      paint: {
        'circle-radius': 5,
        'circle-color': '#a4161a',
        'circle-opacity': ['case', ['==', ['get', 'attribution'], 'ambiguous'], 0, 0.85],
        'circle-stroke-color': ['case', ['to-boolean', ['get', 'new_in_update']], '#0b6b5b', '#a4161a'],
        'circle-stroke-width': ['case', ['to-boolean', ['get', 'new_in_update']], 3, ['==', ['get', 'attribution'], 'ambiguous'], 2, 1],
      },
    },
  ];
  for (const spec of specs) if (!map.getLayer(spec.id)) map.addLayer(spec);
}

export default function MethaneMap({ sites, isPublic, dataThrough, availableSources }: Props) {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const markersRef = useRef<Marker[]>([]);
  const [data, setData] = useState<{ plumes: FC; sites: FC; boundaries: FC; neighbours: FC } | null>(null);
  const [ready, setReady] = useState(0);
  const [sources, setSources] = useState<Set<string>>(new Set(availableSources));
  const [instruments, setInstruments] = useState<Set<string>>(new Set(INSTRUMENTS.map((i) => i.id)));
  const [range, setRange] = useState<[number, number] | null>(null);
  const [weight, setWeight] = useState<'count' | 'rate'>('count');
  const [layers, setLayers] = useState({ heat: true, points: true, passes: true, outlines: true, neighbours: true, boundaries: true });
  const [selected, setSelected] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    Promise.all(
      ['plumes', 'sites', 'boundaries', 'neighbours'].map((n) =>
        fetch(`/data/${n}.geojson`).then((r) => (r.ok ? r.json() : EMPTY)).catch(() => EMPTY),
      ),
    ).then(([plumes, sitesFc, boundaries, neighbours]) => {
      if (alive) setData({ plumes, sites: sitesFc, boundaries, neighbours });
    });
    return () => {
      alive = false;
    };
  }, []);

  const months = useMemo(() => {
    if (!data) return [] as string[];
    const keys = new Set<string>();
    for (const f of data.plumes.features) keys.add(monthKey(String(f.properties?.acquired_utc ?? '')));
    return [...keys].filter((k) => k.length === 7).sort();
  }, [data]);
  useEffect(() => {
    if (months.length && !range) setRange([0, months.length - 1]);
  }, [months, range]);

  const filtered = useMemo<FC>(() => {
    if (!data) return EMPTY;
    const [a, b] = range ?? [0, Math.max(0, months.length - 1)];
    const lo = months[a] ?? '0000-00';
    const hi = months[b] ?? '9999-99';
    return {
      type: 'FeatureCollection',
      features: data.plumes.features.filter((f) => {
        const p = f.properties ?? {};
        const m = monthKey(String(p.acquired_utc ?? ''));
        return sources.has(String(p.source)) && instruments.has(String(p.instrument)) && m >= lo && m <= hi;
      }),
    };
  }, [data, sources, instruments, range, months]);

  const passFc = useMemo<FC>(
    () => ({
      type: 'FeatureCollection',
      features: sites.map((s) => ({
        type: 'Feature',
        geometry: { type: 'Point', coordinates: [s.lon, s.lat] },
        properties: { site_id: s.site_id, usable_passes: s.usable_passes, plume_days: s.plume_days },
      })),
    }),
    [sites],
  );

  // The map itself. Every style load (first paint and each theme switch) re-adds the layers and
  // bumps `ready`, so the data and toggle effects below run again on the fresh style.
  useEffect(() => {
    if (!container.current || mapRef.current) return;
    const map = new MapLibreMap({
      container: container.current,
      style: STYLES[currentTheme()],
      center: [-122.25, 37.85],
      zoom: 8.2,
      attributionControl: { compact: false },
    });
    map.addControl(new NavigationControl({ visualizePitch: false }), 'top-left');
    map.addControl(new ScaleControl({ unit: 'metric' }), 'bottom-left');
    map.on('style.load', () => {
      addLayers(map);
      setReady((n) => n + 1);
    });
    mapRef.current = map;
    const observer = new MutationObserver(() => map.setStyle(STYLES[currentTheme()]));
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
    return () => {
      observer.disconnect();
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready || !data) return;
    const set = (id: string, fc: FC) => (map.getSource(id) as GeoJSONSource | undefined)?.setData(fc);
    set('boundaries', data.boundaries);
    set('sites', data.sites);
    set('neighbours', data.neighbours);
    set('passes', passFc);
    set('plumes', filtered);
  }, [ready, data, filtered, passFc]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    const show = (id: string, on: boolean) => map.getLayer(id) && map.setLayoutProperty(id, 'visibility', on ? 'visible' : 'none');
    show('plumes-heat', layers.heat);
    show('plumes-point', layers.points);
    show('passes-circle', layers.passes);
    show('sites-fill', layers.outlines);
    show('sites-line', layers.outlines);
    show('sites-line-provisional', layers.outlines);
    show('neighbours-point', layers.neighbours);
    show('boundaries-line', layers.boundaries);
    if (map.getLayer('plumes-heat')) {
      map.setPaintProperty(
        'plumes-heat',
        'heatmap-weight',
        weight === 'rate' ? ['interpolate', ['linear'], ['coalesce', ['get', 'q_kg_hr'], 0], 0, 0.15, 500, 0.5, 3000, 1] : 1,
      );
    }
  }, [ready, layers, weight]);

  // Site markers: shape = latest record type, colour = its result, grey when none on record.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    markersRef.current.forEach((m) => m.remove());
    markersRef.current = sites.map((s) => {
      const el = document.createElement('button');
      el.type = 'button';
      const colour = s.latest?.held ? 'grey' : (s.latest?.colour ?? 'grey');
      el.className = `site-marker ${colour}${selected === s.site_id ? ' is-selected' : ''}`;
      const what = s.latest ? (s.latest.held ? 'result held back' : s.latest.label) : 'no check on record';
      el.setAttribute('aria-label', `${s.name}: ${what}`);
      el.innerHTML = `<svg viewBox="0 0 16 16" aria-hidden="true" fill="currentColor">${SHAPES[s.latest?.held ? 'lock' : (s.latest?.icon ?? 'dot')] ?? SHAPES.dot}</svg>`;
      el.addEventListener('click', () => setSelected((cur) => (cur === s.site_id ? null : s.site_id)));
      return new Marker({ element: el }).setLngLat([s.lon, s.lat]).addTo(map);
    });
    return () => {
      markersRef.current.forEach((m) => m.remove());
      markersRef.current = [];
    };
  }, [ready, sites, selected]);

  const site = sites.find((s) => s.site_id === selected) ?? null;
  const plumesAtSite = site ? filtered.features.filter((f) => f.properties?.site_id === site.site_id).length : 0;
  const toggleIn = (set: Set<string>, id: string) => {
    const next = new Set(set);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    return next;
  };

  return (
    <div className="map-layout">
      <form className="map-controls" aria-label="Map filters" onSubmit={(e) => e.preventDefault()}>
        <fieldset>
          <legend>Source</legend>
          {SOURCES.filter((s) => availableSources.includes(s.id)).map((s) => (
            <label key={s.id}>
              <input type="checkbox" checked={sources.has(s.id)} onChange={() => setSources(toggleIn(sources, s.id))} /> {s.label}
            </label>
          ))}
          {isPublic && <p className="muted" style={{ margin: '0.25rem 0 0', fontSize: '0.85rem' }}>Carbon Mapper is held back until its terms are confirmed.</p>}
        </fieldset>
        <fieldset>
          <legend>Instrument</legend>
          {INSTRUMENTS.map((i) => (
            <label key={i.id}>
              <input type="checkbox" checked={instruments.has(i.id)} onChange={() => setInstruments(toggleIn(instruments, i.id))} /> {i.label}
            </label>
          ))}
        </fieldset>
        <fieldset>
          <legend>Dates</legend>
          {months.length > 1 && range ? (
            <>
              <label htmlFor="from">From {monthLabel(months[range[0]])}</label>
              <input id="from" type="range" min={0} max={months.length - 1} value={range[0]} onChange={(e) => setRange([Math.min(Number(e.target.value), range[1]), range[1]])} />
              <label htmlFor="to">To {monthLabel(months[range[1]])}</label>
              <input id="to" type="range" min={0} max={months.length - 1} value={range[1]} onChange={(e) => setRange([range[0], Math.max(Number(e.target.value), range[0])])} />
              <div className="range-labels"><span>{monthLabel(months[0])}</span><span>{monthLabel(months[months.length - 1])}</span></div>
            </>
          ) : (
            <p className="muted" style={{ margin: 0 }}>{data ? 'Too few plume dates to filter.' : 'Loading…'}</p>
          )}
        </fieldset>
        <fieldset>
          <legend>Heat map weight</legend>
          <label><input type="radio" name="weight" checked={weight === 'count'} onChange={() => setWeight('count')} /> Count of plumes</label>
          <label><input type="radio" name="weight" checked={weight === 'rate'} onChange={() => setWeight('rate')} /> Rate, where known</label>
        </fieldset>
        <fieldset>
          <legend>Layers</legend>
          {(
            [
              ['heat', 'Plume heat map'],
              ['points', 'Plume origins (zoom in)'],
              ['passes', 'Usable passes per site'],
              ['outlines', 'Site outlines'],
              ['neighbours', 'Neighbouring sources'],
              ['boundaries', 'County and Air District lines'],
            ] as const
          ).map(([key, label]) => (
            <label key={key}>
              <input type="checkbox" checked={layers[key]} onChange={() => setLayers({ ...layers, [key]: !layers[key] })} /> {label}
            </label>
          ))}
        </fieldset>
      </form>

      <div className="map-stage">
        {/* The canvas is a scrollable, zoomable region and must be reachable from the keyboard. */}
        {/* eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex */}
        <div ref={container} className="map-canvas" role="region" aria-label="Map of plumes and landfills" tabIndex={0} />
        {site && (
          <aside className="map-panel" aria-label={`${site.name} summary`}>
            <button type="button" className="close" aria-label="Close" onClick={() => setSelected(null)}>×</button>
            <h3>{site.name}</h3>
            <p className="muted" style={{ margin: 0 }}>{site.status ?? ''}{site.provisional ? ' · provisional outline' : ''}</p>
            <dl className="facts">
              <dt>Latest estimate</dt>
              <dd>{site.estimate ? `${fmt(site.estimate.med)} t/yr (90% range ${fmt(site.estimate.lo)} to ${fmt(site.estimate.hi)})` : site.estimate_status === 'insufficient_data' ? 'Insufficient data' : 'None yet'}</dd>
              <dt>Latest check</dt>
              <dd>{site.latest ? (site.latest.held ? `${site.latest.type_label}: result held back` : `${site.latest.type_label}: ${site.latest.label}`) : 'No check on record'}</dd>
              <dt>Plumes shown</dt>
              <dd>{plumesAtSite} with the current filters</dd>
              <dt>Passes</dt>
              <dd>{site.usable_passes} usable; {site.plume_days} plume days ({site.plume_days_per_usable_pass == null ? '–' : site.plume_days_per_usable_pass.toFixed(3)} per usable pass)</dd>
            </dl>
            <p style={{ margin: 0 }}><a href={site.href}>Landfill page</a></p>
          </aside>
        )}
        <ul className="map-legend" aria-label="Legend">
          <li><span className="swatch heat" /> Plume density</li>
          <li><span className="swatch plume" /> Plume origin</li>
          <li><span className="swatch ambiguous" /> Ambiguous, near another source</li>
          <li><span className="swatch new" /> New in the latest update</li>
          <li><span className="swatch pass" /> Usable passes (size)</li>
          <li><span className="swatch outline" /> Site outline (dashed: provisional)</li>
          <li><span className="swatch neighbour" /> Neighbouring source</li>
          <li><span className="swatch boundary" /> County and Air District</li>
          <li>Marker shape: record type; colour: latest result</li>
        </ul>
        <p className="map-status" aria-live="polite">
          {data ? `${filtered.features.length} plume origins shown${dataThrough ? `, data through ${dataThrough}` : ''}.` : 'Loading map data…'} Counts follow how often a site was observed.
        </p>
      </div>
    </div>
  );
}
