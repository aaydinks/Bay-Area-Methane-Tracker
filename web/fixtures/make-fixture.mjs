// Writes fixtures/snapshot.json: sample rows in the shape of the database, for CI and local
// work without keys. Nothing here is a real result. Site names and reference points are the
// public CalRecycle entries; every figure is made up and the site shows a banner saying so.
// Deterministic: the same file comes out every time.

import { writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));

// A small seeded generator so the fixture never changes by accident.
let seed = 20261030;
function rand() {
  seed = (seed * 1103515245 + 12345) % 2147483648;
  return seed / 2147483648;
}
const pick = (xs) => xs[Math.floor(rand() * xs.length)];

const SITES = [
  { site_id: 'newby-island', name: 'Newby Island Landfill', city: 'Milpitas', county: 'Santa Clara', lat: 37.45897, lon: -121.94108, status: 'active', swis: '43-AN-0003', ghgrp: '1006179' },
  { site_id: 'acme-fill', name: 'Acme Fill', city: 'Martinez', county: 'Contra Costa', lat: 38.02532, lon: -122.0873, status: 'active', swis: null, ghgrp: null },
  { site_id: 'sonoma-central', name: 'Sonoma Central Landfill', city: 'Petaluma', county: 'Sonoma', lat: 38.29964, lon: -122.74951, status: 'active', swis: '49-AA-0001', ghgrp: '1004123' },
  { site_id: 'shoreline', name: 'Shoreline Landfill', city: 'Mountain View', county: 'Santa Clara', lat: 37.42788, lon: -122.08513, status: 'closed', swis: null, ghgrp: '1005910' },
  { site_id: 'potrero-hills', name: 'Potrero Hills Landfill', city: 'Suisun City', county: 'Solano', lat: 38.21188, lon: -121.98081, status: 'active', swis: null, ghgrp: '1007345' },
];

function circle(lon, lat, metres, n = 32) {
  const dLat = metres / 111320;
  const dLon = metres / (111320 * Math.cos((lat * Math.PI) / 180));
  const ring = [];
  for (let i = 0; i <= n; i += 1) {
    const a = (2 * Math.PI * i) / n;
    ring.push([+(lon + dLon * Math.cos(a)).toFixed(6), +(lat + dLat * Math.sin(a)).toFixed(6)]);
  }
  return { type: 'MultiPolygon', coordinates: [[ring]] };
}

const PUBS = [
  { publish_id: 'fixture-public-0001', created_at: '2026-10-01T18:00:00Z', visibility: 'public', published_at: '2026-10-01T18:05:00Z', simulated: false, provisional: true, refresh_id: 'fixture-refresh-1', model_run_id: 'fixture-model-1', check_run_id: 'fixture-repairs-1', data_through: '2026-09-01', source_lag_days: 30, git_sha: 'fixture0', git_dirty: false, notes: 'Sample publication for development.' },
  { publish_id: 'fixture-review-0002', created_at: '2026-10-20T18:00:00Z', visibility: 'review', published_at: null, simulated: false, provisional: true, refresh_id: 'fixture-refresh-2', model_run_id: 'fixture-model-1', check_run_id: 'fixture-repairs-1', data_through: '2026-09-20', source_lag_days: 30, git_sha: 'fixture0', git_dirty: false, notes: 'Sample publication for development, review visibility.' },
];

const RUNS = [
  { run_id: 'fixture-refresh-1', kind: 'refresh', created_at: '2026-10-01T17:00:00Z', git_sha: 'fixture0', git_dirty: false, config_sha256: {}, versions: {}, manifest: { note: 'sample' } },
  { run_id: 'fixture-refresh-2', kind: 'refresh', created_at: '2026-10-20T17:00:00Z', git_sha: 'fixture0', git_dirty: false, config_sha256: {}, versions: {}, manifest: { note: 'sample' } },
  { run_id: 'fixture-model-1', kind: 'model', created_at: '2026-10-01T17:30:00Z', git_sha: 'fixture0', git_dirty: false, config_sha256: {}, versions: {}, manifest: { note: 'sample' } },
  { run_id: 'fixture-repairs-1', kind: 'repair', created_at: '2026-10-01T17:45:00Z', git_sha: 'fixture0', git_dirty: false, config_sha256: {}, versions: {}, manifest: { note: 'sample' } },
];

