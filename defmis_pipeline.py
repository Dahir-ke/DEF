import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
import os
import sys

# =========================
# 1. DATA LOADER (CLI + STREAMLIT SAFE)
# =========================
def load_data(file_input):
    if hasattr(file_input, "name"):
        file_name = file_input.name
        file_obj = file_input
    elif isinstance(file_input, str):
        file_name = file_input
        file_obj = file_input
    else:
        raise ValueError("Unsupported input type")

    if file_name.endswith(".csv"):
        df = pd.read_csv(file_obj)
    elif file_name.endswith(".xlsx"):
        df = pd.read_excel(file_obj, engine="openpyxl")
    else:
        raise ValueError("Only CSV and XLSX supported")
    return df

# =========================
# 2. CLEANING LAYER (ENHANCED)
# =========================
def clean_data(df):
    df = df.copy()
    # Strip column names
    df.columns = df.columns.str.strip()

    # Convert key columns to proper types
    df['AMOUNT'] = pd.to_numeric(df['AMOUNT'], errors='coerce')
    df['ARRIVAL DATE'] = pd.to_datetime(df['ARRIVAL DATE'], errors='coerce')
    df['TRANSACTION DATE'] = pd.to_datetime(df['TRANSACTION DATE'], errors='coerce')
    df['DOB'] = pd.to_datetime(df['DOB'], errors='coerce')
    df['MEMBER NUMBER'] = df['MEMBER NUMBER'].astype(str)

    # Drop columns that are completely empty
    df = df.dropna(axis=1, how='all')

    # Remove rows with essential missing data
    df = df.dropna(subset=['AMOUNT', 'ARRIVAL DATE', 'MEMBER NUMBER', 'PROVIDER NAME'])

    # Duplicate removal
    df = df.drop_duplicates()
    return df

# =========================
# 3. FEATURE ENGINEERING (ENHANCED)
# =========================
def feature_engineering(df):
    df = df.copy()
    # Visit key (already exists, but we recompute for safety)
    df['VISIT_KEY'] = (
        df['MEMBER NUMBER'].astype(str) + '_' +
        df['ARRIVAL DATE'].dt.strftime('%Y-%m-%d') + '_' +
        df['SERVICE TYPE'].astype(str)
    )
    # Time features
    df['YEAR_MONTH'] = df['ARRIVAL DATE'].dt.to_period('M')
    df['YEAR'] = df['ARRIVAL DATE'].dt.year
    df['MONTH'] = df['ARRIVAL DATE'].dt.month
    df['DAY_OF_WEEK'] = df['ARRIVAL DATE'].dt.dayofweek
    df['WEEK'] = df['ARRIVAL DATE'].dt.isocalendar().week

    # Member age at claim (if DOB available)
    df['AGE'] = (df['ARRIVAL DATE'] - df['DOB']).dt.days // 365
    df['AGE'] = df['AGE'].clip(0, 120)

    # Roaming flag
    df['IS_ROAMER'] = df['ROAMING COUNTRIES'].notna() & (df['ROAMING COUNTRIES'] != '')
    return df

# =========================
# 4. ANALYTICS ENGINE (RISK SCORING)
# =========================
def analytics_engine(df):
    provider_stats = df.groupby('PROVIDER NAME').agg(
        TOTAL_COST=('AMOUNT', 'sum'),
        UNIQUE_VISITS=('VISIT_KEY', 'nunique'),
        UNIQUE_MEMBERS=('MEMBER NUMBER', 'nunique'),
        TOTAL_CLAIMS=('CLAIM ID', 'count'),
        AVG_COST=('AMOUNT', 'mean'),
        TOTAL_ROAMING=('IS_ROAMER', 'sum')
    ).reset_index()
    provider_stats['AVG_COST_PER_VISIT'] = (
        provider_stats['TOTAL_COST'] / provider_stats['UNIQUE_VISITS'].replace(0, 1)
    )
    # Risk scoring (percentile rank weighting)
    provider_stats['RISK_SCORE'] = (
        provider_stats['AVG_COST_PER_VISIT'].rank(pct=True) * 0.5 +
        provider_stats['TOTAL_CLAIMS'].rank(pct=True) * 0.3 +
        provider_stats['UNIQUE_MEMBERS'].rank(pct=True) * 0.2
    )
    provider_stats = provider_stats.sort_values('RISK_SCORE', ascending=False)
    return provider_stats

