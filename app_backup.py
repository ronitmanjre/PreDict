import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date, timedelta

st.set_page_config(page_title="JSW Predictive Maintenance", layout="wide")
st.title("JSW Maintenance Dashboard")
st.markdown("---")

# --- Read Machine Master (from local file, not upload) ---
MASTER_PATH = "/Users/ronitmanjre/Desktop/HelloWorld/Equipment Master As on 21.04.25.xlsx"
try:
    master_df = pd.read_excel(MASTER_PATH, engine="openpyxl")
    master_df.columns = master_df.columns.str.strip().str.lower()
    master_machines = master_df["equipment"].astype(str).str.strip().unique()
    total_master_machines = len(master_machines)
except Exception as e:
    st.error(f"Could not load Equipment Master file: {e}")
    master_machines = []
    total_master_machines = 0

# --- Sidebar Filters ---
st.sidebar.header("Date Range Filter")
today = date.today()
default_start = today - timedelta(days=30)
start_date, end_date = st.sidebar.date_input(
    "Select timeframe",
    value=(default_start, today),
    min_value=date(2022, 1, 1),
    max_value=today
)

st.sidebar.header("Upload Breakdown Data")
uploaded_file = st.sidebar.file_uploader(
    "Upload breakdown data (Excel)", type=["xlsx", "xls"]
)

# --- Tile Renderer ---


def style_machine_tile(machine_id, machine_name, health_percent, tag, failures, eta_text):
    health_color_map = {
        "Good": "#00ff3c", "Fair": "#ffc518", "Bad": "#f4051d", "No Score": "#6c757d"
    }
    health_color = health_color_map.get(tag, "#6c757d")
    try:
        score = int(health_percent.strip('%'))
        bar_color = "#29f1ff"
    except:
        score = 100
        bar_color = "#989898"

    return f"""
        <div style="background: linear-gradient(135deg, #7074ff, #0935be, #98b1ff);
                    border-radius: 10px; padding: 10px; color: white;
                    box-shadow: 0 4px 8px rgba(0,0,0,0.2); height: 230px;">
            <h4 style='margin-bottom: 6px;'>{machine_name}</h4>
            <p>ID: <b>{machine_id}</b></p>
            <p>Health: <b style='color:{health_color}'>{health_percent} ({tag})</b></p>
            <p>Breakdowns: <b>{failures}</b></p>
            <p>MTBF: <b>{eta_text}</b></p>
        </div>
        <div style="margin-top: 1px; margin-bottom: 8px; height: 3px; border-radius: 4px;
                    background: #ffffff44;">
            <div style="width: {score}%; height: 100%; background-color: {bar_color}; border-radius: 4px;"></div>
        </div>
    """


