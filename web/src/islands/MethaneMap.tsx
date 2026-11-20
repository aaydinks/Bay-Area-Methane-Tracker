import type { FeatureCollection } from 'geojson';
import { type GeoJSONSource, type LayerSpecification, LngLatBounds, Map as MapLibreMap, Marker, NavigationControl, ScaleControl, setWorkerUrl } from 'maplibre-gl';
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url';
import 'maplibre-gl/dist/maplibre-gl.css';
import { useEffect, useMemo, useRef, useState } from 'react';
import { firstMonthOf, shortMonth, stepLabel, stepOf, stepsFor, type StepKind } from '../lib/timeline';

setWorkerUrl(workerUrl);

// The light basemap only: the site has one light theme.
const STYLE = 'https://tiles.openfreemap.org/styles/positron';
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
  availableSources: string[];
}

type FC = FeatureCollection;
const EMPTY: FC = { type: 'FeatureCollection', features: [] };

function fmt(x: number | null | undefined) {
  if (x == null) return '–';
  return x.toLocaleString('en-US', { maximumSignificantDigits: 3 });
}

function addLayers(map: MapLibreMap) {
  for (const id of ['boundaries', 'sites', 'neighbours', 'passes', 'plumes']) {
    if (!map.getSource(id)) map.addSource(id, { type: 'geojson', data: EMPTY });
  }
  const specs: LayerSpecification[] = [
    { id: 'boundaries-line', type: 'line', source: 'boundaries', paint: { 'line-color': '#6b6b6b', 'line-width': 1, 'line-dasharray': [2, 2] } },
    { id: 'sites-fill', type: 'fill', source: 'sites', paint: { 'fill-color': '#8fc59c', 'fill-opacity': 0.35 } },
    { id: 'sites-line', type: 'line', source: 'sites', filter: ['!', ['to-boolean', ['get', 'provisional']]], paint: { 'line-color': '#2f6b3f', 'line-width': 2 } },
    { id: 'sites-line-provisional', type: 'line', source: 'sites', filter: ['to-boolean', ['get', 'provisional']], paint: { 'line-color': '#2f6b3f', 'line-width': 2, 'line-dasharray': [3, 2] } },
    {
      id: 'passes-circle', type: 'circle', source: 'passes',
      paint: {
        'circle-radius': ['interpolate', ['linear'], ['get', 'usable_passes'], 0, 6, 50, 18, 500, 44],
        'circle-color': '#111111', 'circle-opacity': 0.12, 'circle-stroke-color': '#111111', 'circle-stroke-width': 1.5,
      },
    },
    { id: 'neighbours-point', type: 'circle', source: 'neighbours', paint: { 'circle-radius': 6, 'circle-color': '#111111', 'circle-stroke-color': '#ffffff', 'circle-stroke-width': 1.5 } },
    {
      id: 'plumes-heat', type: 'heatmap', source: 'plumes', maxzoom: 15,
      paint: {
        'heatmap-weight': 1,
        'heatmap-intensity': ['interpolate', ['linear'], ['zoom'], 7, 0.6, 13, 2],
        'heatmap-radius': ['interpolate', ['linear'], ['zoom'], 7, 10, 13, 40],
        'heatmap-opacity': ['interpolate', ['linear'], ['zoom'], 11, 0.85, 14, 0.4],
        'heatmap-color': ['interpolate', ['linear'], ['heatmap-density'], 0, 'rgba(143,197,156,0)', 0.2, 'rgba(143,197,156,0.45)', 0.5, '#e5707f', 0.8, '#c8102e', 1, '#9b0d22'],
      },
    },
    {
      id: 'plumes-point', type: 'circle', source: 'plumes',
      paint: {
        'circle-radius': ['interpolate', ['linear'], ['zoom'], 7, 3, 10, 5, 14, 7],
        'circle-color': '#c8102e',
        'circle-opacity': ['case', ['==', ['get', 'attribution'], 'ambiguous'], 0, 0.85],
        'circle-stroke-color': ['case', ['to-boolean', ['get', 'new_in_update']], '#111111', '#c8102e'],
        'circle-stroke-width': ['case', ['to-boolean', ['get', 'new_in_update']], 3, ['==', ['get', 'attribution'], 'ambiguous'], 2, 1],
      },
    },
  ];
  for (const spec of specs) if (!map.getLayer(spec.id)) map.addLayer(spec);
}