# =========================
# 5. FRAUD DETECTION ENGINE (ENHANCED)
# ==========================
def fraud_detection(df):
    # 1. Exact duplicate claims
    duplicate_subset = ['MEMBER NUMBER', 'ARRIVAL DATE', 'AMOUNT', 'PROVIDER NAME']
    duplicates = df[df.duplicated(subset=duplicate_subset, keep=False)]

    # 2. Provider-Benefit anomaly (Z-score on avg cost per visit)
    prov_ben = df.groupby(['PROVIDER NAME', 'BENEFIT DESC']).agg(
        TOTAL_COST=('AMOUNT', 'sum'),
        UNIQUE_VISITS=('VISIT_KEY', 'nunique'),
        TOTAL_CLAIMS=('CLAIM ID', 'count')
    ).reset_index()
    prov_ben['AVG_COST_PER_VISIT'] = prov_ben['TOTAL_COST'] / prov_ben['UNIQUE_VISITS'].replace(0, 1)
    mean = prov_ben['AVG_COST_PER_VISIT'].mean()
    std = prov_ben['AVG_COST_PER_VISIT'].std()
    prov_ben['Z_SCORE'] = (prov_ben['AVG_COST_PER_VISIT'] - mean) / std
    fraud_flags = prov_ben[prov_ben['Z_SCORE'] > 2]

    # 3. Additional: members with unusually high number of claims
    member_claim_count = df.groupby('MEMBER NUMBER').size().reset_index(name='CLAIM_COUNT')
    high_freq_members = member_claim_count[member_claim_count['CLAIM_COUNT'] > member_claim_count['CLAIM_COUNT'].quantile(0.99)]
    high_freq_members = df[df['MEMBER NUMBER'].isin(high_freq_members['MEMBER NUMBER'])]

    return duplicates, fraud_flags, high_freq_members

# =========================
# 6. STREAMLIT DASHBOARD
# =========================
st.set_page_config(page_title="Healthcare Fraud Analytics", layout="wide", initial_sidebar_state="expanded")
st.title("🏥 Healthcare Claims Analytics & Fraud Detection Dashboard")
st.markdown("### *Magical insights from your claims data*")

# Sidebar upload & filters
with st.sidebar:
    st.header("📂 Data Upload")
    uploaded_file = st.file_uploader("Upload CSV or Excel", type=['csv', 'xlsx'])
    if uploaded_file is not None:
        with st.spinner("Loading and processing data..."):
            df_raw = load_data(uploaded_file)
            df = clean_data(df_raw)
            df = feature_engineering(df)
            provider_stats = analytics_engine(df)
            duplicates, fraud_flags, high_freq_members = fraud_detection(df)

            # Global filters
            st.header("🔍 Global Filters")
            min_date = df['ARRIVAL DATE'].min().date()
            max_date = df['ARRIVAL DATE'].max().date()
            date_range = st.date_input("Arrival Date Range", [min_date, max_date], min_value=min_date, max_value=max_date)
            if len(date_range) == 2:
                start_date, end_date = date_range
                df = df[(df['ARRIVAL DATE'].dt.date >= start_date) & (df['ARRIVAL DATE'].dt.date <= end_date)]

            providers = st.multiselect("Provider Name", options=df['PROVIDER NAME'].unique())
            if providers:
                df = df[df['PROVIDER NAME'].isin(providers)]

            benefits = st.multiselect("Benefit Description", options=df['BENEFIT DESC'].unique())
            if benefits:
                df = df[df['BENEFIT DESC'].isin(benefits)]

            roam_filter = st.radio("Roaming Claims", ["All", "Roaming Only", "Non-Roaming"])
            if roam_filter == "Roaming Only":
                df = df[df['IS_ROAMER'] == True]
            elif roam_filter == "Non-Roaming":
                df = df[df['IS_ROAMER'] == False]

