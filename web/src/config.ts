// Fixed text and labels. Anything that is a figure comes from the published snapshot, never
// from here.

export const SITE_NAME = 'Bay Area Landfill Methane Watch';
export const SHORT_NAME = 'Methane Watch';
export const TAGLINE = 'A retrospective tracker of landfill methane, built from public satellite and aircraft data.';
export const FRAMING =
  'Every result is a screening indication for investigation. Nothing here is a compliance finding, live monitoring or a health claim.';

export const NAV = [
  { href: '/', label: 'Home' },
  { href: '/map/', label: 'Map' },
  { href: '/checks/', label: 'Checks' },
  { href: '/sites/', label: 'Landfills' },
  { href: '/updates/', label: 'Updates' },
  { href: '/methods/', label: 'Methods' },
  { href: '/how-to-read/', label: 'How to read' },
  { href: '/data/', label: 'Data' },
] as const;

// Region names as config/project.yaml gives them; tests/test_web_regions.py keeps the two in step.
// The order here is the order the pages list them in.
export const REGION: Record<string, string> = {
  'bay-area': 'Bay Area',
  'north-valley': 'North Valley',
};

// How closely a landfill is followed (the registry's tier).
export const TIER: Record<string, string> = {
  pilot: 'Studied in depth',
  screen: 'Screened',
};

export const EXPECTED = {
  publication: 'Nothing has been published yet. The first data update is expected in November 2026.',
  estimates:
    'An estimate appears once a landfill is part of a model fit and has enough usable passes for one.',
  checks:
    'Results appear as dated records arrive from regulators and operators. The first requests were filed in October 2026 and responses can take 45 days or more.',
  plumes: 'Plume and pass counts appear with the first published data update.',
  updates: 'The update log starts with the first published data update.',
  operator: 'Operator-reported figures appear once the EPA records are loaded for this site.',
};

export type ResultColour = 'red' | 'orange' | 'yellow' | 'green' | 'grey';

export const RESULT: Record<ResultColour, { label: string; icon: string }> = {
  red: { label: 'Severe increase, strong evidence', icon: 'triangle' },
  orange: { label: 'Moderate increase, strong evidence', icon: 'diamond' },
  yellow: { label: 'Increase, small or uncertain', icon: 'circle' },
  green: { label: 'No increase indicated', icon: 'down' },
  grey: { label: 'Not enough data', icon: 'ring' },
};

// Landfills fall under several air districts (ADR 0020), so a record's label names its own:
// `label` follows the regulator's name, as in "Bay Area AQMD inspection". `checkLabel` in
// lib/data.ts builds it; the full text here is used when the district is not known.
export const CHECK_TYPE: Record<string, { label: string; icon: string; record?: string }> = {
  'air-district-inspection': { label: 'Air district inspection', icon: 'clipboard', record: 'inspection' },
  'air-district-notice': { label: 'Air district notice', icon: 'document', record: 'notice' },
  'operator-repair': { label: 'Operator repair', icon: 'wrench' },
  'carb-plume-notice': { label: 'CARB plume notice', icon: 'satellite' },
  other: { label: 'Other record', icon: 'dot' },
};

// Air districts by the name CARB's district outlines give them (the name a site carries), with
// the name CARB's list of districts uses (ww2.arb.ca.gov/california-air-districts, read
// 2026-11-23). tests/test_web_regions.py checks every key is a name in those outlines.
export const AIR_DISTRICT: Record<string, string> = {
  'Bay Area': 'Bay Area AQMD',
  'Northern Sonoma': 'Northern Sonoma County APCD',
  'Sacramento Metro': 'Sacramento Metro AQMD',
  'San Joaquin Valley Unified': 'San Joaquin Valley APCD',
  'Yolo-Solano': 'Yolo-Solano AQMD',
};

export const EVIDENCE: Record<string, string> = {
  strong: 'strong evidence',
  weak: 'weak evidence',
  none: 'not enough data',
};

export const INSTRUMENT: Record<string, string> = {
  emit: 'NASA EMIT',
  sentinel2: 'Sentinel-2',
  tanager1: 'Tanager-1',
  aircraft: 'Aircraft',
};

export const SOURCE_LABEL: Record<string, string> = {
  'emit-v2': 'NASA EMIT',
  's2-local': 'Sentinel-2',
  carbonmapper: 'Carbon Mapper',
};

export const DATE_CONFIDENCE: Record<string, string> = {
  exact: 'exact date',
  week: 'to the week',
  month: 'to the month',
};
