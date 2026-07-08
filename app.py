"""
VERA-CO: Verification Engine for Results & Accountability - Colorado

Real data from the Colorado Department of Education (CDE):
  - CMAS (Colorado Measures of Academic Success) - district+school, all grades, all subjects
  - ACCESS for ELLs summary - district+school+state, WIDA proficiency levels + redesignation
  - DPF / SPF (District/School Performance Frameworks)
  - Enrollment (IPST: SPED, EL, homeless, gifted, immigrant, migrant)
  - Graduation and dropout rates
  - Growth (Median Growth Percentiles)

H-EDU.Solutions | https://h-edu.solutions
"""

import os
import sqlite3
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ============================================================================
# CONFIGURATION
# ============================================================================

CO_BLUE = "#002868"
CO_RED  = "#C8102E"
CO_GOLD = "#CFB87C"

# Resolve DB path: same directory as app.py, or override via env var.
DEFAULT_DB = Path(__file__).parent / "vera_co.sqlite"
DB_PATH = Path(os.environ.get("VERA_CO_DB", DEFAULT_DB))

# Local dev fallback: use the full warehouse on F: if the bundled DB is missing.
if not DB_PATH.exists():
    dev_db = Path(r"F:\VERA\vera-co\data\vera_co.sqlite")
    if dev_db.exists():
        DB_PATH = dev_db


# ============================================================================
# DATA ACCESS
# ============================================================================

@st.cache_resource
def get_conn():
    return sqlite3.connect(str(DB_PATH), check_same_thread=False)


@st.cache_data(ttl=3600)
def load_districts():
    """All Colorado districts with 2025 enrollment, EL count, SPF rating, and graduation rate."""
    conn = get_conn()

    # Backbone: DPF for the full district list + 2025 rating and points
    q = """
    SELECT
        d.district_code               AS district_id,
        d.district_name,
        d.region,
        d.setting,
        d.rating_2025_final           AS spf_rating,
        d.points_2025                 AS spf_points,

        e.pk12_count                  AS total_students,
        e.el_count,
        e.el_pct                      AS el_percent,
        e.sped_count,
        e.sped_pct,
        e.homeless_count,
        e.gt_count

    FROM dpf_district d
    LEFT JOIN (
        SELECT district_code,
               SUM(pk12_count)  AS pk12_count,
               SUM(el_count)    AS el_count,
               AVG(el_pct)      AS el_pct,
               SUM(sped_count)  AS sped_count,
               AVG(sped_pct)    AS sped_pct,
               SUM(homeless_count) AS homeless_count,
               SUM(gt_count)    AS gt_count
        FROM enrollment_ipst_school
        WHERE school_year = '2024-2025'
        GROUP BY district_code
    ) e ON e.district_code = d.district_code
    ORDER BY d.district_name
    """
    df = pd.read_sql_query(q, conn)

    # Convert EL/SPED percentages: CDE stores as decimals (0.271) or percentages depending on year
    # For the 2024-2025 file they are decimals. Normalize to percent (0-100).
    for col in ("el_percent", "sped_pct"):
        if col in df.columns:
            # If mean value looks like a fraction (<=1), scale up. Guard NaN.
            m = df[col].dropna().mean() if df[col].notna().any() else 0
            if m and m <= 1.5:
                df[col] = df[col] * 100

    # Latest available graduation rate per district
    grad_q = """
    SELECT district_code, all_grad_rate
    FROM outcomes_grad_district
    WHERE cohort_year IN ('2024-2025','2023-2024')
      AND source_sheet LIKE '%District%'
    """
    grad = pd.read_sql_query(grad_q, conn)
    # Parse '78.9%' -> 78.9
    def _pct_to_float(x):
        if x is None: return None
        s = str(x).strip().replace('%','')
        try: return float(s)
        except: return None
    grad["graduation_rate"] = grad["all_grad_rate"].apply(_pct_to_float)
    grad_agg = grad.groupby("district_code", as_index=False)["graduation_rate"].max()
    df = df.merge(grad_agg, left_on="district_id", right_on="district_code", how="left").drop(columns=["district_code"])

    return df