if uploaded_file is None:
    st.info("👈 Please upload a CSV or Excel file to begin.")
    st.stop()

# Cache expensive recomputations after filtering
@st.cache_data
def get_filtered_metrics(_df):
    total_claims = len(_df)
    total_amount = _df['AMOUNT'].sum()
    unique_members = _df['MEMBER NUMBER'].nunique()
    duplicate_count = _df[_df.duplicated(subset=['MEMBER NUMBER', 'ARRIVAL DATE', 'AMOUNT', 'PROVIDER NAME'], keep=False)].shape[0]
    return total_claims, total_amount, unique_members, duplicate_count

total_claims, total_amount, unique_members, duplicate_count = get_filtered_metrics(df)

# =========================
# KPI ROW
# =========================
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("💰 Total Claims", f"{total_claims:,}")
col2.metric("💵 Total Amount", f"${total_amount:,.2f}")
col3.metric("👥 Unique Members", f"{unique_members:,}")
col4.metric("⚠️ Duplicate Claims", f"{duplicate_count:,}")
col5.metric("🚨 Fraud Flags (Prov-Ben)", f"{len(fraud_flags):,}")

st.markdown("---")

# =========================
# TABS FOR ALL VISUALS
# =========================
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
    "📊 Provider Risk", "🚨 Fraud Detection", "📈 Time Series", "👤 Member Analysis",
    "🏷️ Category & Benefit", "🌍 Roaming Analysis", "📋 Data Explorer", "📥 Download Reports"
])

# ------------------------- TAB 1: Provider Risk -------------------------
with tab1:
    st.subheader("Provider Risk Score Dashboard")
    st.markdown("**Risk Score Formula:** 50% Avg Cost/Visit + 30% Total Claims + 20% Unique Members (percentile ranks)")

    # Top risky providers
    top_risk = provider_stats.head(10)
    colA, colB = st.columns([2, 1])
    with colA:
        fig_risk = px.bar(top_risk, x='PROVIDER NAME', y='RISK_SCORE', color='RISK_SCORE',
                          title="Top 10 High-Risk Providers", color_continuous_scale='Reds')
        st.plotly_chart(fig_risk, use_container_width=True)
    with colB:
        st.dataframe(top_risk[['PROVIDER NAME', 'RISK_SCORE', 'TOTAL_COST', 'UNIQUE_VISITS', 'AVG_COST_PER_VISIT']])

    # Scatter: Avg Cost vs Total Claims
    fig_scatter = px.scatter(provider_stats, x='AVG_COST_PER_VISIT', y='TOTAL_CLAIMS', size='TOTAL_COST',
                             hover_name='PROVIDER NAME', color='RISK_SCORE', color_continuous_scale='Viridis',
                             title="Provider Risk Scatter Plot (Size = Total Cost)")
    st.plotly_chart(fig_scatter, use_container_width=True)

    # Cost distribution per provider (boxplot)
    fig_box = px.box(df, x='PROVIDER NAME', y='AMOUNT', title="Amount Distribution by Provider", height=500)
    st.plotly_chart(fig_box, use_container_width=True)

