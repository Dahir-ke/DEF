import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import warnings
warnings.filterwarnings('ignore')

# ============================================
# PAGE CONFIG
# ============================================
st.set_page_config(page_title="Healthcare Claims Analytics", page_icon="🏥", layout="wide")

# ============================================
# CUSTOM CSS
# ============================================
st.markdown("""
<style>
    .stApp { background-color: #f5f9fc; }
    .css-1d391kg { background-color: #ffffff; border-right: 1px solid #e0e7ed; }
    .kpi-card {
        background: white; border-radius: 16px; padding: 1rem;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04); border: 1px solid #e9ecef;
        text-align: center;
    }
    .kpi-label { font-size: 0.85rem; font-weight: 500; color: #5a6e7c; letter-spacing: 0.5px; }
    .kpi-value { font-size: 1.9rem; font-weight: 700; color: #1f3b4c; line-height: 1.2; }
    .kpi-delta { font-size: 0.85rem; margin-top: 4px; }
    .kpi-unit { font-size: 0.85rem; color: #7c8f9c; }
    h1, h2, h3 { color: #1a4a6e; font-weight: 600; }
    .stTabs [data-baseweb="tab-list"] {
        gap: 0.5rem; background-color: white; padding: 0.5rem 1rem;
        border-radius: 40px; box-shadow: 0 1px 2px rgba(0,0,0,0.05);
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 30px; padding: 0.5rem 1.2rem; font-weight: 500;
        color: #2c5a7a; background-color: #f0f4f8;
    }
    .stTabs [aria-selected="true"] { background-color: #1a6f8c; color: white; }
    .stDataFrame { border-radius: 12px; overflow: hidden; }
</style>
""", unsafe_allow_html=True)

# ============================================
# DATA LOADING
# ============================================
@st.cache_data
def load_data(filepath):
    df = pd.read_excel(filepath)
    df.columns = df.columns.str.strip()
    
    required = ['CLAIM ID', 'MEMBER NUMBER', 'PATIENT NAME', 'SERVICE TYPE',
                'BENEFIT DESC', 'MAIN HOSPITAL', 'AMOUNT', 'ARRIVAL DATE', 
                'TRANSACTION DATE', 'DOB']
    for col in required:
        if col not in df.columns:
            st.error(f"Missing column: {col}")
            st.stop()
    
    df['ARRIVAL DATE'] = pd.to_datetime(df['ARRIVAL DATE'], errors='coerce')
    df['TRANSACTION DATE'] = pd.to_datetime(df['TRANSACTION DATE'], errors='coerce')
    df['DOB'] = pd.to_datetime(df['DOB'], errors='coerce')
    df['AMOUNT'] = pd.to_numeric(df['AMOUNT'], errors='coerce')
    
    df = df.dropna(subset=['AMOUNT', 'ARRIVAL DATE', 'MEMBER NUMBER'])
    
    df['VISIT_KEY'] = (df['MEMBER NUMBER'].astype(str) + '_' +
                       df['ARRIVAL DATE'].dt.strftime('%Y-%m-%d') + '_' +
                       df['SERVICE TYPE'].astype(str))
    
    df['AGE_AT_VISIT'] = (df['ARRIVAL DATE'] - df['DOB']).dt.days // 365
    df['AGE_AT_VISIT'] = df['AGE_AT_VISIT'].clip(0, 120)
    return df

DATA_PATH = "data/visits for an-april-2026.xlsx"
try:
    df = load_data(DATA_PATH)
    st.sidebar.success(f"✅ Loaded {df.shape[0]:,} rows")
except Exception as e:
    st.error(f"Failed to load data: {e}")
    st.stop()

# ============================================
# SIDEBAR FILTERS
# ============================================
st.sidebar.title("🎛️ Dashboard Filters")
min_date = df['TRANSACTION DATE'].min().date()
max_date = df['TRANSACTION DATE'].max().date()
date_range = st.sidebar.date_input("Transaction Date Range", [min_date, max_date],
                                    min_value=min_date, max_value=max_date)