const DATA_TERMS = [
  { source: 'cloudsen12', display_name: 'CloudSEN12+ v1.1 expert cloud labels', raw_publishable: true, derived_publishable: true, confirmed: false, checked_on: '2026-10-31', terms_url: 'https://huggingface.co/datasets/tacofoundation/cloudsen12', credit_line: 'CloudSEN12+ (Aybar et al. 2024, Data in Brief 56:110852), CC0' },
  { source: 'carbonmapper', display_name: 'Carbon Mapper (Tanager-1, aircraft)', raw_publishable: false, derived_publishable: false, confirmed: false, checked_on: '2026-10-30', terms_url: null, credit_line: 'Carbon Mapper, non-commercial use' },
  { source: 'emit-v2', display_name: 'NASA EMIT L2B CH4 v002', raw_publishable: true, derived_publishable: true, confirmed: false, checked_on: '2026-10-30', terms_url: 'https://lpdaac.usgs.gov/products/emitl2bch4plmv002/', credit_line: 'NASA EMIT L2B methane products, LP DAAC' },
  { source: 's2-local', display_name: 'ESA Copernicus Sentinel-2 L1C', raw_publishable: true, derived_publishable: true, confirmed: false, checked_on: '2026-10-30', terms_url: null, credit_line: 'Contains modified Copernicus Sentinel data' },
  { source: 'ghgrp', display_name: 'US EPA Greenhouse Gas Reporting Program', raw_publishable: true, derived_publishable: true, confirmed: true, checked_on: '2026-10-30', terms_url: 'https://www.epa.gov/ghgreporting', credit_line: 'US EPA Greenhouse Gas Reporting Program, accessed via Envirofacts' },
  { source: 'baaqmd', display_name: 'Bay Area Air District public records', raw_publishable: true, derived_publishable: true, confirmed: true, checked_on: '2026-10-30', terms_url: null, credit_line: 'Bay Area Air Quality Management District public records' },
  { source: 'census', display_name: 'US Census Bureau ACS and TIGER', raw_publishable: true, derived_publishable: true, confirmed: true, checked_on: '2026-10-30', terms_url: null, credit_line: 'US Census Bureau, American Community Survey 5-year estimates' },
  { source: 'calrecycle', display_name: 'CalRecycle SWIS', raw_publishable: true, derived_publishable: true, confirmed: true, checked_on: '2026-10-30', terms_url: null, credit_line: 'CalRecycle Solid Waste Information System (SWIS)' },
];

const INSTRUMENTS = [
  { instrument: 'emit', source: 'emit-v2', restricted: false, perMonth: [0, 1, 1, 2], start: '2025-01', detectRate: { 'newby-island': 0.25, 'potrero-hills': 0.1 } },
  { instrument: 'sentinel2', source: 's2-local', restricted: false, perMonth: [0, 1, 1, 2], start: '2025-01', detectRate: {} },
  { instrument: 'tanager1', source: 'carbonmapper', restricted: true, perMonth: [0, 1, 1, 2], start: '2025-03', detectRate: { 'newby-island': 0.5, 'potrero-hills': 0.2 } },
  { instrument: 'aircraft', source: 'carbonmapper', restricted: true, perMonth: [0, 0, 0, 1], start: '2025-01', detectRate: { 'newby-island': 0.6, 'potrero-hills': 0.3 } },
];

function months(from, to) {
  const out = [];
  let [y, m] = from.split('-').map(Number);
  const [ty, tm] = to.split('-').map(Number);
  while (y < ty || (y === ty && m <= tm)) {
    out.push(`${y}-${String(m).padStart(2, '0')}`);
    m += 1;
    if (m > 12) { m = 1; y += 1; }
  }
  return out;
}

function passesAndPlumes(pub, through) {
  const passes = [];
  const plumes = [];
  for (const s of SITES) {
    for (const inst of INSTRUMENTS) {
      for (const month of months(inst.start, through)) {
        const n = pick(inst.perMonth);
        const days = new Set();
        for (let k = 0; k < n; k += 1) {
          let day = 1 + Math.floor(rand() * 27);
          while (days.has(day)) day = 1 + Math.floor(rand() * 27);
          days.add(day);
          const acquired = `${month}-${String(day).padStart(2, '0')}T18:30:00Z`;
          const usable = rand() > 0.35;
          const detected = usable && rand() < (inst.detectRate[s.site_id] ?? 0.02);
          const overpass_id = `${s.site_id}:${inst.instrument}:${acquired.slice(0, 10)}`;
          const q = detected ? Math.round(300 + rand() * 2500) : null;
          passes.push({
            publish_id: pub.publish_id, overpass_id, site_id: s.site_id, instrument: inst.instrument, acquired_utc: acquired,
            usable, coverage_frac: usable ? 0.95 : 0.6, valid_frac: usable ? 0.9 : 0.4, coverage_source: inst.instrument === 'emit' ? 'cmr-granule' : inst.instrument === 'sentinel2' ? 's2-scene' : 'stac-footprint',
            detected, q_obs_kg_hr: q, n_plumes: detected ? 1 : 0, restricted: inst.restricted,
          });
          if (detected) {
            plumes.push({
              publish_id: pub.publish_id, plume_id: `fx-${inst.instrument}-${s.site_id}-${acquired.slice(0, 10)}`, source: inst.source, instrument: inst.instrument,
              acquired_utc: acquired, lon: +(s.lon + (rand() - 0.5) * 0.006).toFixed(5), lat: +(s.lat + (rand() - 0.5) * 0.006).toFixed(5),
              q_kg_hr: inst.instrument === 'emit' ? null : q, q_sigma_kg_hr: inst.instrument === 'emit' ? null : Math.round(q * 0.3), site_id: s.site_id,
              attribution: rand() < 0.85 ? 'inside' : 'buffer', distance_m: 0, data_version: 'fixture', overpass_id, restricted: inst.restricted,
              new_in_update: pub.publish_id === 'fixture-review-0002' && acquired > '2026-09-01',
            });
          }
        }
      }
    }
  }
  return { passes, plumes };
}

