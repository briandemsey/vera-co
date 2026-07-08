"""
Build a slim SQLite for Render deployment.

Source: F:\\VERA\\vera-co\\data\\vera_co.sqlite (646 MB full warehouse)
Target: F:\\VERA\\vera-co-repo\\vera_co.sqlite (~30 MB)

Keeps every table the app queries, but:
  - District-level rows only (drops school-level from CMAS + disagg)
  - Drops cmas_disagg subgroups the app doesn't use in the current 5 pages
  - Keeps all 184 districts, all subjects, all grades, current+one prior year for trend charts
  - Keeps every ACCESS district row (small)
"""
import os, sqlite3, shutil

SRC = r"F:\VERA\vera-co\data\vera_co.sqlite"
DST = r"F:\VERA\vera-co-repo\vera_co.sqlite"

if os.path.exists(DST):
    os.remove(DST)

# Fastest: copy the schema by attaching source and CREATE TABLE ... AS SELECT
conn = sqlite3.connect(DST)
cur = conn.cursor()
cur.execute("ATTACH DATABASE ? AS src", (SRC,))

TABLES = [
    # cmas_district_school: keep DISTRICT and STATE only (drop 16K SCHOOL rows)
    ("cmas_district_school",
     "SELECT * FROM src.cmas_district_school WHERE level IN ('DISTRICT','STATE')"),

    # cmas_disagg: DISTRICT-level rows only (drops schools). Note: this table stores 'District' not 'DISTRICT'.
    ("cmas_disagg",
     "SELECT * FROM src.cmas_disagg WHERE UPPER(level) IN ('DISTRICT','STATE') "
     "AND subgroup_type IN ('Language Proficiency','Gender','Free Reduced Lunch','Race Ethnicity','IEP')"),

    # dpf_district: full copy (184 rows, tiny)
    ("dpf_district",
     "SELECT * FROM src.dpf_district"),

    # spf_school: full copy (1833 rows, small)
    ("spf_school",
     "SELECT * FROM src.spf_school"),

    # enrollment_ipst_school: latest year only for Overview
    ("enrollment_ipst_school",
     "SELECT * FROM src.enrollment_ipst_school WHERE school_year IN ('2024-2025','2023-2024')"),

    # outcomes_grad_district: latest 2 years for Overview
    ("outcomes_grad_district",
     "SELECT * FROM src.outcomes_grad_district WHERE cohort_year IN ('2024-2025','2023-2024')"),

    # assessment_access_summary: all district+state rows (schools dropped)
    ("assessment_access_summary",
     "SELECT * FROM src.assessment_access_summary WHERE level IN ('DISTRICT','STATE')"),

    # files_ingested: keep for provenance
    ("files_ingested",
     "SELECT * FROM src.files_ingested"),
]

for name, select_sql in TABLES:
    print(f"Creating {name}...", flush=True)
    cur.execute(f"CREATE TABLE {name} AS {select_sql}")
    n = cur.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
    print(f"  {n:,} rows")

# Recreate indexes that app queries need
print("\nCreating indexes...", flush=True)
cur.executescript("""
CREATE INDEX ix_cmas_dist ON cmas_district_school(district_code, content, grade);
CREATE INDEX ix_disagg_dist ON cmas_disagg(district_code, subject, subgroup_type);
CREATE INDEX ix_ipst_dist  ON enrollment_ipst_school(district_code, school_year);
CREATE INDEX ix_grad_dist  ON outcomes_grad_district(district_code, cohort_year);
CREATE INDEX ix_access_dist ON assessment_access_summary(district_code, school_year, grade_cluster);
CREATE INDEX ix_dpf_code ON dpf_district(district_code);
CREATE INDEX ix_spf_code ON spf_school(district_code, school_code);
""")

conn.commit()
cur.execute("DETACH DATABASE src")
conn.execute("VACUUM")
conn.close()

size = os.path.getsize(DST)
print(f"\n=== SLIM DB READY ===")
print(f"Path: {DST}")
print(f"Size: {size:,} bytes ({size/1024/1024:.1f} MB)")