all_services = df['SERVICE TYPE'].dropna().unique().tolist()
selected_services = st.sidebar.multiselect("Service Type", all_services, default=all_services)
all_hospitals = df['MAIN HOSPITAL'].dropna().unique().tolist()
selected_hospitals = st.sidebar.multiselect("Hospital (optional)", all_hospitals, default=[])

df_filtered = df.copy()
if len(date_range) == 2:
    start, end = date_range
    df_filtered = df_filtered[(df_filtered['TRANSACTION DATE'].dt.date >= start) &
                              (df_filtered['TRANSACTION DATE'].dt.date <= end)]
if selected_services:
    df_filtered = df_filtered[df_filtered['SERVICE TYPE'].isin(selected_services)]
if selected_hospitals:
    df_filtered = df_filtered[df_filtered['MAIN HOSPITAL'].isin(selected_hospitals)]
if df_filtered.empty:
    st.sidebar.warning("No data matches filters. Showing all data.")
    df_filtered = df.copy()

# ============================================
# KPIs
# ============================================
total_cost = df_filtered['AMOUNT'].sum()
total_claims = df_filtered['CLAIM ID'].nunique()
total_visits = df_filtered['VISIT_KEY'].nunique()
ip_amount = df_filtered[df_filtered['SERVICE TYPE'] == 'IP']['AMOUNT'].sum()
ip_pct = (ip_amount / total_cost * 100) if total_cost > 0 else 0

monthly_total = df_filtered.groupby(df_filtered['TRANSACTION DATE'].dt.to_period('M'))['AMOUNT'].sum()
if len(monthly_total) >= 2:
    amount_mom = (monthly_total.iloc[-1] - monthly_total.iloc[-2]) / monthly_total.iloc[-2] * 100