const sites = PUBS.flatMap((pub) => SITES.map((s) => ({
  publish_id: pub.publish_id, site_id: s.site_id, name: s.name, city: s.city, county: s.county, operator: s.site_id === 'shoreline' ? 'City of Mountain View' : null,
  tier: 'pilot', status: s.status, swis_number: s.swis, ghgrp_facility_id: s.ghgrp, polygon_source: 'provisional 500 m buffer around the CalRecycle SWIS point',
  provisional: true, area_km2: 0.785, lon: s.lon, lat: s.lat, outline_geojson: circle(s.lon, s.lat, 500),
})));

const neighbours = PUBS.map((pub) => ({
  publish_id: pub.publish_id, neighbour_id: 'fx-compost-1', name: 'Sample compost facility (fixture)', kind: 'compost',
  nearest_site_id: 'newby-island', distance_m: 1800, source: 'fixture', geojson: { type: 'Point', coordinates: [-121.925, 37.465] },
}));

const gen1 = passesAndPlumes(PUBS[0], '2026-08');
seed = 20261030;
const gen2 = passesAndPlumes(PUBS[1], '2026-09');

const site_estimates = PUBS.flatMap((pub) => [
  { publish_id: pub.publish_id, model_run_id: 'fixture-model-1', site_id: 'newby-island', period: 'all', n_usable_overpasses: 61, n_detections: 19, f_med: 0.31, f_lo: 0.21, f_hi: 0.43, qbar_kg_hr_med: 1500, qbar_kg_hr_lo: 900, qbar_kg_hr_hi: 2600, e_t_yr_med: 4100, e_t_yr_lo: 1900, e_t_yr_hi: 8300, status: 'provisional', insufficient_reason: null, rhat_max: 1.004, ess_bulk_min: 812, divergences: 0, provisional: true, restricted: true },
  { publish_id: pub.publish_id, model_run_id: 'fixture-model-1', site_id: 'potrero-hills', period: 'all', n_usable_overpasses: 44, n_detections: 5, f_med: 0.11, f_lo: 0.05, f_hi: 0.22, qbar_kg_hr_med: 900, qbar_kg_hr_lo: 400, qbar_kg_hr_hi: 2100, e_t_yr_med: 870, e_t_yr_lo: 230, e_t_yr_hi: 3100, status: 'provisional', insufficient_reason: null, rhat_max: 1.006, ess_bulk_min: 640, divergences: 0, provisional: true, restricted: true },
  { publish_id: pub.publish_id, model_run_id: 'fixture-model-1', site_id: 'acme-fill', period: 'all', n_usable_overpasses: 6, n_detections: 0, f_med: null, f_lo: null, f_hi: null, qbar_kg_hr_med: null, qbar_kg_hr_lo: null, qbar_kg_hr_hi: null, e_t_yr_med: null, e_t_yr_lo: null, e_t_yr_hi: null, status: 'insufficient_data', insufficient_reason: 'fewer than 8 usable passes', rhat_max: null, ess_bulk_min: null, divergences: null, provisional: false, restricted: false },
  { publish_id: pub.publish_id, model_run_id: 'fixture-model-1', site_id: 'sonoma-central', period: 'all', n_usable_overpasses: 7, n_detections: 0, f_med: null, f_lo: null, f_hi: null, qbar_kg_hr_med: null, qbar_kg_hr_lo: null, qbar_kg_hr_hi: null, e_t_yr_med: null, e_t_yr_lo: null, e_t_yr_hi: null, status: 'insufficient_data', insufficient_reason: 'fewer than 8 usable passes', rhat_max: null, ess_bulk_min: null, divergences: null, provisional: false, restricted: false },
  { publish_id: pub.publish_id, model_run_id: 'fixture-model-1', site_id: 'shoreline', period: 'all', n_usable_overpasses: 5, n_detections: 0, f_med: null, f_lo: null, f_hi: null, qbar_kg_hr_med: null, qbar_kg_hr_lo: null, qbar_kg_hr_hi: null, e_t_yr_med: null, e_t_yr_lo: null, e_t_yr_hi: null, status: 'insufficient_data', insufficient_reason: 'fewer than 8 usable passes', rhat_max: null, ess_bulk_min: null, divergences: null, provisional: false, restricted: false },
]);