export default function MethaneMap({ sites, availableSources }: Props) {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const markersRef = useRef<Marker[]>([]);
  const [data, setData] = useState<{ plumes: FC; sites: FC; boundaries: FC; neighbours: FC } | null>(null);
  const [ready, setReady] = useState(0);
  const [sources, setSources] = useState<Set<string>>(new Set(availableSources));
  const [instruments, setInstruments] = useState<Set<string>>(new Set(INSTRUMENTS.map((i) => i.id)));
  // The timeline: all dates at once, or one month (or quarter) at a time.
  const [stepKind, setStepKind] = useState<'all' | StepKind>('all');
  const [index, setIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
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

  const dates = useMemo(() => (data ? data.plumes.features.map((f) => String(f.properties?.acquired_utc ?? '')) : []), [data]);
  const span = useMemo(() => stepsFor(dates, 'month'), [dates]);
  const steps = useMemo(() => (stepKind === 'all' ? [] : stepsFor(dates, stepKind)), [dates, stepKind]);
  const current = stepKind === 'all' ? null : (steps[Math.min(index, steps.length - 1)] ?? null);
  const hasRates = useMemo(() => Boolean(data?.plumes.features.some((f) => f.properties?.q_kg_hr != null)), [data]);

  const filtered = useMemo<FC>(() => {
    if (!data) return EMPTY;
    return {
      type: 'FeatureCollection',
      features: data.plumes.features.filter((f) => {
        const p = f.properties ?? {};
        if (!sources.has(String(p.source)) || !instruments.has(String(p.instrument))) return false;
        return stepKind === 'all' || current === null || stepOf(String(p.acquired_utc ?? ''), stepKind) === current;
      }),
    };
  }, [data, sources, instruments, stepKind, current]);

  // Play steps forward about once a second and stops on the last step.
  useEffect(() => {
    if (!playing || stepKind === 'all') return;
    const timer = window.setInterval(() => {
      setIndex((i) => {
        if (i >= steps.length - 1) {
          setPlaying(false);
          return i;
        }
        return i + 1;
      });
    }, 1100);
    return () => window.clearInterval(timer);
  }, [playing, stepKind, steps.length]);

  const changeStep = (next: 'all' | StepKind) => {
    setPlaying(false);
    if (next !== 'all') {
      // Keep the reader's place: the new step that holds the month they were looking at.
      const month = current && stepKind !== 'all' ? firstMonthOf(current, stepKind) : null;
      const nextSteps = stepsFor(dates, next);
      const at = month ? nextSteps.indexOf(stepOf(month, next)) : 0;
      setIndex(Math.max(0, at));
    }
    setStepKind(next);
  };
  const togglePlay = () => {
    if (playing) {
      setPlaying(false);
      return;
    }
    if (stepKind === 'all') {
      setStepKind('month');
      setIndex(0);
    } else if (index >= steps.length - 1) {
      setIndex(0);
    }
    setPlaying(true);
  };

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

  // The map itself. The style load adds the layers and bumps `ready`, so the data and toggle
  // effects below run on the loaded style.
  useEffect(() => {
    if (!container.current || mapRef.current) return;
    const map = new MapLibreMap({
      container: container.current,
      style: STYLE,
      center: [-122.25, 37.85],
      zoom: 8.2,
      attributionControl: { compact: false },
    });
    // Open on the five landfills, whatever the width of the screen.
    if (sites.length > 1) {
      const bounds = sites.reduce((b, s) => b.extend([s.lon, s.lat]), new LngLatBounds([sites[0].lon, sites[0].lat], [sites[0].lon, sites[0].lat]));
      map.fitBounds(bounds, { padding: { top: 40, bottom: 40, left: 64, right: 48 }, maxZoom: 11, animate: false });
    }
    map.addControl(new NavigationControl({ visualizePitch: false }), 'top-left');
    map.addControl(new ScaleControl({ unit: 'metric' }), 'bottom-left');
    map.on('style.load', () => {
      addLayers(map);
      setReady((n) => n + 1);
    });
    mapRef.current = map;
    return () => {
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

  // Plumes per landfill for the dates and filters shown, for the count badge on each marker.
  const countsBySite = useMemo(() => {
    const counts = new Map<string, number>();
    for (const f of filtered.features) {
      const id = String(f.properties?.site_id ?? '');
      if (id && f.properties?.attribution !== 'ambiguous') counts.set(id, (counts.get(id) ?? 0) + 1);
    }
    return counts;
  }, [filtered]);

  // Site markers: shape = latest record type, colour = its result, grey when none on record. A red
  // badge gives the number of plumes at the site for the dates shown, readable at any zoom.
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
      const n = countsBySite.get(s.site_id) ?? 0;
      el.setAttribute('aria-label', `${s.name}: ${n} ${n === 1 ? 'plume' : 'plumes'} for the dates shown; latest check: ${what}`);
      el.innerHTML = `<svg viewBox="0 0 16 16" aria-hidden="true" fill="currentColor">${SHAPES[s.latest?.held ? 'lock' : (s.latest?.icon ?? 'dot')] ?? SHAPES.dot}</svg>${n ? `<span class="plume-badge" aria-hidden="true">${n}</span>` : ''}`;
      el.addEventListener('click', () => setSelected((cur) => (cur === s.site_id ? null : s.site_id)));
      return new Marker({ element: el }).setLngLat([s.lon, s.lat]).addTo(map);
    });
    return () => {
      markersRef.current.forEach((m) => m.remove());
      markersRef.current = [];
    };
  }, [ready, sites, selected, countsBySite]);

  const site = sites.find((s) => s.site_id === selected) ?? null;
  const plumesAtSite = site ? filtered.features.filter((f) => f.properties?.site_id === site.site_id).length : 0;
  const toggleIn = (set: Set<string>, id: string) => {
    const next = new Set(set);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    return next;
  };
  const count = filtered.features.length;
  const countText = `${count.toLocaleString('en-US')} ${count === 1 ? 'plume' : 'plumes'} seen`;
  const when = stepKind === 'all' || !current
    ? span.length ? `All dates, ${shortMonth(span[0])} to ${shortMonth(span[span.length - 1])}` : 'All dates'
    : stepLabel(current, stepKind);

  return (
    <div className="map-layout">
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
              <dd>{plumesAtSite} for {stepKind === 'all' ? 'all dates' : when}</dd>
              <dt>Passes</dt>
              <dd>{site.usable_passes} usable; {site.plume_days} plume days ({site.plume_days_per_usable_pass == null ? '–' : site.plume_days_per_usable_pass.toFixed(3)} per usable pass)</dd>
            </dl>
            <p style={{ margin: 0 }}><a href={site.href}>Landfill page</a></p>
          </aside>
        )}
      </div>

      <div className="timeline" role="group" aria-label="Plumes over time">
        <div className="timeline-row">
          <button
            type="button"
            className="play"
            aria-pressed={playing}
            onClick={togglePlay}
            disabled={!span.length}
          >
            <svg viewBox="0 0 16 16" aria-hidden="true" fill="currentColor">
              {playing ? <path d="M4 3h3v10H4zM9 3h3v10H9z" /> : <path d="M4 2.5v11l9-5.5z" />}
            </svg>
            {playing ? 'Pause' : 'Play'}
          </button>
          <fieldset className="step-choice">
            <legend className="visually-hidden">Show plumes</legend>
            {(
              [
                ['all', 'All dates'],
                ['month', 'By month'],
                ['quarter', 'By quarter'],
              ] as const
            ).map(([key, label]) => (
              <label key={key} className={stepKind === key ? 'is-on' : undefined}>
                <input type="radio" name="step" value={key} checked={stepKind === key} onChange={() => changeStep(key)} disabled={!span.length} /> {label}
              </label>
            ))}
          </fieldset>
        </div>
        {stepKind !== 'all' && steps.length > 1 && (
          <input
            className="timeline-slider"
            type="range"
            min={0}
            max={steps.length - 1}
            value={Math.min(index, steps.length - 1)}
            aria-label={stepKind === 'month' ? 'Month' : 'Quarter'}
            aria-valuetext={when}
            onChange={(e) => {
              setPlaying(false);
              setIndex(Number(e.target.value));
            }}
          />
        )}
        <p className="timeline-label" aria-live={playing ? 'off' : 'polite'}>
          {data ? (
            <>
              <strong>{when}</strong> <span className="timeline-count">· {countText}</span>
            </>
          ) : (
            'Loading map data…'
          )}
        </p>
        <p className="timeline-note">Each red dot is one plume. A month with few or no dots may simply have had few clear looks at the landfills.</p>
      </div>

      <ul className="map-legend" aria-label="Key">
        <li><span className="swatch plume" /> Plume</li>
        <li><span className="swatch heat" /> Many plumes close together</li>
        <li><span className="swatch marker" /><span className="swatch badge" aria-hidden="true">3</span> Landfill and its number of plumes for the dates shown; select it for a summary</li>
        <li><span className="swatch pass" /> Clear looks at the site (bigger ring, more looks)</li>
      </ul>

      <details className="map-more">
        <summary>More map options</summary>
        <form className="map-controls" aria-label="Map filters" onSubmit={(e) => e.preventDefault()}>
          <fieldset>
            <legend>Source</legend>
            {SOURCES.filter((s) => availableSources.includes(s.id)).map((s) => (
              <label key={s.id}>
                <input type="checkbox" checked={sources.has(s.id)} onChange={() => setSources(toggleIn(sources, s.id))} /> {s.label}
              </label>
            ))}
          </fieldset>
          <fieldset>
            <legend>Instrument</legend>
            {INSTRUMENTS.map((i) => (
              <label key={i.id}>
                <input type="checkbox" checked={instruments.has(i.id)} onChange={() => setInstruments(toggleIn(instruments, i.id))} /> {i.label}
              </label>
            ))}
          </fieldset>
          {hasRates && (
            <fieldset>
              <legend>Heat map weight</legend>
              <label><input type="radio" name="weight" checked={weight === 'count'} onChange={() => setWeight('count')} /> Count of plumes</label>
              <label><input type="radio" name="weight" checked={weight === 'rate'} onChange={() => setWeight('rate')} /> Rate, where known</label>
            </fieldset>
          )}
          <fieldset>
            <legend>Layers</legend>
            {(
              [
                ['heat', 'Plume heat map'],
                ['points', 'Plume dots'],
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
        <h3 className="map-more-heading">Full key</h3>
        <ul className="map-legend full" aria-label="Full key">
          <li><span className="swatch heat" /> Plume density</li>
          <li><span className="swatch plume" /> Plume origin</li>
          <li><span className="swatch ambiguous" /> Ambiguous, near another source</li>
          <li><span className="swatch new" /> New in the latest update</li>
          <li><span className="swatch pass" /> Usable passes (size)</li>
          <li><span className="swatch outline" /> Site outline (dashed: provisional)</li>
          <li><span className="swatch neighbour" /> Neighbouring source</li>
          <li><span className="swatch boundary" /> County and Air District</li>
          <li>Marker shape: type of the latest record; colour: its result; grey: no check on record</li>
        </ul>
      </details>
    </div>
  );
}