else:
    amount_mom = 0

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-label">💰 TOTAL CLAIMS VALUE</div>
        <div class="kpi-value">Ksh {total_cost/1e6:.1f}M</div>
        <div class="kpi-delta" style="color: {'#2e7d64' if amount_mom >= 0 else '#c73e3e'}">
            {'▲' if amount_mom >= 0 else '▼'} {abs(amount_mom):.1f}% vs prev month
        </div>
        <div class="kpi-unit">{total_cost:,.0f} KES</div>
    </div>
    """, unsafe_allow_html=True)
with col2:
    st.markdown(f"<div class='kpi-card'><div class='kpi-label'>📄 TOTAL CLAIMS</div><div class='kpi-value'>{total_claims:,}</div></div>", unsafe_allow_html=True)
with col3:
    st.markdown(f"<div class='kpi-card'><div class='kpi-label'>👥 UNIQUE VISITS</div><div class='kpi-value'>{total_visits:,}</div></div>", unsafe_allow_html=True)
with col4:
    st.markdown(f"<div class='kpi-card'><div class='kpi-label'>🏥 INPATIENT SHARE</div><div class='kpi-value'>{ip_pct:.1f}%</div></div>", unsafe_allow_html=True)

st.markdown("---")

# ============================================
# TABS
# ============================================
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📊 Service & Benefit", "🏥 Provider Scorecard", "📈 Monthly Trends",
    "⚠️ Outlier Detection", "🔍 Member Lookup", "🔄 Retention & Export"
])

# ---------- TAB 1 ----------
with tab1:
    st.subheader("Service Type Breakdown")
    service_agg = df_filtered.groupby('SERVICE TYPE').agg(TOTAL=('AMOUNT', 'sum'), VISITS=('VISIT_KEY', 'nunique')).reset_index()
    fig1 = px.bar(service_agg, x='SERVICE TYPE', y='TOTAL',
                  text=service_agg['TOTAL'].apply(lambda x: f'Ksh {x/1e6:.1f}M'),
                  color='TOTAL', color_continuous_scale='Tealgrn')
    fig1.update_traces(textposition='outside')
    st.plotly_chart(fig1, use_container_width=True)

    st.subheader("Benefit Description Summary")
    benefit = df_filtered.groupby('BENEFIT DESC').agg(Visits=('VISIT_KEY', 'nunique'), Amount=('AMOUNT', 'sum')).reset_index().sort_values('Amount', ascending=False)
    benefit['Avg per Visit'] = benefit['Amount'] / benefit['Visits']
    benefit['Amount'] = benefit['Amount'].apply(lambda x: f'Ksh {x:,.0f}')
    benefit['Avg per Visit'] = benefit['Avg per Visit'].apply(lambda x: f'Ksh {x:,.0f}')
    st.dataframe(benefit, use_container_width=True, hide_index=True)

# ---------- TAB 2 ----------
with tab2:
    st.subheader("Provider Efficiency Scorecard")
    provider = df_filtered.groupby('MAIN HOSPITAL').agg(
        TOTAL_COST=('AMOUNT', 'sum'),
        UNIQUE_VISITS=('VISIT_KEY', 'nunique'),
        UNIQUE_PATIENTS=('MEMBER NUMBER', 'nunique')
    ).reset_index()
    provider['COST_PER_VISIT'] = provider['TOTAL_COST'] / provider['UNIQUE_VISITS']
    provider['COST_PER_PATIENT'] = provider['TOTAL_COST'] / provider['UNIQUE_PATIENTS']
    
    def first_hosp(g): return g.loc[g['ARRIVAL DATE'].idxmin(), 'MAIN HOSPITAL']
    def last_hosp(g): return g.loc[g['ARRIVAL DATE'].idxmax(), 'MAIN HOSPITAL']
    first = df_filtered.groupby('MEMBER NUMBER').apply(first_hosp).reset_index(name='FIRST')
    last = df_filtered.groupby('MEMBER NUMBER').apply(last_hosp).reset_index(name='LAST')
    merged = first.merge(last, on='MEMBER NUMBER')
    merged['SWITCHED'] = merged['FIRST'] != merged['LAST']
    retention = merged.groupby('FIRST').agg(PATIENTS=('MEMBER NUMBER', 'count'), SWITCHED=('SWITCHED', 'sum')).reset_index()
    retention['RETAINED'] = retention['PATIENTS'] - retention['SWITCHED']
    retention['RETENTION_RATE'] = retention['RETAINED'] / retention['PATIENTS'] * 100
    retention.columns = ['MAIN HOSPITAL', 'PATIENTS_STARTED', 'SWITCHED', 'RETAINED', 'RETENTION_RATE']
    provider = provider.merge(retention[['MAIN HOSPITAL', 'RETENTION_RATE']], on='MAIN HOSPITAL', how='left')
    provider['RETENTION_RATE'] = provider['RETENTION_RATE'].fillna(100)
    
    top_providers = provider.nlargest(15, 'TOTAL_COST')
    st.dataframe(top_providers[['MAIN HOSPITAL', 'TOTAL_COST', 'UNIQUE_VISITS', 'COST_PER_VISIT',
                                 'COST_PER_PATIENT', 'RETENTION_RATE']],
                 use_container_width=True, hide_index=True,
                 column_config={
                     'TOTAL_COST': st.column_config.NumberColumn(format="Ksh %.0f"),
                     'COST_PER_VISIT': st.column_config.NumberColumn(format="Ksh %.0f"),
                     'COST_PER_PATIENT': st.column_config.NumberColumn(format="Ksh %.0f"),
                     'RETENTION_RATE': st.column_config.NumberColumn(format="%.1f%%")
                 })
    
    fig_eff = px.scatter(provider, x='COST_PER_VISIT', y='RETENTION_RATE',
                         size='TOTAL_COST', hover_name='MAIN HOSPITAL',
                         title='Cost per Visit vs Retention Rate',
                         labels={'COST_PER_VISIT': 'Avg Cost per Visit (Ksh)',
                                 'RETENTION_RATE': 'Retention Rate (%)'},
                         color='TOTAL_COST', color_continuous_scale='Viridis')
    st.plotly_chart(fig_eff, use_container_width=True)

# ---------- TAB 3 (FIXED) ----------
with tab3:
    st.subheader("Monthly Performance with MoM Changes")
    monthly = df_filtered.groupby(df_filtered['TRANSACTION DATE'].dt.to_period('M')).agg(
        AMOUNT=('AMOUNT', 'sum'),
        CLAIMS=('CLAIM ID', 'count'),
        VISITS=('VISIT_KEY', 'nunique')
    ).reset_index()
    monthly['MONTH_NAME'] = monthly['TRANSACTION DATE'].dt.strftime('%b')
    monthly['AMOUNT_MOM'] = monthly['AMOUNT'].pct_change() * 100
    monthly['CLAIMS_MOM'] = monthly['CLAIMS'].pct_change() * 100
    monthly['VISITS_MOM'] = monthly['VISITS'].pct_change() * 100
    
    # Chart
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(x=monthly['MONTH_NAME'], y=monthly['AMOUNT'],
                         name='Amount (Ksh)', marker_color='#2c7a7a'), secondary_y=False)
    fig.add_trace(go.Scatter(x=monthly['MONTH_NAME'], y=monthly['CLAIMS'],
                             name='Claims', mode='lines+markers',
                             line=dict(color='#f4a261', width=3)), secondary_y=True)
    fig.add_trace(go.Scatter(x=monthly['MONTH_NAME'], y=monthly['VISITS'],
                             name='Unique Visits', mode='lines+markers',
                             line=dict(color='#2a9d8f', dash='dot')), secondary_y=True)
    fig.update_layout(title='Monthly Trends', height=450, hovermode='x unified')
    fig.update_yaxes(title_text="Amount (Ksh)", secondary_y=False)
    fig.update_yaxes(title_text="Count", secondary_y=True)
    st.plotly_chart(fig, use_container_width=True)
    
    # MoM table - FIX: format only numeric columns
    st.subheader("Month-over-Month Change (%)")
    mom_table = monthly[['MONTH_NAME', 'AMOUNT_MOM', 'CLAIMS_MOM', 'VISITS_MOM']].dropna()
    if not mom_table.empty:
        # Convert to numeric (already is, but ensure)
        for col in ['AMOUNT_MOM', 'CLAIMS_MOM', 'VISITS_MOM']:
            mom_table[col] = pd.to_numeric(mom_table[col], errors='coerce')
        # Apply formatting only to numeric columns
        styled = mom_table.style.format({
            'AMOUNT_MOM': '{:.1f}%',
            'CLAIMS_MOM': '{:.1f}%',
            'VISITS_MOM': '{:.1f}%'
        })
        st.dataframe(styled, use_container_width=True)
    else:
        st.info("Not enough months to calculate MoM changes.")

# ---------- TAB 4 ----------
with tab4:
    st.subheader("Cost Outlier Detection (Top 1% Claims)")
    if len(df_filtered) > 0:
        threshold = df_filtered['AMOUNT'].quantile(0.99)
        outliers = df_filtered[df_filtered['AMOUNT'] >= threshold]
        st.metric("99th Percentile Threshold", f"Ksh {threshold:,.0f}")
        st.write(f"**{len(outliers)} claims** exceed this threshold (top 1%).")
        if not outliers.empty:
            st.dataframe(outliers[['CLAIM ID', 'MEMBER NUMBER', 'PATIENT NAME',
                                   'MAIN HOSPITAL', 'AMOUNT', 'SERVICE TYPE']].head(50),
                         use_container_width=True,
                         column_config={'AMOUNT': st.column_config.NumberColumn(format="Ksh %.0f")})
        sample = df_filtered.sample(min(5000, len(df_filtered)))
        fig_out = px.scatter(sample, x='TRANSACTION DATE', y='AMOUNT',
                             color='SERVICE TYPE', title='Claim Amount Distribution (sampled)',
                             labels={'AMOUNT': 'Claim Amount (Ksh)'})
        fig_out.add_hline(y=threshold, line_dash="dash", line_color="red",
                          annotation_text=f"99th percentile: {threshold:,.0f}")
        st.plotly_chart(fig_out, use_container_width=True)
    else:
        st.info("No data for outlier analysis.")

# ---------- TAB 5 ----------
with tab5:
    st.subheader("Member Lookup")
    search_term = st.text_input("Enter Member Number or Patient Name")
    if search_term:
        mask = (df_filtered['MEMBER NUMBER'].astype(str).str.contains(search_term, case=False) |
                df_filtered['PATIENT NAME'].str.contains(search_term, case=False))
        result = df_filtered[mask]
        if not result.empty:
            st.success(f"Found {result['MEMBER NUMBER'].nunique()} matching member(s)")
            for member in result['MEMBER NUMBER'].unique()[:10]:
                with st.expander(f"Member: {member}"):
                    member_data = result[result['MEMBER NUMBER'] == member]
                    total = member_data['AMOUNT'].sum()
                    st.metric("Total Claimed", f"Ksh {total:,.0f}")
                    st.dataframe(member_data[['ARRIVAL DATE', 'MAIN HOSPITAL',
                                              'SERVICE TYPE', 'AMOUNT']],
                                 column_config={'AMOUNT': st.column_config.NumberColumn(format="Ksh %.0f")})
        else:
            st.warning("No matching member found.")

# ---------- TAB 6 ----------
with tab6:
    st.subheader("Patient Retention Analysis")
    def first_hosp(g): return g.loc[g['ARRIVAL DATE'].idxmin(), 'MAIN HOSPITAL']
    def last_hosp(g): return g.loc[g['ARRIVAL DATE'].idxmax(), 'MAIN HOSPITAL']
    first = df_filtered.groupby('MEMBER NUMBER').apply(first_hosp).reset_index(name='FIRST')
    last = df_filtered.groupby('MEMBER NUMBER').apply(last_hosp).reset_index(name='LAST')
    merged = first.merge(last, on='MEMBER NUMBER')
    merged['SWITCHED'] = merged['FIRST'] != merged['LAST']
    switch_stats = merged.groupby('FIRST').agg(Patients=('MEMBER NUMBER', 'count'), Switched=('SWITCHED', 'sum')).reset_index()
    switch_stats['Retained'] = switch_stats['Patients'] - switch_stats['Switched']
    switch_stats['Retention %'] = switch_stats['Retained'] / switch_stats['Patients'] * 100
    top_switch = switch_stats.nlargest(10, 'Switched')
    if not top_switch.empty:
        fig_switch = px.bar(top_switch, x='Switched', y='FIRST', orientation='h',
                            text='Switched', color='Retention %', color_continuous_scale='Reds',
                            title='Hospitals with Most Patients Ending at Different Hospital')
        fig_switch.update_traces(texttemplate='%{text}', textposition='outside')
        fig_switch.update_layout(height=450, margin=dict(l=150))
        st.plotly_chart(fig_switch, use_container_width=True)
    else:
        st.info("Not enough data for switching analysis.")
    
    st.subheader("Export Data")
    csv = df_filtered.to_csv(index=False).encode('utf-8')
    st.download_button("📥 Download Filtered Data as CSV", data=csv,
                       file_name="filtered_claims.csv", mime="text/csv")
    st.caption(f"Filtered dataset: {len(df_filtered):,} rows | {df_filtered['MEMBER NUMBER'].nunique():,} unique members")

st.markdown("---")
st.caption("Healthcare Claims Dashboard | Built with Streamlit & Plotly | Data period: Jan–Apr 2026")