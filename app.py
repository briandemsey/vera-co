"""
VERA-CO: Verification Engine for Results & Accountability - Colorado
Type 4 Dyslexia Screening using ACCESS for ELLs and CMAS Assessment Data

H-EDU.Solutions | https://h-edu.solutions
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

# ============================================================================
# CONFIGURATION
# ============================================================================

APP_# Colorado colors
CO_BLUE = "#002868"   # Colorado blue
CO_RED = "#C8102E"    # Colorado red
CO_GOLD = "#CFB87C"   # Colorado gold/tan

# ============================================================================
# SAMPLE DATA - Colorado Districts
# ============================================================================

def load_districts():
    """Load Colorado district data."""
    districts_data = [
        ("0880", "Denver Public Schools", 90000, 31500, 35.0, 74.2, 62.5),
        ("0010", "Jefferson County R-1", 80000, 8800, 11.0, 86.3, 71.2),
        ("0900", "Douglas County RE-1", 68000, 4760, 7.0, 92.5, 78.4),
        ("0080", "Cherry Creek 5", 55000, 8250, 15.0, 88.7, 74.8),
        ("0030", "Aurora Public Schools", 38000, 15200, 40.0, 71.5, 55.3),
        ("0011", "Colorado Springs D-11", 24000, 3600, 15.0, 78.4, 61.7),
        ("0500", "Adams 12 Five Star", 38000, 7600, 20.0, 82.1, 67.3),
        ("0020", "Boulder Valley RE-2", 30000, 2700, 9.0, 89.8, 75.6),
        ("2180", "Poudre R-1", 32000, 3840, 12.0, 85.6, 70.2),
        ("1210", "Greeley-Evans 6", 23000, 9200, 40.0, 72.8, 54.8),
    ]

    df = pd.DataFrame(districts_data, columns=[
        'district_id', 'district_name', 'total_students',
        'ell_count', 'ell_percent', 'graduation_rate', 'spf_score'
    ])
    return df

def load_access_data():
    """Load sample ACCESS for ELLs data (Colorado is a WIDA state)."""
    access_data = []

    districts = [
        ("0880", "Denver Public Schools"),
        ("0010", "Jefferson County R-1"),
        ("0900", "Douglas County RE-1"),
        ("0080", "Cherry Creek 5"),
        ("0030", "Aurora Public Schools"),
        ("0011", "Colorado Springs D-11"),
        ("0500", "Adams 12 Five Star"),
        ("0020", "Boulder Valley RE-2"),
        ("2180", "Poudre R-1"),
        ("1210", "Greeley-Evans 6"),
    ]

    for district_id, district_name in districts:
        for grade in range(3, 9):
            for year in [2024, 2025]:
                # Generate realistic ACCESS scores (scale 100-600)
                base_speaking = 340 + (grade * 8)
                base_writing = 295 + (grade * 6)

                # Add district-specific variation
                if district_id == "0030":  # Aurora - high EL%, larger delta
                    speaking_adj = 40
                    writing_adj = -10
                elif district_id == "1210":  # Greeley - high EL%
                    speaking_adj = 38
                    writing_adj = -8
                elif district_id == "0880":  # Denver
                    speaking_adj = 32
                    writing_adj = -3
                elif district_id in ["0900", "0020"]:  # Higher performing
                    speaking_adj = 15
                    writing_adj = 12
                else:
                    speaking_adj = 22
                    writing_adj = 5

                access_data.append({
                    'district_id': district_id,
                    'district_name': district_name,
                    'grade': grade,
                    'year': year,
                    'total_tested': 250 + (grade * 20) if district_id in ["0880", "0030"] else 80 + (grade * 8),
                    'listening_avg': base_speaking + speaking_adj - 5,
                    'speaking_avg': base_speaking + speaking_adj,
                    'reading_avg': base_writing + writing_adj + 15,
                    'writing_avg': base_writing + writing_adj,
                    'composite_avg': (base_speaking + speaking_adj + base_writing + writing_adj) / 2 + 22
                })

    return pd.DataFrame(access_data)

def load_cmas_data():
    """Load sample CMAS (Colorado Measures of Academic Success) data."""
    cmas_data = []

    districts = [
        ("0880", "Denver Public Schools"),
        ("0010", "Jefferson County R-1"),
        ("0900", "Douglas County RE-1"),
        ("0080", "Cherry Creek 5"),
        ("0030", "Aurora Public Schools"),
        ("0011", "Colorado Springs D-11"),
        ("0500", "Adams 12 Five Star"),
        ("0020", "Boulder Valley RE-2"),
        ("2180", "Poudre R-1"),
        ("1210", "Greeley-Evans 6"),
    ]

    for district_id, district_name in districts:
        for grade in range(3, 9):
            for year in [2024, 2025]:
                for subject in ['ELA', 'Math']:
                    # Generate realistic CMAS proficiency distributions
                    if district_id in ["0900", "0020", "0080"]:  # Higher performing
                        exceeded = 22 + (grade * 0.5)
                        met = 35 + (grade * 0.3)
                        approaching = 28 - (grade * 0.3)
                        not_met = 15 - (grade * 0.5)
                    elif district_id in ["0030", "1210"]:  # Lower performing
                        exceeded = 8 + (grade * 0.3)
                        met = 22 + (grade * 0.2)
                        approaching = 38 - (grade * 0.2)
                        not_met = 32 - (grade * 0.3)
                    elif district_id == "0880":  # Denver - large urban
                        exceeded = 14 + (grade * 0.4)
                        met = 28 + (grade * 0.2)
                        approaching = 32 - (grade * 0.2)
                        not_met = 26 - (grade * 0.4)
                    else:  # Average
                        exceeded = 16 + (grade * 0.4)
                        met = 30 + (grade * 0.2)
                        approaching = 30 - (grade * 0.2)
                        not_met = 24 - (grade * 0.4)

                    cmas_data.append({
                        'district_id': district_id,
                        'district_name': district_name,
                        'grade': grade,
                        'subject': subject,
                        'year': year,
                        'total_tested': 2500 + (grade * 100) if district_id == "0880" else 600 + (grade * 40),
                        'not_met_pct': max(5, not_met),
                        'approaching_pct': max(10, approaching),
                        'met_pct': min(45, met),
                        'exceeded_pct': min(35, exceeded),
                        'mean_scale_score': 725 + (met + exceeded) * 1.5
                    })

    return pd.DataFrame(cmas_data)

# ============================================================================
# AUTHENTICATION
# ============================================================================

# ============================================================================
# TYPE 4 DETECTION
# ============================================================================

def compute_type4_analysis(access_df, district_id, grade, year):
    """
    Compute Type 4 (oral-written delta) analysis for a district.
    """
    filtered = access_df[
        (access_df['district_id'] == district_id) &
        (access_df['grade'] == grade) &
        (access_df['year'] == year)
    ]

    if filtered.empty:
        return None

    row = filtered.iloc[0]

    speaking = row['speaking_avg']
    writing = row['writing_avg']
    delta = speaking - writing
    delta_normalized = delta / 5
    flagged = delta_normalized > 8

    return {
        'district_id': district_id,
        'district_name': row['district_name'],
        'grade': grade,
        'year': year,
        'speaking_avg': speaking,
        'writing_avg': writing,
        'delta': delta,
        'delta_normalized': delta_normalized,
        'flagged': flagged,
        'total_tested': row['total_tested'],
        'estimated_flagged': int(row['total_tested'] * 0.15) if flagged else int(row['total_tested'] * 0.05)
    }

# ============================================================================
# DASHBOARD PAGES
# ============================================================================

def render_overview(districts_df, access_df, cmas_df):
    """Render the overview dashboard."""
    st.header("Colorado Education Overview")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Districts", len(districts_df))
    with col2:
        st.metric("Total Students", f"{districts_df['total_students'].sum():,}")
    with col3:
        st.metric("English Learners", f"{districts_df['ell_count'].sum():,}")
    with col4:
        avg_spf = districts_df['spf_score'].mean()
        st.metric("Avg SPF Score", f"{avg_spf:.1f}")

    st.divider()

    st.subheader("Pilot Districts")

    display_df = districts_df.copy()
    display_df['ell_percent'] = display_df['ell_percent'].apply(lambda x: f"{x:.1f}%")
    display_df['graduation_rate'] = display_df['graduation_rate'].apply(lambda x: f"{x:.1f}%")
    display_df['spf_score'] = display_df['spf_score'].apply(lambda x: f"{x:.1f}")
    display_df.columns = ['District ID', 'District Name', 'Total Students', 'EL Count', 'EL %', 'Grad Rate', 'SPF']

    st.dataframe(display_df, use_container_width=True, hide_index=True)

    st.subheader("English Learner Population by District")

    fig = px.bar(
        districts_df.sort_values('ell_count', ascending=True),
        x='ell_count',
        y='district_name',
        orientation='h',
        color='ell_percent',
        color_continuous_scale=[[0, CO_GOLD], [0.5, CO_BLUE], [1, CO_RED]],
        labels={'ell_count': 'English Learners', 'district_name': 'District', 'ell_percent': 'EL %'}
    )
    fig.update_layout(height=400, showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

def render_access_analysis(access_df, districts_df):
    """Render ACCESS for ELLs assessment analysis."""
    st.header("ACCESS for ELLs Analysis")

    st.markdown("""
    **ACCESS for ELLs** (WIDA) measures English learners' proficiency across four domains:
    Listening, Speaking, Reading, and Writing. Colorado is a WIDA consortium member state.
    """)

    col1, col2, col3 = st.columns(3)

    with col1:
        district = st.selectbox(
            "Select District",
            options=districts_df['district_name'].tolist(),
            key="access_district"
        )

    with col2:
        grade = st.selectbox("Select Grade", options=list(range(3, 9)), key="access_grade")

    with col3:
        year = st.selectbox("Select Year", options=[2025, 2024], key="access_year")

    district_id = districts_df[districts_df['district_name'] == district]['district_id'].values[0]

    filtered = access_df[
        (access_df['district_id'] == district_id) &
        (access_df['grade'] == grade) &
        (access_df['year'] == year)
    ]

    if not filtered.empty:
        row = filtered.iloc[0]

        st.divider()

        st.subheader("ACCESS Domain Scores")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Listening", f"{row['listening_avg']:.0f}")
        with col2:
            st.metric("Speaking", f"{row['speaking_avg']:.0f}")
        with col3:
            st.metric("Reading", f"{row['reading_avg']:.0f}")
        with col4:
            st.metric("Writing", f"{row['writing_avg']:.0f}")

        domains = ['Listening', 'Speaking', 'Reading', 'Writing']
        scores = [row['listening_avg'], row['speaking_avg'], row['reading_avg'], row['writing_avg']]

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=domains,
            y=scores,
            marker_color=[CO_BLUE, CO_RED, CO_GOLD, CO_BLUE],
            text=[f"{s:.0f}" for s in scores],
            textposition='outside'
        ))
        fig.update_layout(
            title=f"ACCESS Domain Scores - {district} - Grade {grade} ({year})",
            yaxis_title="Scale Score",
            height=400
        )
        st.plotly_chart(fig, use_container_width=True)

        oral_avg = (row['listening_avg'] + row['speaking_avg']) / 2
        written_avg = (row['reading_avg'] + row['writing_avg']) / 2
        gap = oral_avg - written_avg

        st.subheader("Oral vs Written Gap")

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Oral Average", f"{oral_avg:.0f}", help="(Listening + Speaking) / 2")
        with col2:
            st.metric("Written Average", f"{written_avg:.0f}", help="(Reading + Writing) / 2")
        with col3:
            delta_color = "normal" if gap < 25 else "inverse"
            st.metric("Gap", f"{gap:+.0f}", delta=f"{'Flag' if gap > 30 else 'OK'}", delta_color=delta_color)

def render_type4_detection(access_df, districts_df):
    """Render Type 4 detection analysis."""
    st.header("Type 4 Detection")

    st.markdown("""
    **Type 4 dyslexia candidates** demonstrate strong oral communication abilities but
    significant challenges with written expression. VERA-CO identifies these students by
    analyzing the delta between ACCESS Speaking and Writing domain scores.

    **Flag Threshold:** Speaking - Writing delta > 8 points (normalized scale)
    """)

    col1, col2, col3 = st.columns(3)

    with col1:
        district = st.selectbox(
            "Select District",
            options=districts_df['district_name'].tolist(),
            key="type4_district"
        )

    with col2:
        grade = st.selectbox("Select Grade", options=list(range(3, 9)), key="type4_grade")

    with col3:
        year = st.selectbox("Select Year", options=[2025, 2024], key="type4_year")

    district_id = districts_df[districts_df['district_name'] == district]['district_id'].values[0]

    result = compute_type4_analysis(access_df, district_id, grade, year)

    if result:
        st.divider()

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Speaking Score", f"{result['speaking_avg']:.0f}")
        with col2:
            st.metric("Writing Score", f"{result['writing_avg']:.0f}")
        with col3:
            st.metric("Delta", f"{result['delta']:+.0f}")
        with col4:
            status = "🚨 FLAGGED" if result['flagged'] else "✅ OK"
            st.metric("Status", status)

        st.subheader("Oral-Written Delta Analysis")

        fig = go.Figure()

        fig.add_trace(go.Bar(
            name='Speaking',
            x=['Score'],
            y=[result['speaking_avg']],
            marker_color=CO_RED,
            text=[f"{result['speaking_avg']:.0f}"],
            textposition='outside'
        ))

        fig.add_trace(go.Bar(
            name='Writing',
            x=['Score'],
            y=[result['writing_avg']],
            marker_color=CO_BLUE,
            text=[f"{result['writing_avg']:.0f}"],
            textposition='outside'
        ))

        fig.update_layout(
            title=f"Speaking vs Writing - {district} - Grade {grade}",
            barmode='group',
            height=350
        )
        st.plotly_chart(fig, use_container_width=True)

        if result['flagged']:
            st.error(f"""
            **Type 4 Flag Triggered**

            This grade level shows a significant oral-written gap (delta: {result['delta']:+.0f}).

            - **Estimated students affected:** {result['estimated_flagged']} of {result['total_tested']} tested
            - **Recommended action:** Individual student-level screening for Type 4 dyslexia
            - **Next steps:** Cross-reference with CMAS ELA writing performance
            """)
        else:
            st.success(f"""
            **No Type 4 Flag**

            The oral-written gap for this grade level is within normal range (delta: {result['delta']:+.0f}).

            - **Students tested:** {result['total_tested']}
            - **Continue monitoring:** Regular ACCESS domain analysis recommended
            """)

        st.subheader(f"All Grades - {district} ({year})")

        all_grades_data = []
        for g in range(3, 9):
            r = compute_type4_analysis(access_df, district_id, g, year)
            if r:
                all_grades_data.append(r)

        if all_grades_data:
            grades_df = pd.DataFrame(all_grades_data)

            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=grades_df['grade'],
                y=grades_df['speaking_avg'],
                name='Speaking',
                mode='lines+markers',
                line=dict(color=CO_RED, width=3),
                marker=dict(size=10)
            ))
            fig.add_trace(go.Scatter(
                x=grades_df['grade'],
                y=grades_df['writing_avg'],
                name='Writing',
                mode='lines+markers',
                line=dict(color=CO_BLUE, width=3),
                marker=dict(size=10)
            ))

            fig.update_layout(
                title="Speaking vs Writing Across Grades",
                xaxis_title="Grade",
                yaxis_title="Scale Score",
                height=400
            )
            st.plotly_chart(fig, use_container_width=True)

def render_cmas_analysis(cmas_df, districts_df):
    """Render CMAS assessment analysis."""
    st.header("CMAS Assessment Analysis")

    st.markdown("""
    **CMAS (Colorado Measures of Academic Success)** measures student achievement
    in English Language Arts and Mathematics aligned to Colorado Academic Standards.
    """)

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        district = st.selectbox(
            "Select District",
            options=districts_df['district_name'].tolist(),
            key="cmas_district"
        )

    with col2:
        grade = st.selectbox("Select Grade", options=list(range(3, 9)), key="cmas_grade")

    with col3:
        subject = st.selectbox("Select Subject", options=['ELA', 'Math'], key="cmas_subject")

    with col4:
        year = st.selectbox("Select Year", options=[2025, 2024], key="cmas_year")

    district_id = districts_df[districts_df['district_name'] == district]['district_id'].values[0]

    filtered = cmas_df[
        (cmas_df['district_id'] == district_id) &
        (cmas_df['grade'] == grade) &
        (cmas_df['subject'] == subject) &
        (cmas_df['year'] == year)
    ]

    if not filtered.empty:
        row = filtered.iloc[0]

        st.divider()

        st.subheader("Performance Distribution")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Did Not Yet Meet", f"{row['not_met_pct']:.1f}%")
        with col2:
            st.metric("Approaching", f"{row['approaching_pct']:.1f}%")
        with col3:
            st.metric("Met", f"{row['met_pct']:.1f}%")
        with col4:
            st.metric("Exceeded", f"{row['exceeded_pct']:.1f}%")

        levels = ['Did Not Yet\nMeet', 'Approaching', 'Met', 'Exceeded']
        values = [row['not_met_pct'], row['approaching_pct'], row['met_pct'], row['exceeded_pct']]
        colors = ['#d32f2f', '#f57c00', CO_GOLD, CO_BLUE]

        fig = go.Figure(data=[
            go.Bar(x=levels, y=values, marker_color=colors, text=[f"{v:.1f}%" for v in values], textposition='outside')
        ])
        fig.update_layout(
            title=f"CMAS {subject} Performance - {district} - Grade {grade} ({year})",
            yaxis_title="Percentage",
            height=400
        )
        st.plotly_chart(fig, use_container_width=True)

        proficient_rate = row['met_pct'] + row['exceeded_pct']
        st.metric(
            "Proficiency Rate (Met + Exceeded)",
            f"{proficient_rate:.1f}%",
            help="Percentage of students meeting or exceeding expectations"
        )

def render_export(access_df, cmas_df, districts_df):
    """Render data export page."""
    st.header("Export Data")

    st.markdown("Download assessment data for further analysis.")

    district = st.selectbox(
        "Select District (or All)",
        options=["All Districts"] + districts_df['district_name'].tolist()
    )

    year = st.selectbox("Select Year", options=[2025, 2024])

    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("ACCESS Data")
        if district == "All Districts":
            export_access = access_df[access_df['year'] == year]
        else:
            district_id = districts_df[districts_df['district_name'] == district]['district_id'].values[0]
            export_access = access_df[(access_df['district_id'] == district_id) & (access_df['year'] == year)]

        st.dataframe(export_access, use_container_width=True, hide_index=True)

        csv_access = export_access.to_csv(index=False)
        st.download_button(
            "Download ACCESS CSV",
            csv_access,
            f"vera_co_access_{year}.csv",
            "text/csv",
            use_container_width=True
        )

    with col2:
        st.subheader("CMAS Data")
        if district == "All Districts":
            export_cmas = cmas_df[cmas_df['year'] == year]
        else:
            district_id = districts_df[districts_df['district_name'] == district]['district_id'].values[0]
            export_cmas = cmas_df[(cmas_df['district_id'] == district_id) & (cmas_df['year'] == year)]

        st.dataframe(export_cmas, use_container_width=True, hide_index=True)

        csv_cmas = export_cmas.to_csv(index=False)
        st.download_button(
            "Download CMAS CSV",
            csv_cmas,
            f"vera_co_cmas_{year}.csv",
            "text/csv",
            use_container_width=True
        )

# ============================================================================
# MAIN APP
# ============================================================================

def main():
    st.set_page_config(
        page_title="VERA-CO | Colorado Type 4 Detection",
        page_icon="🏔️",
        layout="wide"
    )

    st.markdown(f"""
    <style>
        .stApp {{
            background-color: #fafafa;
        }}
        .block-container {{
            padding-top: 2rem;
        }}
        h1, h2, h3 {{
            color: {CO_BLUE};
        }}
        .stButton > button {{
            background-color: {CO_BLUE};
            color: white;
        }}
        .stButton > button:hover {{
            background-color: {CO_RED};
            color: white;
        }}
    </style>
    """, unsafe_allow_html=True)

    districts_df = load_districts()
    access_df = load_access_data()
    cmas_df = load_cmas_data()

    st.sidebar.markdown(f"""
    <div style="text-align: center; padding: 20px 0;">
        <h2 style="color: {CO_BLUE}; margin: 0;">VERA-CO</h2>
        <p style="color: #666; font-size: 0.85rem; margin-top: 5px;">Colorado Implementation</p>
    </div>
    """, unsafe_allow_html=True)

    st.sidebar.divider()

    page = st.sidebar.radio(
        "Navigation",
        ["Overview", "ACCESS Analysis", "Type 4 Detection", "CMAS Analysis", "Export Data"]
    )

    st.sidebar.divider()

    st.sidebar.markdown("""
    **Data Sources:**
    - ACCESS for ELLs (WIDA)
    - CMAS (Colorado Academic Success)
    - School Performance Framework

    **Type 4 Detection:**
    - Speaking vs Writing delta
    - Flag threshold: > 8 points

    ---

    [H-EDU.Solutions](https://h-edu.solutions)
    """)

    if page == "Overview":
        render_overview(districts_df, access_df, cmas_df)
    elif page == "ACCESS Analysis":
        render_access_analysis(access_df, districts_df)
    elif page == "Type 4 Detection":
        render_type4_detection(access_df, districts_df)
    elif page == "CMAS Analysis":
        render_cmas_analysis(cmas_df, districts_df)
    elif page == "Export Data":
        render_export(access_df, cmas_df, districts_df)

if __name__ == "__main__":
    main()