const checks = PUBS.flatMap((pub) => [
  { publish_id: pub.publish_id, check_id: 'fx-check-1', site_id: 'newby-island', check_type: 'operator-repair', repair_kind: 'cover', date_start: '2025-05-12', date_end: '2025-05-30', date_confidence: 'week', description: 'Sample record: interim cover placed on the north slope.', source_doc: 'fixture-operator-log.pdf', source_doc_title: 'Sample operator log (fixture)', source_url: null, source_page: '3', entered_on: '2026-09-01' },
  { publish_id: pub.publish_id, check_id: 'fx-check-2', site_id: 'sonoma-central', check_type: 'air-district-notice', repair_kind: null, date_start: '2023-06-15', date_end: null, date_confidence: 'month', description: 'Sample record: a notice issued after a surface monitoring round.', source_doc: 'fixture-notice.pdf', source_doc_title: 'Notice of Violation (sample title, fixture)', source_url: null, source_page: null, entered_on: '2026-09-01' },
]);

const check_results = PUBS.flatMap((pub) => [
  { publish_id: pub.publish_id, check_run_id: 'fixture-repairs-1', check_id: 'fx-check-1', site_id: 'newby-island', call: 'inconclusive', effect_med: 0.12, effect_lo: -0.41, effect_hi: 0.63, change_pct_med: 12.7, change_pct_lo: -33.6, change_pct_hi: 87.8, de_t_yr_med: -520, de_t_yr_lo: -3600, de_t_yr_hi: 1700, p_decrease: 0.36, mde_pct: 75, n_before: 14, n_after: 16, controls: 'potrero-hills;sonoma-central', diag_ok: true, reason: '', evidence: 'weak', size: 'slight', colour: 'yellow', plain_reading: 'Methane rose about 13% (90% range -34% to 88%) after this record; weak evidence; this test could only have caught drops of 75% or more.', provisional: true, restricted: true },
  { publish_id: pub.publish_id, check_run_id: 'fixture-repairs-1', check_id: 'fx-check-2', site_id: 'sonoma-central', call: 'insufficient_data', effect_med: null, effect_lo: null, effect_hi: null, change_pct_med: null, change_pct_lo: null, change_pct_hi: null, de_t_yr_med: null, de_t_yr_lo: null, de_t_yr_hi: null, p_decrease: null, mde_pct: null, n_before: 3, n_after: 6, controls: '', diag_ok: null, reason: 'fewer than 5 overpasses in a window', evidence: 'none', size: null, colour: 'grey', plain_reading: 'Not enough passes before this record to test for a change.', provisional: false, restricted: false },
]);

const operator_reports = PUBS.flatMap((pub) => [
  { publish_id: pub.publish_id, site_id: 'newby-island', year: 2022, source: 'GHGRP', reported_ch4_t: 2345.6, reported_co2e_t: 58640, gwp_used: 25, gwp_confirmed: false, facility_id: '1006179', url: 'https://enviro.epa.gov/' },
  { publish_id: pub.publish_id, site_id: 'newby-island', year: 2023, source: 'GHGRP', reported_ch4_t: 2222.2, reported_co2e_t: 55555, gwp_used: 25, gwp_confirmed: false, facility_id: '1006179', url: 'https://enviro.epa.gov/' },
  { publish_id: pub.publish_id, site_id: 'potrero-hills', year: 2023, source: 'GHGRP', reported_ch4_t: 1234.5, reported_co2e_t: 30862, gwp_used: 25, gwp_confirmed: false, facility_id: '1007345', url: 'https://enviro.epa.gov/' },
  { publish_id: pub.publish_id, site_id: 'sonoma-central', year: 2023, source: 'GHGRP', reported_ch4_t: 987.6, reported_co2e_t: 24690, gwp_used: 25, gwp_confirmed: false, facility_id: '1004123', url: 'https://enviro.epa.gov/' },
]);

const population = PUBS.flatMap((pub) => SITES.flatMap((s, i) => [1, 3, 5].map((r) => ({
  publish_id: pub.publish_id, site_id: s.site_id, radius_km: r, residents: (i + 1) * 1000 * r * r, label: 'residents nearby (context only)',
}))));

const site_features = PUBS.flatMap((pub) => SITES.map((s) => ({
  publish_id: pub.publish_id, site_id: s.site_id, closed: s.status === 'closed', area_km2: 0.785, ghgrp_reporter: Boolean(s.ghgrp), dist_neighbor_m: s.site_id === 'newby-island' ? 1800 : null,
})));