# ------------------------- TAB 2: Fraud Detection -------------------------
with tab2:
    st.subheader("Anomaly & Fraud Indicators")
    # Duplicate claims
    if not duplicates.empty:
        st.warning(f"⚠️ Found {len(duplicates)} duplicate claim rows")
        st.dataframe(duplicates[['CLAIM ID', 'MEMBER NUMBER', 'PROVIDER NAME', 'ARRIVAL DATE', 'AMOUNT', 'BENEFIT DESC']])
    else:
        st.success("No duplicate claims detected")

    # Provider-Benefit anomalies
    if not fraud_flags.empty:
        st.error(f"🚨 {len(fraud_flags)} high-risk provider-benefit pairs (Z-score > 2)")
        fig_z = px.bar(fraud_flags, x='PROVIDER NAME', y='Z_SCORE', color='BENEFIT DESC',
                       title="Anomaly Score by Provider & Benefit", color_discrete_sequence=px.colors.qualitative.Set1)
        st.plotly_chart(fig_z, use_container_width=True)
        st.dataframe(fraud_flags[['PROVIDER NAME', 'BENEFIT DESC', 'AVG_COST_PER_VISIT', 'Z_SCORE']])
    else:
        st.info("No significant provider-benefit anomalies")

    # High frequency members
    if not high_freq_members.empty:
        st.subheader("Members with Unusually High Claim Volume")
        st.dataframe(high_freq_members[['MEMBER NUMBER', 'PROVIDER NAME', 'ARRIVAL DATE', 'AMOUNT', 'CLAIM ID']])

    # Z-score distribution histogram
    fig_hist = px.histogram(fraud_flags, x='Z_SCORE', nbins=30, title="Distribution of Z-Scores (Anomalies)")
    st.plotly_chart(fig_hist, use_container_width=True)

# ------------------------- TAB 3: Time Series -------------------------
with tab3:
    st.subheader("Claims Over Time")
    # Aggregate by month
    monthly = df.groupby('YEAR_MONTH').agg(
        Total_Amount=('AMOUNT', 'sum'),
        Claim_Count=('CLAIM ID', 'count')
    ).reset_index()
    monthly['YEAR_MONTH'] = monthly['YEAR_MONTH'].astype(str)

    fig_ts = make_subplots(specs=[[{"secondary_y": True}]])
    fig_ts.add_trace(go.Scatter(x=monthly['YEAR_MONTH'], y=monthly['Total_Amount'], name="Total Amount ($)", line=dict(color='blue')), secondary_y=False)
    fig_ts.add_trace(go.Bar(x=monthly['YEAR_MONTH'], y=monthly['Claim_Count'], name="Claim Count", marker_color='orange'), secondary_y=True)
    fig_ts.update_xaxes(title="Month")
    fig_ts.update_yaxes(title="Amount ($)", secondary_y=False)
    fig_ts.update_yaxes(title="Claim Count", secondary_y=True)
    fig_ts.update_layout(title="Monthly Claims Trend", height=500)
    st.plotly_chart(fig_ts, use_container_width=True)

    # Day of week pattern
    dow_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    df['DAY_NAME'] = df['ARRIVAL DATE'].dt.day_name()
    dow_counts = df.groupby('DAY_NAME').size().reindex(dow_order).reset_index()
    dow_counts.columns = ['Day', 'Claim Count']
    fig_dow = px.bar(dow_counts, x='Day', y='Claim Count', title="Claims by Day of Week", color='Claim Count')
    st.plotly_chart(fig_dow, use_container_width=True)

    # Roaming vs Non-Roaming over time
    roaming_ts = df.groupby(['YEAR_MONTH', 'IS_ROAMER'])['AMOUNT'].sum().reset_index()
    roaming_ts['YEAR_MONTH'] = roaming_ts['YEAR_MONTH'].astype(str)
    fig_roam = px.line(roaming_ts, x='YEAR_MONTH', y='AMOUNT', color='IS_ROAMER', title="Roaming vs Non-Roaming Claim Amount Trend")
    st.plotly_chart(fig_roam, use_container_width=True)

# ------------------------- TAB 4: Member Analysis -------------------------
with tab4:
    st.subheader("Member-Level Insights")
    # Top members by total amount
    member_spend = df.groupby('MEMBER NUMBER')['AMOUNT'].sum().sort_values(ascending=False).head(10).reset_index()
    fig_member = px.bar(member_spend, x='MEMBER NUMBER', y='AMOUNT', title="Top 10 Members by Total Claim Amount", color='AMOUNT')
    st.plotly_chart(fig_member, use_container_width=True)

    # Member age distribution
    fig_age = px.histogram(df, x='AGE', nbins=30, title="Member Age Distribution (at claim date)", color_discrete_sequence=['green'])
    st.plotly_chart(fig_age, use_container_width=True)

    # Duplicate claims per member
    dup_members = duplicates.groupby('MEMBER NUMBER').size().reset_index(name='Duplicate Count')
    if not dup_members.empty:
        st.dataframe(dup_members.sort_values('Duplicate Count', ascending=False))

