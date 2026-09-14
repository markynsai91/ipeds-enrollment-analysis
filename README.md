# IPEDS Enrollment Analysis

A data pipeline and analytical model built on US federal higher education
enrollment data. Built as a portfolio project demonstrating data profiling,
SQL modelling, and analytics engineering practice.

## Project goal

Take raw IPEDS survey files, understand their structure and quality issues,
model them into a clean dimensional layer, and surface enrollment trends
across US institutions. The final deliverable is a dbt project on a cloud
warehouse with a dashboard on top.

## Data source

[IPEDS Data Center](https://nces.ed.gov/ipeds/datacenter/DataFiles.aspx),
National Center for Education Statistics.

Two survey components, three years each (2022, 2023, 2024):

| File | Contents | Grain |
|---|---|---|
| EF*A | Fall enrollment by level, race/ethnicity, gender | One row per institution per enrollment level |
| HD* | Institution directory: name, state, sector, status | One row per institution |

**Scale:** EF2024A contains 113,833 rows across 73 columns.

**Join:** `UNITID`. Primary key in HD, foreign key in EF.

Raw files are not committed to this repository. Download them from the link
above and place them in `raw/`.

## Data quality findings

Four issues were identified during profiling. Each was verified against the
data rather than assumed.

### 1. Hierarchical totals stored as rows

`EFALEVEL` encodes a hierarchy where parent totals and their components sit
in the same column as sibling rows.

- Code 1 (All students) = code 2 (Undergraduate) + code 12 (Graduate)
- Code 1 = code 21 (Full-time) + code 41 (Part-time)

A single student can appear in up to eight rows.

**Impact:** a naive `SUM(EFTOTLT)` over EF2024A returns **167,193,812**
students. Filtering to `EFALEVEL = 1` returns **20,357,226**, an overcount
factor of roughly **8.2x**. The filtered figure is consistent with published
national enrollment of approximately 20 million.

### 2. Imputed values are indistinguishable from reported ones

34 of the 73 columns are imputation flags. Each measure column has a paired
`X` column recording whether the value was reported by the institution or
estimated by NCES.

In EF2024A: 113,648 rows flagged `R` (reported), 167 flagged `P` (imputed),
18 flagged `N` (not applicable).

**Verified:** UNITID 152044 was imputed in both 2023 and 2024, with values of
85 and 80 respectively. Imputed figures change year to year rather than being
carried forward unchanged, so they are visually identical to real enrolment
movement in any trend chart.

**Impact:** the flag columns are the only signal distinguishing real data from
estimates. They must be carried into the model, not dropped as noise.

### 3. The institution dimension changes over time

HD contains `CYACTIVE`, `DEATHYR`, and `CLOSEDAT`. Institutions close, merge,
and change sector or name between survey years.

**Impact:** joining a multi-year fact table to a single HD snapshot either
drops institutions that have since closed, or retroactively applies current
attributes to historical rows. This is a slowly changing dimension problem
requiring an explicit snapshot strategy.

### 4. Percent-change rankings surface reporting artifacts

Ranking institutions by year-over-year percent change returns data events,
not enrollment trends.

**Verified:** Illinois Eastern Community Colleges (UNITID 145707) shows
869 → 880 → 3,726 students across 2022 to 2024. A 1.3% change followed by a
323% change is characteristic of a reporting or consolidation change rather
than growth.

**Impact:** any ranked change analysis needs a multi-year consistency check
and an absolute-magnitude floor, not just a size threshold.

## Analysis completed

- National enrollment totals with correct hierarchy handling
- Institution concentration: no single institution exceeds 1.1% of US
  enrollment, indicating a highly fragmented market
- Year-over-year change by institution using window functions, with
  reported-only filtering and a minimum-size threshold
- Top and bottom movers, with artifact identification

## Modelling decisions

Open, to be resolved in the modelling phase:

- **EFALEVEL totals:** filter to a single level, or model the hierarchy with
  an explicit `is_total` flag and level attributes
- **Imputed rows:** exclude, or include with an `is_imputed` flag exposed to
  downstream consumers
- **Institution dimension:** Type 1 (current attributes only) or Type 2
  (versioned with validity dates)

## Stack

- **DuckDB** for querying raw CSVs directly, no warehouse required
- **Python / Jupyter** for orchestration and exploration
- **Planned:** BigQuery, dbt, Tableau

## Running it

```bash
pip install duckdb pandas
```

Place the IPEDS CSVs in `raw/`, then open `IPEDS_PROJECT.ipynb`.

Queries reference files directly:

```python
duckdb.sql("SELECT COUNT(*) FROM 'raw/ef2024a.csv'").df()
```

## Roadmap

- [x] Source and profile raw data
- [x] Identify and quantify data quality issues
- [x] Exploratory analysis with SQL window functions
- [ ] Python ingestion layer
- [ ] Load to BigQuery
- [ ] dbt models with tests and documentation
- [ ] Dimensional model
- [ ] Tableau dashboard