// The Sentinel-2 cloud model's held-out test (ADR 0013), copied from what `mw publish` reads in
// reports/validation/s2-cloud-model/ (values rounded to 4 decimals).
const CLOUD_MODEL_CHECKS = [
  {
    "run_id": "s2-cloud-model-20261031T224123Z",
    "superseded": false,
    "created_at": "2026-10-31T22:41:24.338978+00:00",
    "report_id": "s2-cloud-model-20261031T224123Z-claim1",
    "gate": "s2_cloud_usable",
    "result": "pass",
    "metrics": {
      "n_patches": 1095,
      "n_sites": 219,
      "n_truly_unusable": 684,
      "n_tile_rule_scored": 1088,
      "rates": {
        "tile_rule": {
          "false_usable": [
            0.3691,
            0.3397,
            0.3997
          ],
          "false_unusable": [
            0.2623,
            0.226,
            0.2979
          ]
        },
        "threshold": {
          "false_usable": [
            0.5161,
            0.482,
            0.5516
          ],
          "false_unusable": [
            0.1922,
            0.1565,
            0.2295
          ]
        },
        "sen2cor": {
          "false_usable": [
            0.3567,
            0.328,
            0.3872
          ],
          "false_unusable": [
            0.0925,
            0.0678,
            0.1194
          ]
        },
        "s2cloudless": {
          "false_usable": [
            0.3026,
            0.2766,
            0.3296
          ],
          "false_unusable": [
            0.0341,
            0.0196,
            0.049
          ]
        },
        "model": {
          "false_usable": [
            0.0848,
            0.0678,
            0.1017
          ],
          "false_unusable": [
            0.0487,
            0.0318,
            0.0663
          ]
        }
      },
      "comparisons": {
        "tile_rule": {
          "false_usable_diff": [
            -0.2853,
            -0.3187,
            -0.254
          ],
          "false_unusable_diff": [
            -0.2132,
            -0.2512,
            -0.1754
          ],
          "passed": true
        },
        "threshold": {
          "false_usable_diff": [
            -0.4313,
            -0.4697,
            -0.3936
          ],
          "false_unusable_diff": [
            -0.1436,
            -0.1845,
            -0.1017
          ],
          "passed": true
        },
        "sen2cor": {
          "false_usable_diff": [
            -0.2719,
            -0.3026,
            -0.2424
          ],
          "false_unusable_diff": [
            -0.0438,
            -0.0695,
            -0.0194
          ],
          "passed": true
        },
        "s2cloudless": {
          "false_usable_diff": [
            -0.2178,
            -0.2456,
            -0.1928
          ],
          "false_unusable_diff": [
            0.0146,
            -0.0048,
            0.0331
          ],
          "passed": true
        }
      },
      "west_coast": {
        "n_patches": 155,
        "n_sites": 31,
        "n_truly_unusable": 104,
        "n_tile_rule_scored": 155,
        "rates": {
          "tile_rule": {
            "false_usable": [
              0.2596,
              0.1942,
              0.3333
            ],
            "false_unusable": [
              0.2157,
              0.1224,
              0.3036
            ]
          },
          "threshold": {
            "false_usable": [
              0.5192,
              0.422,
              0.6139
            ],
            "false_unusable": [
              0.2157,
              0.0909,
              0.3478
            ]
          },
          "sen2cor": {
            "false_usable": [
              0.2885,
              0.2165,
              0.36
            ],
            "false_unusable": [
              0.0588,
              0.0182,
              0.1132
            ]
          },
          "s2cloudless": {
            "false_usable": [
              0.2788,
              0.21,
              0.3433
            ],
            "false_unusable": [
              0.0196,
              0.0,
              0.0577
            ]
          },
          "model": {
            "false_usable": [
              0.0481,
              0.019,
              0.0811
            ],
            "false_unusable": [
              0.0196,
              0.0,
              0.0577
            ]
          }
        },
        "comparisons": {
          "tile_rule": {
            "false_usable_diff": [
              -0.2115,
              -0.2925,
              -0.1359
            ],
            "false_unusable_diff": [
              -0.1961,
              -0.2857,
              -0.1064
            ],
            "passed": true
          },
          "threshold": {
            "false_usable_diff": [
              -0.4712,
              -0.5714,
              -0.3711
            ],
            "false_unusable_diff": [
              -0.1961,
              -0.3396,
              -0.0638
            ],
            "passed": true
          },
          "sen2cor": {
            "false_usable_diff": [
              -0.2404,
              -0.3107,
              -0.1683
            ],
            "false_unusable_diff": [
              -0.0392,
              -0.1053,
              0.02
            ],
            "passed": true
          },
          "s2cloudless": {
            "false_usable_diff": [
              -0.2308,
              -0.2941,
              -0.1666
            ],
            "false_unusable_diff": [
              0.0,
              -0.0417,
              0.0426
            ],
            "passed": true
          }
        }
      },
      "band_means": {
        "bands": [
          "B01",
          "B02",
          "B03",
          "B04",
          "B05",
          "B06",
          "B07",
          "B08",
          "B8A",
          "B09",
          "B10",
          "B11",
          "B12"
        ],
        "clear": [
          0.1833,
          0.1615,
          0.1508,
          0.1531,
          0.1733,
          0.2299,
          0.2568,
          0.248,
          0.2744,
          0.0946,
          0.0054,
          0.194,
          0.1318
        ],
        "cloud": [
          0.3173,
          0.2994,
          0.2816,
          0.2918,
          0.3049,
          0.3487,
          0.3747,
          0.3598,
          0.3899,
          0.16,
          0.0224,
          0.283,
          0.2154
        ],
        "shadow": [
          0.1806,
          0.1501,
          0.1298,
          0.1228,
          0.1317,
          0.1663,
          0.1838,
          0.1715,
          0.191,
          0.0609,
          0.0053,
          0.119,
          0.0803
        ],
        "pixels": {
          "clear": 36710623,
          "cloud": 27238692,
          "shadow": 6695705
        }
      },
      "bay_area": [
        {
          "site": "ROI_00787",
          "date": "20190902",
          "true_clear": 1.0,
          "clear_model": 0.9632,
          "clear_sen2cor": 0.9908,
          "clear_s2cloudless": 0.9938,
          "clear_threshold": 0.9855,
          "tile_cloud_cover": 40.3929
        },
        {
          "site": "ROI_00787",
          "date": "20200305",
          "true_clear": 0.0,
          "clear_model": 0.5388,
          "clear_sen2cor": 0.2047,
          "clear_s2cloudless": 0.2957,
          "clear_threshold": 0.99,
          "tile_cloud_cover": 79.0177
        },
        {
          "site": "ROI_00787",
          "date": "20200320",
          "true_clear": 0.8373,
          "clear_model": 0.8443,
          "clear_sen2cor": 0.9434,
          "clear_s2cloudless": 0.9213,
          "clear_threshold": 0.9578,
          "tile_cloud_cover": 8.7463
        },
        {
          "site": "ROI_00787",
          "date": "20200325",
          "true_clear": 0.144,
          "clear_model": 0.1577,
          "clear_sen2cor": 0.2689,
          "clear_s2cloudless": 0.1719,
          "clear_threshold": 0.3149,
          "tile_cloud_cover": 47.4957
        },
        {
          "site": "ROI_00787",
          "date": "20200519",
          "true_clear": 0.3956,
          "clear_model": 0.3543,
          "clear_sen2cor": 0.5293,
          "clear_s2cloudless": 0.3717,
          "clear_threshold": 0.662,
          "tile_cloud_cover": 49.4438
        },
        {
          "site": "ROI_00911",
          "date": "20190525",
          "true_clear": 0.029,
          "clear_model": 0.0803,
          "clear_sen2cor": 0.1592,
          "clear_s2cloudless": 0.1408,
          "clear_threshold": 0.2651,
          "tile_cloud_cover": 47.9689
        },
        {
          "site": "ROI_00911",
          "date": "20190629",
          "true_clear": 0.5482,
          "clear_model": 0.7852,
          "clear_sen2cor": 0.9301,
          "clear_s2cloudless": 0.9762,
          "clear_threshold": 0.903,
          "tile_cloud_cover": 22.6673
        },
        {
          "site": "ROI_00911",
          "date": "20200325",
          "true_clear": 0.4903,
          "clear_model": 0.5932,
          "clear_sen2cor": 0.7407,
          "clear_s2cloudless": 0.8011,
          "clear_threshold": 0.8192,
          "tile_cloud_cover": 19.9889
        },
        {
          "site": "ROI_00911",
          "date": "20200424",
          "true_clear": 1.0,
          "clear_model": 0.9816,
          "clear_sen2cor": 0.9991,
          "clear_s2cloudless": 1.0,
          "clear_threshold": 0.9459,
          "tile_cloud_cover": 0.0
        },
        {
          "site": "ROI_00911",
          "date": "20200529",
          "true_clear": 0.5208,
          "clear_model": 0.3661,
          "clear_sen2cor": 0.662,
          "clear_s2cloudless": 0.7933,
          "clear_threshold": 0.8708,
          "tile_cloud_cover": 69.7357
        },
        {
          "site": "ROI_00927",
          "date": "20190629",
          "true_clear": 0.0486,
          "clear_model": 0.0474,
          "clear_sen2cor": 0.0077,
          "clear_s2cloudless": 0.1917,
          "clear_threshold": 0.917,
          "tile_cloud_cover": 22.6673
        },
        {
          "site": "ROI_00927",
          "date": "20190828",
          "true_clear": 0.4911,
          "clear_model": 0.6864,
          "clear_sen2cor": 0.9606,
          "clear_s2cloudless": 0.936,
          "clear_threshold": 0.9743,
          "tile_cloud_cover": 15.2732
        },
        {
          "site": "ROI_00927",
          "date": "20191027",
          "true_clear": 1.0,
          "clear_model": 0.9908,
          "clear_sen2cor": 0.9674,
          "clear_s2cloudless": 1.0,
          "clear_threshold": 0.9904,
          "tile_cloud_cover": 3.0244
        },
        {
          "site": "ROI_00927",
          "date": "20200204",
          "true_clear": 0.1585,
          "clear_model": 0.1236,
          "clear_sen2cor": 0.0009,
          "clear_s2cloudless": 0.0841,
          "clear_threshold": 0.6572,
          "tile_cloud_cover": 62.3718
        },
        {
          "site": "ROI_00927",
          "date": "20200325",
          "true_clear": 0.9578,
          "clear_model": 0.948,
          "clear_sen2cor": 0.9628,
          "clear_s2cloudless": 0.9705,
          "clear_threshold": 0.9725,
          "tile_cloud_cover": 19.9889
        }
      ],
      "reference": {
        "n_patches": 975,
        "rates": {
          "model": {
            "false_usable": [
              0.0899,
              0.0706,
              0.1094
            ],
            "false_unusable": [
              0.0535,
              0.035,
              0.0732
            ]
          },
          "unetmobv2_v2": {
            "false_usable": [
              0.0466,
              0.032,
              0.0622
            ],
            "false_unusable": [
              0.0374,
              0.0222,
              0.0528
            ]
          }
        }
      }
    },
    "note": "Sentinel-2 cloud model, held-out test (ADR 0013): cloudy windows wrongly counted as usable."
  },
  {
    "run_id": "s2-cloud-model-20261031T224123Z",
    "superseded": false,
    "created_at": "2026-10-31T22:41:24.338978+00:00",
    "report_id": "s2-cloud-model-20261031T224123Z-claim2",
    "gate": "s2_cloud_detections",
    "result": "pass",
    "metrics": {
      "n_sites": 217,
      "n_targets": 868,
      "n_plumes": 2131,
      "rates": {
        "none": {
          "cloud_caused_per_target": [
            21.9101,
            19.5229,
            24.1873
          ],
          "detection_share": [
            0.2454,
            0.2173,
            0.2738
          ]
        },
        "threshold": {
          "cloud_caused_per_target": [
            15.6532,
            13.7137,
            17.6305
          ],
          "detection_share": [
            0.2384,
            0.2071,
            0.2704
          ]
        },
        "sen2cor": {
          "cloud_caused_per_target": [
            12.2304,
            10.5667,
            13.9275
          ],
          "detection_share": [
            0.2013,
            0.1758,
            0.2285
          ]
        },
        "s2cloudless": {
          "cloud_caused_per_target": [
            12.6221,
            11.0313,
            14.233
          ],
          "detection_share": [
            0.2421,
            0.2129,
            0.2731
          ]
        },
        "model": {
          "cloud_caused_per_target": [
            8.28,
            7.1923,
            9.4578
          ],
          "detection_share": [
            0.2562,
            0.2268,
            0.2871
          ]
        }
      },
      "comparisons": {
        "none": {
          "cloud_caused_diff": [
            -13.6302,
            -15.3595,
            -11.9037
          ],
          "detection_share_diff": [
            0.0108,
            -0.0084,
            0.0293
          ],
          "passed": true
        },
        "threshold": {
          "cloud_caused_diff": [
            -7.3733,
            -8.749,
            -6.023
          ],
          "detection_share_diff": [
            0.0178,
            0.0,
            0.0349
          ],
          "passed": true
        },
        "sen2cor": {
          "cloud_caused_diff": [
            -3.9505,
            -5.0876,
            -2.812
          ],
          "detection_share_diff": [
            0.0549,
            0.0376,
            0.0736
          ],
          "passed": true
        },
        "s2cloudless": {
          "cloud_caused_diff": [
            -4.3422,
            -5.3018,
            -3.3718
          ],
          "detection_share_diff": [
            0.0141,
            0.0,
            0.0291
          ],
          "passed": true
        }
      },
      "amplitude": 0.12,
      "reference": {
        "model": {
          "cloud_caused_per_target": [
            8.1438,
            7.0179,
            9.4135
          ],
          "detection_share": [
            0.2603,
            0.2291,
            0.2949
          ]
        },
        "unetmobv2_v2": {
          "cloud_caused_per_target": [
            3.6762,
            3.1372,
            4.2916
          ],
          "detection_share": [
            0.2918,
            0.2586,
            0.3278
          ]
        }
      }
    },
    "note": "Sentinel-2 cloud model, held-out test (ADR 0013): false detections caused by clouds."
  }
];