@st.cache_data(ttl=3600)
def load_cmas_row(district_id: str, subject: str, grade: str):
    """One row of CMAS results for a district+subject+grade."""
    conn = get_conn()
    q = """
    SELECT district_name, content, grade, mean_scale_score, participation_rate,
           pct_did_not_yet_meet, pct_partially_met, pct_approached, pct_met, pct_exceeded,
           pct_met_or_exceeded, num_valid_scores, num_total_records
    FROM cmas_district_school
    WHERE level = 'DISTRICT'
      AND district_code = ?
      AND content       = ?
      AND grade         = ?
    """
    return pd.read_sql_query(q, conn, params=[district_id, subject, grade])


@st.cache_data(ttl=3600)
def load_cmas_all_grades(district_id: str, subject: str):
    conn = get_conn()
    q = """
    SELECT grade, mean_scale_score, participation_rate, pct_met_or_exceeded, num_valid_scores
    FROM cmas_district_school
    WHERE level = 'DISTRICT' AND district_code = ? AND content = ?
      AND grade IN ('03','04','05','06','07','08','All Grades')
    ORDER BY grade
    """
    return pd.read_sql_query(q, conn, params=[district_id, subject])


@st.cache_data(ttl=3600)
def load_access_row(district_id: str, grade_cluster: str, school_year: str = "2024-2025"):
    conn = get_conn()
    q = """
    SELECT district_name, grade_cluster, num_valid_scores, mean_scale_score,
           num_level_1, pct_level_1,
           num_level_2, pct_level_2,
           num_level_3, pct_level_3,
           num_level_4, pct_level_4,
           num_level_5_6, pct_level_5_6,
           num_redesignation_eligible, pct_redesignation_eligible
    FROM assessment_access_summary
    WHERE level = 'DISTRICT'
      AND district_code = ?
      AND grade_cluster = ?
      AND school_year   = ?
    """
    return pd.read_sql_query(q, conn, params=[district_id, grade_cluster, school_year])


@st.cache_data(ttl=3600)
def load_access_grade_clusters(district_id: str, school_year: str = "2024-2025"):
    conn = get_conn()
    q = """
    SELECT DISTINCT grade_cluster
    FROM assessment_access_summary
    WHERE level='DISTRICT' AND district_code=? AND school_year=?
    ORDER BY CASE grade_cluster
        WHEN 'All Grades' THEN 0
        WHEN 'K'          THEN 1
        WHEN '1'          THEN 2
        WHEN '2-3'        THEN 3
        WHEN '4-5'        THEN 4
        WHEN '6-8'        THEN 5
        WHEN '9-12'       THEN 6
        ELSE 7 END
    """
    return pd.read_sql_query(q, conn, params=[district_id, school_year])["grade_cluster"].tolist()


@st.cache_data(ttl=3600)
def available_access_years(district_id: str):
    conn = get_conn()
    q = """
    SELECT DISTINCT school_year FROM assessment_access_summary
    WHERE level='DISTRICT' AND district_code=?
    ORDER BY school_year DESC
    """
    return pd.read_sql_query(q, conn, params=[district_id])["school_year"].tolist()


@st.cache_data(ttl=3600)
def state_ela_gap_by_grade():
    """State-level CMAS ELA proficiency vs. state ACCESS Level 4+ percentage by grade.
    Used as an anchor for the honest Type 4 discussion at state level."""
    conn = get_conn()
    q = """
    SELECT grade, pct_met_or_exceeded
    FROM cmas_district_school
    WHERE level='STATE' AND content='English Language Arts'
      AND grade IN ('03','04','05','06','07','08')
    ORDER BY grade
    """
    return pd.read_sql_query(q, conn)


# ============================================================================
# PAGES
# ============================================================================

