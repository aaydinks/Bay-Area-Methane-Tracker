# US EPA Greenhouse Gas Reporting Program

| File | Contents |
|---|---|
| `emissions_by_subpart_gas.csv` | Every row Envirofacts returns for the four crosswalked facilities: `facility_id`, `sub_part_id`, `gas_id`, `co2e_emission` (t CO2e, as published), `year` |
| `facilities_2023.csv` | The 17 Bay Area facilities that reported subpart HH (municipal landfills) for 2023, with EPA's latitude and longitude |
| `pulls/` | Manifest of the download |

Facilities: Newby Island 1006179, Sonoma Central 1004123, Potrero Hills 1007345 (2010 to
2023), Shoreline 1005910 (2010 to 2018). No Acme Fill record was found. Subpart HH is
`sub_part_id` 31 and methane is `gas_id` 2; the other rows are subpart C (combustion).
Envirofacts has no reports for 2024 or 2025 yet (checked 2026-10-17).

**Units.** Emissions are published in tonnes of CO2-equivalent. Converting back to tonnes
of methane needs the warming factor (GWP) EPA used for each year; that lives in
`config/impact.yaml` and is still unconfirmed, so this table keeps EPA's own numbers.

**Source:** Envirofacts REST API (`data.epa.gov/efservice`), tables `pub_dim_facility`
and `pub_facts_subp_ghg_emission`. No key.

**Terms and credit:** US government public data. "US EPA Greenhouse Gas Reporting
Program, accessed via Envirofacts."