// The method checks are the project's real ones; their numbers come from reports/validation.
const validation_results = PUBS.flatMap((pub) => [
  ...CLOUD_MODEL_CHECKS.map((r) => ({ publish_id: pub.publish_id, ...r })),
  { publish_id: pub.publish_id, report_id: 'synthetic-20261003T223204Z', gate: 'gate3', run_id: 'synthetic-20261003T223204Z', result: 'pass', metrics: { coverage_f: 0.91, coverage_qbar: 0.9, coverage_e: 0.895, diag_fail_frac: 0.07, replicates: 200, sites: 10, target: [0.85, 0.95] }, superseded: false, note: 'Gate 3: 90% ranges contain the simulated truth 85 to 95% of the time.', created_at: '2026-10-03T22:32:04Z' },
  { publish_id: pub.publish_id, report_id: 'synthetic-20261024T013708Z', gate: 'gate3', run_id: 'synthetic-20261024T013708Z', result: 'pass', metrics: { coverage_f: 0.898, coverage_qbar: 0.888, coverage_e: 0.889, diag_fail_frac: 0.045, replicates: 200, sites: 10, target: [0.85, 0.95], covariates: ['closed', 'log_area'] }, superseded: false, note: 'Gate 3 with site covariates.', created_at: '2026-10-24T01:37:08Z' },
  { publish_id: pub.publish_id, report_id: 'holdout-synthetic-20261004T001513Z', gate: 'holdout', run_id: 'holdout-synthetic-20261004T001513Z', result: 'pass', metrics: { share_inside: 0.98, folds: 50, target: 0.8 }, superseded: false, note: 'Dry run on simulated data, not Gate 4.', created_at: '2026-10-04T00:15:13Z' },
  { publish_id: pub.publish_id, report_id: 'repair-synthetic-20261003T234738Z-placebo', gate: 'placebo', run_id: 'repair-synthetic-20261003T234738Z', result: 'dry-run', metrics: { false_positive_rate: 0.02, wilson: [0.007, 0.056], fits: 153, worlds: 40, threshold: 0.1, call_probability: 0.975 }, superseded: false, note: 'Dry run on simulated data, not Gate 5.', created_at: '2026-10-03T23:47:38Z' },
  { publish_id: pub.publish_id, report_id: 'repair-synthetic-20261003T234738Z-power', gate: 'power', run_id: 'repair-synthetic-20261003T234738Z', result: 'dry-run', metrics: { p_drop_by_factor: { '0.1': 0.214, '0.25': 0.429, '0.5': 0.143, '0.75': 0 }, target: 0.8 }, superseded: false, note: 'No tested drop reached 80% power; a 90% drop was called in 21% of fits.', created_at: '2026-10-03T23:47:38Z' },
  { publish_id: pub.publish_id, report_id: 'repair-synthetic-20261003T232115Z-placebo', gate: 'placebo', run_id: 'repair-synthetic-20261003T232115Z', result: 'dry-run', metrics: { false_positive_rate: 0.129, wilson: [0.084, 0.193], fits: 147 }, superseded: true, note: 'Earlier call rule (90% interval excludes 0); superseded by ADR 0006.', created_at: '2026-10-03T23:21:15Z' },
]);