def render_overview(districts_df: pd.DataFrame):
    st.header("Colorado Education Overview")
    st.caption(
        "Data source: Colorado Department of Education public files (CMAS, DPF, IPST, graduation). "
        "184 districts, 2024-2025 school year."
    )

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Districts", f"{len(districts_df):,}")
    with col2:
        total = districts_df['total_students'].fillna(0).sum()
        st.metric("Students (PK-12, 2024-25)", f"{int(total):,}")
    with col3:
        el = districts_df['el_count'].fillna(0).sum()
        st.metric("English Learners", f"{int(el):,}")
    with col4:
        pts = districts_df['spf_points'].dropna().mean()
        # CDE stores DPF points earned as a decimal (0.527 = 52.7%). Display as percentage.
        st.metric("Avg 2025 DPF % Earned", f"{pts * 100:.1f}%" if pd.notna(pts) else "n/a")

    st.divider()
    st.subheader("Districts")

    display_df = districts_df.copy()
    display_df["EL %"]       = display_df["el_percent"].map(lambda x: f"{x:.1f}%" if pd.notna(x) else "")
    display_df["Grad Rate"]  = display_df["graduation_rate"].map(lambda x: f"{x:.1f}%" if pd.notna(x) else "")
    display_df["Students"]   = display_df["total_students"].map(lambda x: f"{int(x):,}" if pd.notna(x) else "")
    display_df["EL Count"]   = display_df["el_count"].map(lambda x: f"{int(x):,}" if pd.notna(x) else "")
    display_df["DPF % Earned"] = display_df["spf_points"].map(lambda x: f"{x*100:.1f}%" if pd.notna(x) else "")

    show = display_df[[
        "district_id","district_name","region","Students","EL Count","EL %","Grad Rate",
        "spf_rating","DPF % Earned"
    ]].rename(columns={
        "district_id":"District ID",
        "district_name":"District",
        "region":"Region",
        "spf_rating":"2025 DPF Rating",
    })
    st.dataframe(show, use_container_width=True, hide_index=True)

    st.subheader("English Learner Population by District (top 30)")
    top = districts_df.dropna(subset=["el_count"]).nlargest(30, "el_count")
    fig = px.bar(
        top.sort_values("el_count"),
        x="el_count", y="district_name",
        orientation="h",
        color="el_percent",
        color_continuous_scale=[[0, CO_GOLD], [0.5, CO_BLUE], [1, CO_RED]],
        labels={"el_count":"English Learners","district_name":"District","el_percent":"EL %"},
    )
    fig.update_layout(height=650, showlegend=False, coloraxis_colorbar=dict(title="EL %"))
    st.plotly_chart(fig, use_container_width=True)


def render_cmas_analysis(districts_df: pd.DataFrame):
    st.header("CMAS Assessment Analysis")
    st.caption("Colorado Measures of Academic Success. Source: 2025 CMAS district+school overall results (CDE).")

    st.markdown("""
    **CMAS** measures student achievement in English Language Arts, Mathematics, and Science aligned to Colorado
    Academic Standards. Five performance levels: Did Not Yet Meet, Partially Met, Approached, Met, Exceeded.
    """)

    col1, col2, col3 = st.columns(3)
    with col1:
        district_name = st.selectbox("District", options=districts_df["district_name"].tolist(), key="cmas_dist")
    with col2:
        subject = st.selectbox("Subject",
                               options=["English Language Arts","Mathematics","Science"],
                               key="cmas_subj")
    with col3:
        grade = st.selectbox("Grade",
                             options=["All Grades","03","04","05","06","07","08","11"],
                             key="cmas_grade")

    district_id = districts_df.loc[districts_df["district_name"] == district_name, "district_id"].values[0]

    df = load_cmas_row(district_id, subject, grade)
    if df.empty:
        st.warning(f"No CMAS data for {district_name} — {subject} — grade {grade}.")
        return

    row = df.iloc[0]

    st.divider()
    st.subheader(f"{district_name} — {subject} — Grade {grade}")

    c1, c2, c3, c4 = st.columns(4)
    with c1: st.metric("Tested (valid scores)", f"{int(row['num_valid_scores']):,}" if pd.notna(row['num_valid_scores']) else "n/a")
    with c2: st.metric("Mean Scale Score", f"{row['mean_scale_score']:.0f}" if pd.notna(row['mean_scale_score']) else "n/a")
    with c3: st.metric("Participation", f"{row['participation_rate']:.1f}%" if pd.notna(row['participation_rate']) else "n/a")
    with c4: st.metric("Met+Exceeded", f"{row['pct_met_or_exceeded']:.1f}%" if pd.notna(row['pct_met_or_exceeded']) else "n/a")

    st.subheader("Performance Distribution")

    is_science = (subject == "Science")
    if is_science:
        levels = ["Partially\nMet","Approached","Met","Exceeded"]
        values = [row.get("pct_partially_met"), row.get("pct_approached"),
                  row.get("pct_met"), row.get("pct_exceeded")]
        colors = ["#f57c00", CO_GOLD, CO_BLUE, CO_RED]
    else:
        levels = ["Did Not\nYet Meet","Partially\nMet","Approached","Met","Exceeded"]
        values = [row.get("pct_did_not_yet_meet"), row.get("pct_partially_met"),
                  row.get("pct_approached"), row.get("pct_met"), row.get("pct_exceeded")]
        colors = ["#d32f2f","#f57c00","#f9a825", CO_BLUE, CO_RED]

    fig = go.Figure(data=[go.Bar(
        x=levels, y=values,
        marker_color=colors,
        text=[f"{v:.1f}%" if pd.notna(v) else "n/a" for v in values],
        textposition="outside"
    )])
    fig.update_layout(
        title=f"CMAS {subject} — {district_name} — Grade {grade}",
        yaxis_title="Percentage of Students",
        height=420
    )
    st.plotly_chart(fig, use_container_width=True)

    st.subheader(f"Across Grades — {subject}")
    all_g = load_cmas_all_grades(district_id, subject)
    if not all_g.empty:
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(
            x=all_g["grade"], y=all_g["pct_met_or_exceeded"],
            mode="lines+markers",
            name="% Met or Exceeded",
            line=dict(color=CO_BLUE, width=3),
            marker=dict(size=10),
        ))
        fig2.update_layout(
            yaxis_title="% Met + Exceeded",
            xaxis_title="Grade",
            height=380
        )
        st.plotly_chart(fig2, use_container_width=True)


