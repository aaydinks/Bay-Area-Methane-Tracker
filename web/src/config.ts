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

export const EXPECTED = {
  publication: 'Nothing has been published yet. The first data update is expected in November 2026.',
  estimates:
    'Estimates appear after the first model fit on real data, which needs the detection curves for each instrument to be confirmed.',
  checks:
    'Results appear as dated records arrive from the Air District and operators. Requests were filed in October 2026 and responses can take 45 days or more.',
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

export const CHECK_TYPE: Record<string, { label: string; icon: string }> = {
  'air-district-inspection': { label: 'Air District inspection', icon: 'clipboard' },
  'air-district-notice': { label: 'Air District notice', icon: 'document' },
  'operator-repair': { label: 'Operator repair', icon: 'wrench' },
  'carb-plume-notice': { label: 'CARB plume notice', icon: 'satellite' },
  other: { label: 'Other record', icon: 'dot' },
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