const update_log = [
  { publish_id: 'fixture-public-0001', item_order: 1, kind: 'new-model-run', site_id: null, event_date: '2026-10-01', count: null, text: 'First sample model run published.', data_through: '2026-09-01' },
  { publish_id: 'fixture-public-0001', item_order: 2, kind: 'note', site_id: null, event_date: '2026-10-01', count: null, text: 'Site outlines are provisional 500 m circles around the CalRecycle reference points.', data_through: '2026-09-01' },
  { publish_id: 'fixture-review-0002', item_order: 1, kind: 'new-plumes', site_id: 'newby-island', event_date: '2026-09-18', count: 3, text: 'Three new plumes near Newby Island in September 2026.', data_through: '2026-09-20' },
  { publish_id: 'fixture-review-0002', item_order: 2, kind: 'new-record', site_id: 'sonoma-central', event_date: '2026-09-25', count: 1, text: 'One Air District record added for Sonoma Central.', data_through: '2026-09-20' },
];

const snapshot = {
  about: 'Sample data in the shape of the publishing database. Not real results. Made by fixtures/make-fixture.mjs.',
  publications: PUBS,
  runs: RUNS,
  data_terms: DATA_TERMS,
  boundaries: [],
  sites,
  neighbours,
  passes: [...gen1.passes, ...gen2.passes],
  plumes: [...gen1.plumes, ...gen2.plumes],
  site_estimates,
  checks,
  check_results,
  operator_reports,
  population,
  site_features,
  validation_results,
  update_log,
};

const out = path.join(here, 'snapshot.json');
await writeFile(out, JSON.stringify(snapshot));
console.log(`make-fixture: wrote ${path.relative(process.cwd(), out)} with ${snapshot.passes.length} passes and ${snapshot.plumes.length} plumes`);