def render_access_analysis(districts_df: pd.DataFrame):
    st.header("ACCESS for ELLs Analysis")
    st.caption("WIDA ACCESS proficiency levels. Source: CDE ACCESS for ELLs District and School Summary files.")

    st.markdown("""
    **ACCESS for ELLs** is Colorado's annual English language proficiency assessment for multilingual learners.
    Six proficiency levels (1=Entering through 6=Reaching). Colorado is a WIDA consortium member state.
    """)

    st.info(
        "**Data note:** District-level Level 1-6 percentages and redesignation eligibility rates are published by CDE. "
        "Raw Speaking / Writing scale scores at the district level are not part of the public summary file — "
        "those require a CDE aggregate data request."
    )

    col1, col2 = st.columns(2)
    with col1:
        district_name = st.selectbox("District", options=districts_df["district_name"].tolist(), key="acc_dist")
    district_id = districts_df.loc[districts_df["district_name"] == district_name, "district_id"].values[0]

    years = available_access_years(district_id)
    with col2:
        if not years:
            st.warning(f"No ACCESS data available for {district_name}.")
            return
        year = st.selectbox("School year", options=years, key="acc_year")

    clusters = load_access_grade_clusters(district_id, year)
    if not clusters:
        st.warning(f"No grade clusters available for {district_name} in {year}.")
        return
    grade_cluster = st.selectbox("Grade cluster", options=clusters, key="acc_grade")

    df = load_access_row(district_id, grade_cluster, year)
    if df.empty:
        st.warning("No matching ACCESS row.")
        return
    row = df.iloc[0]

    st.divider()
    st.subheader(f"{district_name} — {grade_cluster} — {year}")

    c1, c2, c3 = st.columns(3)
    with c1: st.metric("Number of Valid Scores", f"{int(row['num_valid_scores']):,}" if pd.notna(row['num_valid_scores']) else "n/a")
    with c2: st.metric("Mean Scale Score", f"{row['mean_scale_score']:.0f}" if pd.notna(row['mean_scale_score']) else "n/a")
    with c3: st.metric("Eligible for Redesignation", f"{row['pct_redesignation_eligible']:.1f}%" if pd.notna(row['pct_redesignation_eligible']) else "n/a")

    st.subheader("WIDA Proficiency Level Distribution")
    labels = ["Level 1\nEntering","Level 2\nEmerging","Level 3\nDeveloping",
              "Level 4\nExpanding","Levels 5&6\nBridging/Reaching"]
    values = [row.get("pct_level_1"), row.get("pct_level_2"),
              row.get("pct_level_3"), row.get("pct_level_4"),
              row.get("pct_level_5_6")]
    colors = [CO_RED, "#f57c00","#f9a825", CO_BLUE, CO_GOLD]

    fig = go.Figure(data=[go.Bar(
        x=labels, y=values,
        marker_color=colors,
        text=[f"{v:.1f}%" if pd.notna(v) else "n/a" for v in values],
        textposition="outside"
    )])
    fig.update_layout(
        title=f"ACCESS Proficiency — {district_name} ({grade_cluster}, {year})",
        yaxis_title="% of Students",
        height=440
    )
    st.plotly_chart(fig, use_container_width=True)


