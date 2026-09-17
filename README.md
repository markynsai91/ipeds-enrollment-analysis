# IPEDS Enrollment Analysis

A data pipeline and analytical model built on US federal higher education
enrollment data. Built as a portfolio project demonstrating data profiling,
ingestion, SQL modelling, and analytics engineering practice.

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

## Pipeline


`ingest.py` reads the raw files and writes two clean tables. Every cleaning
rule in it comes from a documented finding below.

**processed/enrollment.parquet** — 17,733 rows

| Column | Description |
|---|---|
| unitid | Institution identifier |
| year | Survey year |
| total_enrollment | Total students |
| is_imputed | True if the figure was estimated by NCES rather than reported |

**processed/institutions.parquet** — 18,491 rows

| Column | Description |
|---|---|
| unitid | Institution identifier |
| year | Survey year |
| institution_name | Institution name |
| state | State abbreviation |

Output is parquet rather than CSV to preserve data types and reduce size.
Three source CSVs totalling roughly 57 MB become two parquet files under
200 KB.

## Data quality findings

Six issues were identified during profiling and ingestion. Each was verified
against the data rather than assumed.

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

**Handled by:** filtering to `EFALEVEL = 1` in `ingest.py`.

### 2. Imputed values are indistinguishable from reported ones

34 of the 73 EF columns are imputation flags. Each measure column has a
paired `X` column recording whether the value was reported by the institution
or estimated by NCES.

In EF2024A: 113,648 rows flagged `R` (reported), 167 flagged `P` (imputed),
18 flagged `N` (not applicable).

**Verified:** UNITID 152044 was imputed in both 2023 and 2024, with values of
85 and 80 respectively. Imputed figures change year to year rather than being
carried forward unchanged, so they are visually identical to real enrollment
movement in any trend chart.

**Handled by:** carrying the flag through as a boolean `is_imputed` column so
downstream queries can exclude or footnote estimated values.

### 3. The institution dimension changes over time

HD contains `CYACTIVE`, `DEATHYR`, and `CLOSEDAT`. Institutions close, merge,
and change sector or name between survey years. The column set also differs
between years, so stacking three years of HD produces more columns than any
single file contains.

**Impact:** joining a multi-year fact table to a single HD snapshot either
drops institutions that have since closed, or retroactively applies current
attributes to historical rows. This is a slowly changing dimension problem
requiring an explicit snapshot strategy.

**Currently handled by:** keeping one institution row per year and joining on
both `unitid` and `year`. A formal SCD approach is deferred to the modelling
phase.

### 4. Percent-change rankings surface reporting artifacts

Ranking institutions by year-over-year percent change returns data events,
not enrollment trends.

**Verified:** Illinois Eastern Community Colleges (UNITID 145707) reported
869 students in 2022, 880 in 2023, and 3,726 in 2024. A 1.3% change followed
by a 323% change is characteristic of a reporting or consolidation change
rather than growth.

**Impact:** any ranked change analysis needs a multi-year consistency check
and an absolute-magnitude floor, not just a size threshold.

### 5. HD files are latin-1 encoded

Institution names contain accented characters written in latin-1, not UTF-8.
Reading them with default settings raises
`UnicodeDecodeError: invalid continuation byte`.

**Handled by:** `encoding='latin-1'` on the HD reads. The EF files are
numeric and read fine as UTF-8.

### 6. A byte-order mark silently breaks the join key

HD2023 and HD2024 begin with a UTF-8 byte-order mark. Read as latin-1, those
three bytes become visible characters attached to the first column name, so
the column parses as `ï»¿UNITID` rather than `UNITID`.

**Impact, and why this one matters most:** `pd.concat` treats the two spellings
as different columns and stacks them side by side rather than on top of each
other. Every 2023 and 2024 row then has a null in `UNITID`. Pandas converts
the column to float to hold the nulls, so the join key becomes a DOUBLE while
the enrollment key stays BIGINT. The resulting join returns 5,978 rows instead
of roughly 17,000, silently dropping two thirds of the data. No error is
raised at any point.

**Found by:** counting rows on each side of the join, counting the join
itself, then inspecting column types with `DESCRIBE`. The row counts on each
side were correct, which localised the fault to the join keys.

**Handled by:** stripping the byte-order mark and surrounding whitespace from
column names immediately after each read.

## Analysis completed

**National totals with correct hierarchy handling.** 20,357,226 students in
2024, filtered to `EFALEVEL = 1`.

**Institution concentration.** No single institution exceeds 1.1% of US
enrollment, indicating a highly fragmented market.

**Largest institutions, 2024, reported figures only.** The top of the list is
dominated by online-first institutions: Western Governors (210,208), Southern
New Hampshire (189,531), Grand Canyon (113,257), University of Phoenix
(111,248). The first traditional campus appears at position seven.

**Year-over-year change by institution.** Built as a layered query:

- Multi-file read across three years using DuckDB's glob syntax, with the
  survey year extracted from the source filename
- Aggregation filtered to reported values only and to the top-level
  enrollment code
- `LAG()` partitioned by institution and ordered by year
- A CTE wrapping the window layer so calculated change columns can be
  filtered in an outer query
- `UNION ALL` between two branches returning the ten fastest growers and the
  ten steepest declines in one result, with a direction label
- A minimum prior-year enrollment threshold to exclude small-institution noise

## Modelling decisions

Open, to be resolved in the modelling phase:

- **EFALEVEL totals:** filter to a single level, or model the hierarchy with
  an explicit `is_total` flag and level attributes
- **Imputed rows:** exclude, or include with the flag exposed to downstream
  consumers
- **Institution dimension:** Type 1 (current attributes only) or Type 2
  (versioned with validity dates)

## Stack

- **Python / Pandas** for ingestion
- **DuckDB** for querying parquet and CSV directly, no warehouse required
- **Git** for version control
- **Planned:** dbt, BigQuery, Tableau

## Running it

```bash
pip install pandas pyarrow duckdb
```

Place the IPEDS CSVs in `raw/`, then:

```bash
python3 ingest.py
```

This writes `processed/enrollment.parquet` and
`processed/institutions.parquet`. Query them directly:

```python
import duckdb
duckdb.sql("SELECT COUNT(*) FROM 'processed/enrollment.parquet'").df()
```

## Roadmap

- [x] Source and profile raw data
- [x] Identify and quantify data quality issues
- [x] Exploratory analysis with SQL window functions and CTEs
- [x] Version control and public repository
- [x] Python ingestion layer producing clean typed outputs
- [ ] dbt models with tests and documentation
- [ ] Load to BigQuery
- [ ] Dimensional model with an explicit SCD strategy
- [ ] Tableau dashboard