# --- Main Logic ---
if uploaded_file:
    df = pd.read_excel(uploaded_file, engine="openpyxl")
    df.columns = df.columns.str.strip().str.lower()

    # --- Parse date columns robustly ---
    try:
        df['malfunction start'] = pd.to_datetime(df['malfunct. start'].astype(
            str) + ' ' + df['start malfn (t)'], errors='coerce')
        df['malfunction end'] = pd.to_datetime(df['malfunct.end'].astype(
            str) + ' ' + df['malfunction end'], errors='coerce')
    except KeyError as e:
        st.error(f"❌ Missing expected column: {e}")
        st.stop()

    # Filter by date
    df = df[(df['malfunction start'].dt.date >= start_date)
            & (df['malfunction start'].dt.date <= end_date)]
    st.session_state.df = df

    # --- Merge with Master Data ---
    df = df.merge(master_df, how='left', on='equipment')

    # --- Compute Times ---
    df['repair time (hrs)'] = (df['malfunction end'] -
                               df['malfunction start']).dt.total_seconds() / 3600
    df = df[df['repair time (hrs)'] > 0]  # Drop invalid

    df = df.sort_values(by=["equipment", "malfunction start"])
    df["prev end"] = df.groupby("equipment")["malfunction end"].shift(1)
    df["uptime since last failure (hrs)"] = (
        df["malfunction start"] - df["prev end"]).dt.total_seconds() / 3600

    # MTBF
    mtbf_df = df.groupby("equipment")[
        "uptime since last failure (hrs)"].mean().reset_index()
    mtbf_df.columns = ["equipment", "mtbf (hrs)"]
    df = df.merge(mtbf_df, on="equipment", how="left")

    # MTTR
    total_repairs = df["repair time (hrs)"].count()
    total_repair_time = df["repair time (hrs)"].sum()
    mttr_value = total_repair_time / total_repairs if total_repairs > 0 else 0

    # --- Metrics ---
    st.caption(
        f"Data from **{start_date.strftime('%d %b %Y')}** to **{end_date.strftime('%d %b %Y')}** | Total records: {len(df)}")
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    col1.metric("Total Machines (Master)", total_master_machines)
    col2.metric("Breakdown Machines", df["equipment"].nunique(
    ), help="Unique machines in selected date range")
    col3.metric("Total Breakdowns", len(df),
                help="Breakdown events in selected period")
    col4.metric("Avg. Breakdown Duration (hrs)",
                f"{df['breakdown dur.'].mean():.2f} hrs" if 'breakdown dur.' in df.columns else "N/A")
    col5.metric("Avg. Repair Time (MTTR)",
                f"{mttr_value:.2f} hrs", help="MTTR = Total Repair Time / Total Repairs")
    col6.metric("Total Downtime (hrs)",
                f"{df['breakdown dur.'].sum():.2f} hrs" if 'breakdown dur.' in df.columns else "N/A")
    st.markdown("---")

    tab1, tab2 = st.tabs(["Dashboard", "Machine Overview"])

    # --- Tab 1: Dashboard ---
    with tab1:
        st.subheader("Key Maintenance Metrics")
        col1, col2 = st.columns(2)

        # Pie chart: Machine status
        with col1:
            now = pd.Timestamp.now()
            latest_status = df.dropna(subset=["malfunction end"]).sort_values(
                "malfunction end").groupby("equipment").last().reset_index()
            all_equipment = df["equipment"].unique()
            machine_status = []
            for machine in all_equipment:
                row = latest_status[latest_status["equipment"] == machine]
                if not row.empty:
                    end = row["malfunction end"].values[0]
                    machine_status.append({
                        "equipment": machine,
                        "status": "Down" if pd.Timestamp(end) > now else "Working"
                    })
                else:
                    machine_status.append(
                        {"equipment": machine, "status": "Down"})
            status_df = pd.DataFrame(machine_status)
            pie_data = status_df["status"].value_counts().reset_index()
            pie_data.columns = ["Status", "Count"]
            fig = px.pie(pie_data, names="Status", values="Count", hole=0.5,
                         color="Status", title="Machine Status",
                         color_discrete_map={"Working": "#41d5e8", "Down": "#c90115"})
            st.plotly_chart(fig, use_container_width=True)

        # Bar chart: Repeated breakdowns
        with col2:
            breakdowns = df['equipment'].value_counts().reset_index()
            breakdowns.columns = ['Equipment', 'Failure Count']
            fig = px.bar(breakdowns.head(5), x='Equipment', y='Failure Count',
                         title="Repeated Breakdowns", color='Failure Count', color_continuous_scale='reds')
            st.plotly_chart(fig, use_container_width=True)

        # Charts: Downtime and Repair Time
        col3, col4 = st.columns(2)
        with col3:
            if 'breakdown dur.' in df.columns:
                downtime = df.groupby('equipment')[
                    "breakdown dur."].sum().reset_index()
                fig = px.bar(downtime.sort_values(by='breakdown dur.', ascending=False).head(10),
                             x='equipment', y='breakdown dur.', title="Highest Downtime (Hrs)",
                             color='breakdown dur.', color_continuous_scale='oranges')
                st.plotly_chart(fig, use_container_width=True)
        with col4:
            mttr = df.groupby('equipment')[
                "repair time (hrs)"].mean().reset_index()
            breakdown_counts = df['equipment'].value_counts().reset_index()
            breakdown_counts.columns = ['equipment', 'breakdown count']
            mttr = mttr.merge(breakdown_counts, on="equipment", how="left")
            fig = px.bar(mttr.sort_values(by='repair time (hrs)', ascending=False).head(10),
                         x='equipment', y='repair time (hrs)', title="High Repair Time (Hrs)",
                         color='repair time (hrs)', color_continuous_scale='blues',
                         hover_data={'equipment': True, 'repair time (hrs)': True, 'breakdown count': True})
            st.plotly_chart(fig, use_container_width=True)

        # MTBF and MTTR side-by-side
        col5, col6 = st.columns(2)
        with col5:
            st.markdown("### Mean Time Between Failures (MTBF)")
            if not mtbf_df.empty:
                lowest_mtbf = mtbf_df.sort_values(
                    by="mtbf (hrs)", ascending=True).head(10)
                fig = px.bar(lowest_mtbf, x="equipment", y="mtbf (hrs)", title="Lowest MTBF by Machine",
                             color="mtbf (hrs)", color_continuous_scale="greens")
                st.plotly_chart(fig, use_container_width=True)
        with col6:
            st.markdown("### Top MTTR Machines")
            mttr_df = df.groupby("equipment")[
                "repair time (hrs)"].mean().reset_index()
            fig = px.bar(mttr_df.sort_values(by="repair time (hrs)", ascending=False).head(10),
                         x="equipment", y="repair time (hrs)", title="Top MTTR by Machine",
                         color="repair time (hrs)", color_continuous_scale="purples")
            st.plotly_chart(fig, use_container_width=True)

        # --- Section/Category/Object Type Analytics ---
        # Section-level
        if "plant section" in df.columns:
            section_metrics = df.groupby("plant section").agg(
                Breakdown_Count=("equipment", "count"),
                Total_Downtime=("breakdown dur.", "sum"),
                Avg_MTTR=("repair time (hrs)", "mean"),
                Avg_MTBF=("mtbf (hrs)", "mean"),
            ).reset_index()
            st.subheader("Section-Level Maintenance Metrics")
            st.dataframe(section_metrics)
            st.markdown("### Total Downtime by Plant Section")
            downtime_section = section_metrics.sort_values(
                by='Total_Downtime', ascending=False)
            fig = px.bar(
                downtime_section,
                x='plant section', y='Total_Downtime',
                title="Total Downtime by Section",
                color='Total_Downtime', color_continuous_scale='oranges'
            )
            st.plotly_chart(fig, use_container_width=True)

        # Equipment category-level
        if "equipment category" in df.columns:
            category_metrics = df.groupby("equipment category").agg(
                Breakdown_Count=("equipment", "count"),
                Total_Downtime=("breakdown dur.", "sum"),
                Avg_MTTR=("repair time (hrs)", "mean"),
                Avg_MTBF=("mtbf (hrs)", "mean"),
            ).reset_index()
            st.subheader("Category-Level Maintenance Metrics")
            st.dataframe(category_metrics)

        # Object type-level
        if "object type" in df.columns:
            type_metrics = df.groupby("object type").agg(
                Breakdown_Count=("equipment", "count"),
                Total_Downtime=("breakdown dur.", "sum"),
                Avg_MTTR=("repair time (hrs)", "mean"),
                Avg_MTBF=("mtbf (hrs)", "mean"),
            ).reset_index()
            st.subheader("Object Type-Level Maintenance Metrics")
            st.dataframe(type_metrics)
            st.markdown("### Breakdown Count by Object Type")
            breakdowns_type = type_metrics.sort_values(
                by='Breakdown_Count', ascending=False)
            fig = px.bar(
                breakdowns_type,
                x='object type', y='Breakdown_Count',
                title="Breakdown Count by Object Type",
                color='Breakdown_Count', color_continuous_scale='reds'
            )
            st.plotly_chart(fig, use_container_width=True)

        # --- Most Common Breakdown Reasons ---
        st.markdown("### Most Common Breakdown Reasons")
        # Identify the correct reason column (e.g., 4th column)
        reason_col = df.columns[3]  # Adjust if needed
        df = df.rename(columns={reason_col: "breakdown_reason"})
        machine_list = df["equipment"].dropna().unique().tolist()
        machine_list.sort()
        col_toggle, col_machine = st.columns([1, 3])
        with col_toggle:
            show_all = st.toggle("Show for All Machines", value=True)
        with col_machine:
            selected_machine = st.selectbox(
                "Select Machine", machine_list, disabled=show_all)
        if show_all:
            df_reasons = df
            breakdown_title = "Top Breakdown Reasons (All Machines)"
        else:
            df_reasons = df[df["equipment"] == selected_machine]
            breakdown_title = f"Top Breakdown Reasons ({selected_machine})"
        if "breakdown_reason" in df_reasons.columns and not df_reasons.empty:
            reason_counts = df_reasons["breakdown_reason"].dropna(
            ).value_counts().reset_index()
            reason_counts.columns = ["Breakdown Reason", "Count"]
            fig = px.bar(reason_counts.head(10), x="Breakdown Reason", y="Count",
                         title=breakdown_title, color="Count", color_continuous_scale="teal")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning(
                "No breakdown reasons found for the selected machine or column missing.")

    # --- Tab 2: Machine Overview ---
    with tab2:
        st.subheader("Machine Overview")
        col1, col2 = st.columns(2)
        with col1:
            search_query = st.text_input("Search by Machine Name or ID")
        with col2:
            sort_by = st.selectbox("Sort by", ["Health (High to Low)", "Health (Low to High)",
                                               "Breakdowns (High to Low)", "Breakdowns (Low to High)",
                                               "MTBF (High to Low)", "MTBF (Low to High)"])
        filtered_df = df.copy()
        if search_query:
            filtered_df = filtered_df[
                filtered_df["functional loc."].astype(str).str.contains(search_query, case=False, na=False) |
                filtered_df["equipment"].astype(str).str.contains(
                    search_query, case=False, na=False)
            ]

        machine_tiles = []
        max_mtbf = df["mtbf (hrs)"].max()
        for machine_id in filtered_df["equipment"].unique():
            mdf = filtered_df[filtered_df["equipment"] == machine_id]
            if mdf.empty:
                continue
            failures = len(mdf)
            mname = mdf["functional loc."].iloc[0] if "functional loc." in mdf.columns else machine_id
            mtbf_val = mdf["mtbf (hrs)"].iloc[0] if "mtbf (hrs)" in mdf.columns else None
            try:
                mtbf_val = float(mtbf_val)
            except:
                mtbf_val = None

            if pd.notna(mtbf_val) and pd.notna(max_mtbf) and max_mtbf > 0:
                pct = (mtbf_val / max_mtbf) * 100
                health_percent = f"{int(pct)}%"
                tag = "Good" if pct > 80 else "Fair" if pct >= 50 else "Bad"
                eta_text = f"{round(mtbf_val, 1)} hrs"
            else:
                tag = "No Score"
                health_percent = "N/A"
                eta_text = "N/A"

            machine_tiles.append({
                "machine_id": machine_id,
                "machine_name": mname,
                "health_percent": health_percent,
                "health_score": int(pct) if health_percent != "N/A" else -1,
                "tag": tag,
                "failures": failures,
                "mtbf": mtbf_val if mtbf_val is not None else -1,
                "eta_text": eta_text
            })

        reverse = "Low to High" not in sort_by
        key_map = {"Health": "health_score",
                   "Breakdowns": "failures", "MTBF": "mtbf"}
        sort_key = key_map[[k for k in key_map if k in sort_by][0]]
        machine_tiles = sorted(
            machine_tiles, key=lambda x: x[sort_key], reverse=reverse)

        cols = st.columns(3)
        for idx, tile in enumerate(machine_tiles):
            tile_html = style_machine_tile(tile["machine_id"], tile["machine_name"],
                                           tile["health_percent"], tile["tag"],
                                           tile["failures"], tile["eta_text"])
            with cols[idx % 3]:
                with st.form(key=f"machine_form_{tile['machine_id']}_{idx}"):
                    st.markdown(tile_html, unsafe_allow_html=True)
                    if st.form_submit_button("View Details"):
                        st.session_state.selected_machine_id = tile["machine_id"]
                        st.switch_page("pages/machine.py")
                    # Uncomment if you have a details page
                    # if st.form_submit_button("View Details"):
                    #     st.session_state.selected_machine_id = tile["machine_id"]
                    #     st.switch_page("pages/machine.py")

else:
    st.info("📂 Please upload a valid Excel file to continue.")