def render_type4_detection(districts_df: pd.DataFrame):
    st.header("Type 4 Gap Detection")

    st.warning(
        "**Methodology note (2026-07-08):** Full Type 4 detection as originally scoped requires district-level "
        "ACCESS Speaking vs Writing scale scores, which CDE does not publish — that data requires a CDE aggregate "
        "data request. The interim analysis below uses two proxies that ARE public: (a) CMAS ELA proficiency "
        "compared for EL vs. non-EL students at the district level (from CMAS disaggregated files), and "
        "(b) ACCESS proficiency level distribution. This complements — it does not replace — READ Act and MTSS screening."
    )

    col1, col2 = st.columns(2)
    with col1:
        district_name = st.selectbox("District", options=districts_df["district_name"].tolist(), key="t4_dist")
    with col2:
        year = st.selectbox("School year", options=["2024-2025","2025-2026","2023-2024"], key="t4_year")
    district_id = districts_df.loc[districts_df["district_name"] == district_name, "district_id"].values[0]

    # Panel 1: CMAS ELA proficiency gap: EL vs non-EL
    conn = get_conn()
    q = """
    SELECT subgroup_value, pct_met_or_exceeded, num_valid_scores
    FROM cmas_disagg
    WHERE district_code=? AND subject='ELA' AND subgroup_type='Language Proficiency'
      AND grade='All Grades' AND UPPER(level)='DISTRICT'
    """
    ela_gap = pd.read_sql_query(q, conn, params=[district_id])

    st.subheader("CMAS ELA Proficiency by Language Status (District Level)")
    if ela_gap.empty:
        st.info("No CMAS ELA disaggregated data available for this district.")
    else:
        fig = go.Figure(data=[go.Bar(
            x=ela_gap["subgroup_value"],
            y=ela_gap["pct_met_or_exceeded"],
            marker_color=CO_BLUE,
            text=[f"{v:.1f}%" if pd.notna(v) else "" for v in ela_gap["pct_met_or_exceeded"]],
            textposition="outside"
        )])
        fig.update_layout(
            title=f"CMAS ELA Met+Exceeded — {district_name} — 2025",
            yaxis_title="% Met + Exceeded",
            height=400
        )
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(ela_gap, use_container_width=True, hide_index=True)

    # Panel 2: ACCESS Level distribution for the district
    st.subheader("ACCESS Proficiency Distribution (from Panel 1 above, cross-referenced)")
    q2 = """
    SELECT grade_cluster, num_valid_scores,
           pct_level_1, pct_level_2, pct_level_3, pct_level_4, pct_level_5_6,
           pct_redesignation_eligible
    FROM assessment_access_summary
    WHERE level='DISTRICT' AND district_code=? AND school_year=?
      AND grade_cluster='All Grades'
    """
    acc = pd.read_sql_query(q2, conn, params=[district_id, year])
    if acc.empty:
        st.info(f"No ACCESS data for {district_name} in {year}.")
    else:
        r = acc.iloc[0]
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        with c1: st.metric("EL Students Tested", f"{int(r['num_valid_scores']):,}" if pd.notna(r['num_valid_scores']) else "n/a")
        with c2: st.metric("Level 1", f"{r['pct_level_1']:.1f}%" if pd.notna(r['pct_level_1']) else "n/a")
        with c3: st.metric("Level 2", f"{r['pct_level_2']:.1f}%" if pd.notna(r['pct_level_2']) else "n/a")
        with c4: st.metric("Level 3", f"{r['pct_level_3']:.1f}%" if pd.notna(r['pct_level_3']) else "n/a")
        with c5: st.metric("Level 4+", f"{(r['pct_level_4'] or 0) + (r['pct_level_5_6'] or 0):.1f}%")
        with c6: st.metric("Redesignation Eligible", f"{r['pct_redesignation_eligible']:.1f}%" if pd.notna(r['pct_redesignation_eligible']) else "n/a")

    st.markdown("""
    ---
    **What this page currently shows (honest scope):**
    - CMAS ELA proficiency gap between EL and non-EL students — a district-level pattern signal.
    - ACCESS proficiency level distribution — the public equivalent of the oral/written gap analysis.

    **What full Type 4 gap detection would require:**
    - District-level ACCESS Speaking and Writing scale scores (available via CDE aggregate data request).
    - Once available, VERA-CO would compute the Speaking − Writing delta per grade and district
      and flag grade levels where the gap exceeds normal range.

    **Important limits:**
    - This is a district-level pattern signal, not an individual diagnosis.
    - Not a substitute for READ Act screening or MTSS processes.
    - Consult your district's SLP and multilingual services team for interpretation.
    """)