# ------------------------- TAB 5: Category & Benefit -------------------------
with tab5:
    st.subheader("Claim Categories & Benefits")
    # Treemap for CAT DESC
    cat_agg = df.groupby('CAT DESC')['AMOUNT'].sum().reset_index()
    fig_treemap = px.treemap(cat_agg, path=['CAT DESC'], values='AMOUNT', title="Total Amount by Category (Treemap)", height=500)
    st.plotly_chart(fig_treemap, use_container_width=True)

    # Sunburst for CAT DESC + BENEFIT DESC
    sunburst_data = df.groupby(['CAT DESC', 'BENEFIT DESC'])['AMOUNT'].sum().reset_index()
    fig_sunburst = px.sunburst(sunburst_data, path=['CAT DESC', 'BENEFIT DESC'], values='AMOUNT',
                               title="Hierarchy: Category → Benefit", height=600)
    st.plotly_chart(fig_sunburst, use_container_width=True)

    # Horizontal bar for top benefits
    benefit_top = df.groupby('BENEFIT DESC')['AMOUNT'].sum().sort_values(ascending=False).head(15).reset_index()
    fig_benefit = px.bar(benefit_top, y='BENEFIT DESC', x='AMOUNT', orientation='h', title="Top 15 Benefits by Total Amount")
    st.plotly_chart(fig_benefit, use_container_width=True)

# ------------------------- TAB 6: Roaming Analysis -------------------------
with tab6:
    st.subheader("Roaming Claims Deep Dive")
    # Roaming amount by country (split multiple countries)
    roaming_df = df[df['IS_ROAMER'] == True].copy()
    if not roaming_df.empty:
        # Some rows might have multiple countries separated by commas? We'll assume a single country string
        country_agg = roaming_df.groupby('ROAMING COUNTRIES')['AMOUNT'].sum().sort_values(ascending=False).reset_index()
        fig_country = px.bar(country_agg, x='ROAMING COUNTRIES', y='AMOUNT', title="Total Amount by Roaming Country")
        st.plotly_chart(fig_country, use_container_width=True)

        # Roaming over time
        roam_month = roaming_df.groupby('YEAR_MONTH')['AMOUNT'].sum().reset_index()
        roam_month['YEAR_MONTH'] = roam_month['YEAR_MONTH'].astype(str)
        fig_roam_time = px.line(roam_month, x='YEAR_MONTH', y='AMOUNT', title="Roaming Amount Trend")
        st.plotly_chart(fig_roam_time, use_container_width=True)

        st.dataframe(roaming_df[['CLAIM ID', 'MEMBER NUMBER', 'ROAMING COUNTRIES', 'AMOUNT', 'PROVIDER NAME']].head(100))
    else:
        st.info("No roaming claims in the filtered data")

# ------------------------- TAB 7: Data Explorer -------------------------
with tab7:
    st.subheader("Interactive Claims Data Table")
    st.dataframe(df, use_container_width=True, height=600)

# ------------------------- TAB 8: Download Reports -------------------------
with tab8:
    st.subheader("Export Results")
    colD1, colD2, colD3, colD4 = st.columns(4)
    with colD1:
        csv_provider = provider_stats.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Provider Risk CSV", csv_provider, "provider_risk.csv", "text/csv")
    with colD2:
        csv_duplicates = duplicates.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Duplicate Claims CSV", csv_duplicates, "duplicate_claims.csv", "text/csv")
    with colD3:
        csv_fraud = fraud_flags.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Fraud Flags CSV", csv_fraud, "fraud_flags.csv", "text/csv")
    with colD4:
        csv_filtered = df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Filtered Data CSV", csv_filtered, "filtered_claims.csv", "text/csv")

st.markdown("---")
st.caption("🎯 Built with Streamlit, Plotly & Pandas – Healthcare Claims Analytics & Fraud Detection")