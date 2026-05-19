import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import warnings
warnings.filterwarnings('ignore')

# ============================================
# PAGE CONFIG
# ============================================
st.set_page_config(page_title="Management Insights Dashboard", page_icon="📈", layout="wide")

# ============================================
# CUSTOM CSS (Clean Blue/White)
# ============================================
st.markdown("""
<style>
    .stApp { background-color: #f4f8fc; }
    .main-title {
        background: linear-gradient(90deg, #1e3c72 0%, #2a5298 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin-bottom: 1.5rem;
    }
    .insight-card {
        background: white;
        border-radius: 12px;
        padding: 1rem;
        margin-bottom: 1rem;
        border-left: 5px solid #2a5298;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
    }
    .bad { border-left-color: #dc3545; background-color: #fff5f5; }
    .good { border-left-color: #28a745; background-color: #f0fff4; }
    .kpi {
        background: white;
        border-radius: 12px;
        padding: 0.8rem;
        text-align: center;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .kpi-number { font-size: 2rem; font-weight: 700; color: #1e3c72; }
    .kpi-label { font-size: 0.8rem; color: #4a627a; text-transform: uppercase; }
    hr { margin: 0.5rem 0; }
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
                'BENEFIT DESC', 'MAIN HOSPITAL', 'AMOUNT', 'ARRIVAL DATE', 'TRANSACTION DATE']
    for col in required:
        if col not in df.columns:
            st.error(f"Missing column: {col}")
            st.stop()
    df['ARRIVAL DATE'] = pd.to_datetime(df['ARRIVAL DATE'], errors='coerce')
    df['TRANSACTION DATE'] = pd.to_datetime(df['TRANSACTION DATE'], errors='coerce')
    df['AMOUNT'] = pd.to_numeric(df['AMOUNT'], errors='coerce')
    df = df.dropna(subset=['AMOUNT', 'ARRIVAL DATE', 'MEMBER NUMBER', 'MAIN HOSPITAL'])
    df['VISIT_KEY'] = (df['MEMBER NUMBER'].astype(str) + '_' +
                       df['ARRIVAL DATE'].dt.strftime('%Y-%m-%d') + '_' +
                       df['SERVICE TYPE'].astype(str))
    return df

DATA_PATH = "data/visits for an-april-2026.xlsx"
try:
    df = load_data(DATA_PATH)
    st.sidebar.success(f"✅ Data loaded: {df.shape[0]:,} rows")
except Exception as e:
    st.error(f"Error loading data: {e}")
    st.stop()

# ============================================
# SIDEBAR FILTERS (simple)
# ============================================
st.sidebar.title("🎯 Filters")
min_date = df['TRANSACTION DATE'].min().date()
max_date = df['TRANSACTION DATE'].max().date()
date_range = st.sidebar.date_input("Period", [min_date, max_date], min_value=min_date, max_value=max_date)
if len(date_range) == 2:
    start, end = date_range
    df = df[(df['TRANSACTION DATE'].dt.date >= start) & (df['TRANSACTION DATE'].dt.date <= end)]

# ============================================
# CORE METRICS
# ============================================
total_visits = df['VISIT_KEY'].nunique()
total_cost = df['AMOUNT'].sum()
avg_cost_per_visit = total_cost / total_visits if total_visits > 0 else 0
unique_patients = df['MEMBER NUMBER'].nunique()

# ============================================
# HOSPITAL METRICS (for comparison)
# ============================================
hosp = df.groupby('MAIN HOSPITAL').agg(
    Total_Cost=('AMOUNT', 'sum'),
    Visits=('VISIT_KEY', 'nunique'),
    Patients=('MEMBER NUMBER', 'nunique')
).reset_index()
hosp['Cost_per_Visit'] = hosp['Total_Cost'] / hosp['Visits']
hosp['Cost_per_Patient'] = hosp['Total_Cost'] / hosp['Patients']

# Retention: % of patients whose first and last hospital are the same
def first_hosp(g): return g.loc[g['ARRIVAL DATE'].idxmin(), 'MAIN HOSPITAL']
def last_hosp(g): return g.loc[g['ARRIVAL DATE'].idxmax(), 'MAIN HOSPITAL']
first = df.groupby('MEMBER NUMBER').apply(first_hosp).reset_index(name='FIRST')
last = df.groupby('MEMBER NUMBER').apply(last_hosp).reset_index(name='LAST')
merged = first.merge(last, on='MEMBER NUMBER')
merged['Stayed'] = merged['FIRST'] == merged['LAST']
retention = merged.groupby('FIRST').agg(Patients=('MEMBER NUMBER', 'count'), Stayed=('Stayed', 'sum')).reset_index()
retention['Retention_Rate'] = retention['Stayed'] / retention['Patients'] * 100
retention.columns = ['MAIN HOSPITAL', 'Patients_Ret', 'Stayed', 'Retention_Rate']
hosp = hosp.merge(retention[['MAIN HOSPITAL', 'Retention_Rate']], on='MAIN HOSPITAL', how='left')
hosp['Retention_Rate'] = hosp['Retention_Rate'].fillna(100)

# Benchmark overall averages
avg_cost_per_visit_overall = hosp['Cost_per_Visit'].mean()
avg_retention_overall = hosp['Retention_Rate'].mean()

# Flag hospitals as "Good" or "Bad" based on cost vs avg and retention vs avg
hosp['Cost_Efficiency'] = hosp['Cost_per_Visit'].apply(lambda x: 'Below Avg' if x < avg_cost_per_visit_overall else 'Above Avg')
hosp['Retention_Status'] = hosp['Retention_Rate'].apply(lambda x: 'Above Avg' if x > avg_retention_overall else 'Below Avg')
hosp['Performance'] = hosp.apply(lambda row: 
    '⭐ Star' if row['Cost_per_Visit'] < avg_cost_per_visit_overall and row['Retention_Rate'] > avg_retention_overall else
    '⚠️ Watch' if row['Cost_per_Visit'] > avg_cost_per_visit_overall and row['Retention_Rate'] < avg_retention_overall else
    '📉 Concern' if row['Cost_per_Visit'] > avg_cost_per_visit_overall and row['Retention_Rate'] < 50 else
    '🟢 Average', axis=1)

# ============================================
# DASHBOARD
# ============================================
st.markdown('<div class="main-title"><h1 style="color:white;">📊 Management Insights Dashboard</h1><p style="color:#cfdfee;">Actionable intelligence on hospital performance, patient retention, and cost efficiency</p></div>', unsafe_allow_html=True)

# Top KPI row
col1, col2, col3, col4 = st.columns(4)
col1.markdown(f'<div class="kpi"><div class="kpi-number">{total_visits:,}</div><div class="kpi-label">Unique Visits</div></div>', unsafe_allow_html=True)
col2.markdown(f'<div class="kpi"><div class="kpi-number">Ksh {total_cost/1e6:.1f}M</div><div class="kpi-label">Total Cost</div></div>', unsafe_allow_html=True)
col3.markdown(f'<div class="kpi"><div class="kpi-number">Ksh {avg_cost_per_visit:,.0f}</div><div class="kpi-label">Avg Cost / Visit</div></div>', unsafe_allow_html=True)
col4.markdown(f'<div class="kpi"><div class="kpi-number">{unique_patients:,}</div><div class="kpi-label">Unique Patients</div></div>', unsafe_allow_html=True)

st.markdown("---")

# ---------- SECTION 1: HOSPITAL RANKING (Cost Efficiency) ----------
st.subheader("🏥 Hospital Cost Efficiency (Avg Cost per Visit)")
top_hosp = hosp.nlargest(10, 'Cost_per_Visit')
bottom_hosp = hosp.nsmallest(10, 'Cost_per_Visit')

colA, colB = st.columns(2)
with colA:
    fig_high = px.bar(top_hosp, x='Cost_per_Visit', y='MAIN HOSPITAL', orientation='h',
                      text=top_hosp['Cost_per_Visit'].apply(lambda x: f'Ksh {x:,.0f}'),
                      title='Highest Avg Cost per Visit (Inefficient)',
                      color='Cost_per_Visit', color_continuous_scale='Reds')
    fig_high.update_traces(textposition='outside')
    fig_high.update_layout(height=400, margin=dict(l=150))
    st.plotly_chart(fig_high, use_container_width=True)
with colB:
    fig_low = px.bar(bottom_hosp, x='Cost_per_Visit', y='MAIN HOSPITAL', orientation='h',
                     text=bottom_hosp['Cost_per_Visit'].apply(lambda x: f'Ksh {x:,.0f}'),
                     title='Lowest Avg Cost per Visit (Efficient)',
                     color='Cost_per_Visit', color_continuous_scale='Greens')
    fig_low.update_traces(textposition='outside')
    fig_low.update_layout(height=400, margin=dict(l=150))
    st.plotly_chart(fig_low, use_container_width=True)

st.markdown("---")

# ---------- SECTION 2: RETENTION & SWITCHING ANALYSIS ----------
st.subheader("🔄 Patient Retention: Which Hospitals Keep Patients?")
# Show hospitals with lowest retention
worst_retention = hosp.nsmallest(10, 'Retention_Rate')
fig_ret = px.bar(worst_retention, x='Retention_Rate', y='MAIN HOSPITAL', orientation='h',
                 text=worst_retention['Retention_Rate'].apply(lambda x: f'{x:.0f}%'),
                 title='Hospitals Losing Most Patients (First ≠ Last Visit)',
                 color='Retention_Rate', color_continuous_scale='Reds')
fig_ret.update_traces(textposition='outside')
fig_ret.update_layout(height=400, margin=dict(l=200))
st.plotly_chart(fig_ret, use_container_width=True)

# Insight comment
st.markdown("""
<div class="insight-card bad">
    <b>⚠️ Management Action Required</b><br>
    Hospitals with <b>low retention rates</b> (below 50%) are losing patients to competitors. 
    Investigate service quality, wait times, or billing issues at these facilities.
</div>
""", unsafe_allow_html=True)

st.markdown("---")

# ---------- SECTION 3: PERFORMANCE MATRIX (Star vs Watch) ----------
st.subheader("⭐ Hospital Performance Matrix")
# Filter to show only those with significant volume
hosp_display = hosp[hosp['Visits'] >= 10].copy()
fig_matrix = px.scatter(hosp_display, x='Cost_per_Visit', y='Retention_Rate',
                        size='Visits', color='Performance', hover_name='MAIN HOSPITAL',
                        title='Strategy Map: Cost per Visit vs Retention Rate (bubble size = visit volume)',
                        labels={'Cost_per_Visit': 'Avg Cost per Visit (Ksh)', 'Retention_Rate': 'Retention Rate (%)'},
                        color_discrete_map={'⭐ Star': '#28a745', '⚠️ Watch': '#ffc107', '📉 Concern': '#dc3545', '🟢 Average': '#17a2b8'})
fig_matrix.add_hline(y=avg_retention_overall, line_dash="dash", line_color="gray", annotation_text="Avg Retention")
fig_matrix.add_vline(x=avg_cost_per_visit_overall, line_dash="dash", line_color="gray", annotation_text="Avg Cost")
fig_matrix.update_layout(height=500)
st.plotly_chart(fig_matrix, use_container_width=True)

st.markdown(f"""
<div class="insight-card good">
    <b>💡 Strategic Insights</b><br>
    • <b>⭐ Star hospitals</b> (bottom‑right quadrant) have <b>low cost AND high retention</b> – benchmark their practices.<br>
    • <b>📉 Concern hospitals</b> (top‑left) have <b>high cost AND low retention</b> – immediate audit recommended.<br>
    • Overall average cost per visit: <b>Ksh {avg_cost_per_visit_overall:,.0f}</b> | Average retention: <b>{avg_retention_overall:.1f}%</b>.
</div>
""", unsafe_allow_html=True)

st.markdown("---")

# ---------- SECTION 4: BENEFIT COST ANOMALIES (Outliers per hospital) ----------
st.subheader("🏷️ Unusually High Cost for Specific Benefits")
# For each hospital, find benefits where cost per visit > 2x overall average for that benefit
benefit_overall = df.groupby('BENEFIT DESC').agg(Total_Cost=('AMOUNT', 'sum'), Visits=('VISIT_KEY', 'nunique')).reset_index()
benefit_overall['Avg_Cost_Benefit'] = benefit_overall['Total_Cost'] / benefit_overall['Visits']

hosp_benefit = df.groupby(['MAIN HOSPITAL', 'BENEFIT DESC']).agg(
    Hospital_Total=('AMOUNT', 'sum'),
    Hospital_Visits=('VISIT_KEY', 'nunique')
).reset_index()
hosp_benefit['Hospital_Avg'] = hosp_benefit['Hospital_Total'] / hosp_benefit['Hospital_Visits']
hosp_benefit = hosp_benefit.merge(benefit_overall[['BENEFIT DESC', 'Avg_Cost_Benefit']], on='BENEFIT DESC', how='left')
hosp_benefit['Ratio'] = hosp_benefit['Hospital_Avg'] / hosp_benefit['Avg_Cost_Benefit']
anomalies = hosp_benefit[(hosp_benefit['Ratio'] > 2) & (hosp_benefit['Hospital_Visits'] >= 5)].nlargest(20, 'Ratio')

if not anomalies.empty:
    st.dataframe(anomalies[['MAIN HOSPITAL', 'BENEFIT DESC', 'Hospital_Avg', 'Avg_Cost_Benefit', 'Ratio', 'Hospital_Visits']].style.format({
        'Hospital_Avg': 'Ksh {:,.0f}',
        'Avg_Cost_Benefit': 'Ksh {:,.0f}',
        'Ratio': '{:.1f}x'
    }), use_container_width=True, hide_index=True)
    st.markdown("""
    <div class="insight-card bad">
        <b>🚨 Potential Overcharging / Inefficiency</b><br>
        The table above shows hospitals where the <b>average cost for a specific benefit</b> is more than double the overall average for that benefit. 
        These should be reviewed for coding errors, fraud, or wasteful practices.
    </div>
    """, unsafe_allow_html=True)
else:
    st.info("No major anomalies detected (cost per benefit >2x average).")

st.markdown("---")

# ---------- SECTION 5: SUMMARY TABLE (All Hospitals) ----------
with st.expander("📋 Complete Hospital Metrics Table"):
    st.dataframe(hosp[['MAIN HOSPITAL', 'Total_Cost', 'Visits', 'Patients', 'Cost_per_Visit', 'Cost_per_Patient', 'Retention_Rate', 'Performance']].style.format({
        'Total_Cost': 'Ksh {:,.0f}',
        'Cost_per_Visit': 'Ksh {:,.0f}',
        'Cost_per_Patient': 'Ksh {:,.0f}',
        'Retention_Rate': '{:.1f}%'
    }), use_container_width=True, hide_index=True)

# Export
csv = hosp.to_csv(index=False).encode('utf-8')
st.download_button("📥 Download Hospital Metrics CSV", data=csv, file_name="hospital_insights.csv", mime="text/csv")