def render_export(districts_df: pd.DataFrame):
    st.header("Export Data")
    st.caption("Download real CDE public data for a district or the whole state.")

    col1, col2 = st.columns(2)
    with col1:
        district = st.selectbox("District (or All)", options=["All Districts"] + districts_df["district_name"].tolist())
    with col2:
        dataset = st.selectbox("Dataset", options=[
            "CMAS district results (all subjects/grades)",
            "CMAS disaggregated (subgroups)",
            "ACCESS summary (Levels 1-6)",
            "Enrollment (IPST: EL/SPED/homeless/gifted)",
            "Graduation rates",
            "DPF district ratings",
        ])

    conn = get_conn()
    where_district = ""
    params = []
    if district != "All Districts":
        district_id = districts_df.loc[districts_df["district_name"] == district, "district_id"].values[0]
        where_district = " AND district_code = ?"
        params = [district_id]

    if dataset.startswith("CMAS district"):
        q = "SELECT * FROM cmas_district_school WHERE level='DISTRICT'" + where_district
    elif dataset.startswith("CMAS disagg"):
        q = "SELECT * FROM cmas_disagg WHERE UPPER(level)='DISTRICT'" + where_district
    elif dataset.startswith("ACCESS"):
        q = "SELECT * FROM assessment_access_summary WHERE level='DISTRICT'" + where_district
    elif dataset.startswith("Enrollment"):
        q = "SELECT * FROM enrollment_ipst_school WHERE 1=1" + where_district
    elif dataset.startswith("Graduation"):
        q = "SELECT * FROM outcomes_grad_district WHERE 1=1" + where_district
    elif dataset.startswith("DPF"):
        q = "SELECT * FROM dpf_district WHERE 1=1" + where_district
    else:
        st.error("Unknown dataset."); return

    df = pd.read_sql_query(q, conn, params=params)
    st.dataframe(df.head(500), use_container_width=True, hide_index=True)
    st.caption(f"Showing first 500 of {len(df):,} rows. Download below for full CSV.")

    csv = df.to_csv(index=False)
    fname = dataset.split("(")[0].strip().lower().replace(" ", "_") + ".csv"
    st.download_button(f"Download {fname}", csv, fname, "text/csv", use_container_width=True)


# ============================================================================
# MAIN
# ============================================================================

def main():
    st.set_page_config(
        page_title="VERA-CO | Colorado Education Data",
        page_icon="🏔️",
        layout="wide",
    )

    st.markdown(f"""
    <style>
        .stApp {{ background-color: #fafafa; }}
        .block-container {{ padding-top: 2rem; }}
        h1, h2, h3 {{ color: {CO_BLUE}; }}
        .stButton > button {{ background-color: {CO_BLUE}; color: white; }}
        .stButton > button:hover {{ background-color: {CO_RED}; color: white; }}
    </style>
    """, unsafe_allow_html=True)

    if not DB_PATH.exists():
        st.error(f"Database not found at {DB_PATH}.")
        st.stop()

    # Sidebar
    st.sidebar.markdown(f"""
    <div style="text-align:center; padding:20px 0;">
        <h2 style="color:{CO_BLUE}; margin:0;">VERA-CO</h2>
        <p style="color:#666; font-size:0.85rem; margin-top:5px;">Colorado — Real CDE Data</p>
    </div>
    """, unsafe_allow_html=True)
    st.sidebar.divider()

    page = st.sidebar.radio(
        "Navigation",
        ["Overview", "CMAS Analysis", "ACCESS Analysis", "Type 4 Gap Detection", "Export Data"]
    )
    st.sidebar.divider()
    st.sidebar.markdown(f"""
    **Data sources:** Colorado Department of Education public files (CMAS, ACCESS for ELLs, DPF/SPF, IPST, Graduation).

    **Coverage:** 184 districts · 1,833 schools · 2019-2026 depending on file.

    [H-EDU.Solutions](https://h-edu.solutions)
    """)

    districts_df = load_districts()

    if page == "Overview":
        render_overview(districts_df)
    elif page == "CMAS Analysis":
        render_cmas_analysis(districts_df)
    elif page == "ACCESS Analysis":
        render_access_analysis(districts_df)
    elif page == "Type 4 Gap Detection":
        render_type4_detection(districts_df)
    elif page == "Export Data":
        render_export(districts_df)


if __name__ == "__main__":
    main()
