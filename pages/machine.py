# machine.py

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import os

st.set_page_config(page_title="Machine Details", layout="wide")

# --- Load Data ---
if "df" not in st.session_state:
    if os.path.exists("temp_data.csv"):
        df_raw = pd.read_csv("temp_data.csv")
        df_raw.columns = df_raw.columns.str.strip().str.lower()  # Fix column casing
        df_raw["malfunction start"] = pd.to_datetime(
            df_raw["malfunction start"], errors="coerce")
        st.session_state.df = df_raw
    else:
        st.error("No machine data available.")
        st.stop()

df = st.session_state.df

# --- Selected machine ID (optional) ---
machine_id = st.session_state.get("selected_machine_id", None)

# --- Machine filter ---
if machine_id:
    machine_df = df[df["equipment"] == machine_id].copy()
else:
    machine_df = df.copy()

if machine_df.empty:
    st.warning("No data available for this machine.")
    st.stop()

# --- Machine Title ---
if machine_id:
    machine_name = machine_df["functional loc."].iloc[0] if "functional loc." in machine_df.columns else machine_id
    st.title(f"{machine_name}")
    st.markdown(f"**Machine ID:** `{machine_id}`")
else:
    st.title("All Machines Overview")
    st.markdown("Showing data for all machines")

# --- Equipment Master Data ---
master_df = None
if os.path.exists("/Users/ronitmanjre/Desktop/HelloWorld/Equipment Master As on 21.04.25.xlsx"):
    master_df = pd.read_excel(
        "/Users/ronitmanjre/Desktop/HelloWorld/Equipment Master As on 21.04.25.xlsx", engine="openpyxl")
    master_df.columns = master_df.columns.str.strip().str.lower()

if machine_id and master_df is not None:
    try:
        master_row = master_df[master_df["equipment"].astype(
            str) == str(machine_id)].iloc[0]
        with st.expander("ℹ️ Equipment Master Details", expanded=True):
            st.markdown(
                f"- **Description:** {master_row.get('description', 'N/A')}")
            st.markdown(
                f"- **Object Type:** {master_row.get('object type', 'N/A')}")
            st.markdown(
                f"- **Plant Section:** {master_row.get('plant section', 'N/A')}")
            st.markdown(
                f"- **Installation Date:** {master_row.get('installation date', 'N/A')}")
            st.markdown(
                f"- **Planner Group:** {master_row.get('planner group', 'N/A')}")
    except Exception:
        st.info("No matching master data found for this machine.")

st.markdown("---")

# --- Date Filter ---
st.sidebar.header("Select Timeframe")
min_date = machine_df["malfunction start"].min().date()
max_date = machine_df["malfunction start"].max().date()
start_date = st.sidebar.date_input(
    "From Date", min_value=min_date, max_value=max_date, value=min_date)
end_date = st.sidebar.date_input(
    "To Date", min_value=min_date, max_value=max_date, value=max_date)

filtered_df = machine_df[
    (machine_df["malfunction start"].dt.date >= start_date) &
    (machine_df["malfunction start"].dt.date <= end_date)
]

# --- Tabs ---
tab1, tab2, tab3, tab4 = st.tabs(
    [" Overview", " Trends", " Maintenance", " Actions"])

# -------------------- TAB 1: Overview --------------------
with tab1:
    st.subheader("Summary Metrics")
    col1, col2, col3 = st.columns(3)

    col1.metric("Total Breakdowns", len(filtered_df))
    col2.metric(
        "Avg. Breakdown Duration (hrs)",
        round(filtered_df["breakdown dur."].mean(),
              2) if "breakdown dur." in filtered_df.columns else "N/A"
    )
    col3.metric(
        "Total Downtime (hrs)",
        round(filtered_df["breakdown dur."].sum(),
              2) if "breakdown dur." in filtered_df.columns else "N/A"
    )

    st.markdown("### Breakdown Over Time")
    if "malfunction start" in filtered_df.columns:
        daily = filtered_df.groupby(
            filtered_df["malfunction start"].dt.date).size().reset_index(name="Count")
        st.plotly_chart(
            px.line(daily, x="malfunction start", y="Count",
                    title="Daily Breakdown Count"),
            use_container_width=True
        )
    else:
        st.info("Breakdown timestamps not available.")


# -------------------- TAB 2: Trends --------------------
with tab2:
    st.subheader("Breakdown Trends")

    if "breakdown dur." in filtered_df.columns:
        st.markdown("### Duration of Breakdowns")
        st.plotly_chart(
            px.bar(filtered_df.sort_values("malfunction start"),
                   x="malfunction start", y="breakdown dur.",
                   title="Breakdown Duration Over Time"),
            use_container_width=True
        )

    st.markdown("### Breakdown Reason Frequency")
    if "coding code txt" in filtered_df.columns:
        reason_counts = filtered_df["coding code txt"].value_counts(
        ).reset_index()
        reason_counts.columns = ["Reason", "Count"]
        st.plotly_chart(
            px.bar(reason_counts.head(10), x="Reason",
                   y="Count", title="Top Failure Reasons"),
            use_container_width=True
        )
    else:
        st.info("Failure reasons not available.")

# -------------------- TAB 3: Maintenance --------------------
with tab3:
    st.subheader("Maintenance Logs")

    if {"failure", "maintenance_done"}.issubset(filtered_df.columns):
        st.dataframe(
            filtered_df[["notif.date", "malfunct. start", "failure",
                         "failure_reason", "maintenance_done", "maintenance_comments"]]
            .sort_values("malfunct. start", ascending=False)
            .head(10)
        )
    else:
        st.info("Maintenance details not available.")

    st.subheader(" Maintenance Recommendation")

    recent_failures = filtered_df[filtered_df["breakdown dur."] >
                                  1] if "breakdown dur." in filtered_df.columns else pd.DataFrame()
    reasons = []

    if recent_failures.shape[0] > 2:
        reasons.append("Multiple recent failures")

    if "coding code txt" in filtered_df.columns:
        mode_series = filtered_df["coding code txt"].mode()
        if not mode_series.empty:
            top_reason = mode_series.iloc[0]
            reasons.append(f"Frequent failure reason: **{top_reason}**")

    if "maintenance_done" in filtered_df.columns:
        if filtered_df["maintenance_done"].sum() == 0:
            reasons.append("No recent maintenance logs")

    if reasons:
        st.markdown("### Recommended Maintenance:")
        for reason in reasons:
            st.markdown(f"- {reason}")
        st.success(" Maintenance advised within 3 days.")
    else:
        st.success(" No urgent maintenance required.")

    st.markdown("---")
    st.markdown("### 📋 Latest Comments")
    if "maintenance_comments" in filtered_df.columns:
        st.dataframe(
            filtered_df[["notif.date", "maintenance_comments"]].dropna().tail(5))
    else:
        st.info("No comments available.")

# -------------------- TAB 4: Actions --------------------
with tab4:
    st.markdown("### Action Center")
    col1, col2 = st.columns(2)
    with col1:
        st.button(" Create Work Order")
        st.button(" Create Maintenance Request")
    with col2:
        st.button(" Add Maintenance Plan")
        st.button(" Edit Machine Info")

# --- Back Button ---
if st.button("🔙 Back to Dashboard"):
    st.switch_page("app.py")
