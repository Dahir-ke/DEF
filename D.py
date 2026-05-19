import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import warnings
warnings.filterwarnings('ignore')

# ------------------------------------------------------------
# PAGE CONFIGURATION
# ------------------------------------------------------------
st.set_page_config(
    page_title="Healthcare Intelligence",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ------------------------------------------------------------
# CUSTOM CSS – Clean, modern, no white-on-white issues
# ------------------------------------------------------------
st.markdown("""
<style>
    /* Main background – soft gradient */
    .stApp {
        background: linear-gradient(135deg, #e6f0f5 0%, #d4e2ed 100%);
    }
    /* Title bar */
    .hero {
        background: linear-gradient(90deg, #0b3b4f 0%, #1c6e8f 100%);
        padding: 1.5rem;
        border-radius: 20px;
        margin-bottom: 2rem;
        text-align: center;
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    }
    .hero h1, .hero p {
        color: white;
        margin: 0;
    }
    .hero h1 { font-size: 2rem; }
    /* KPI cards */
    .kpi {
        background: white;
        border-radius: 16px;
        padding: 1rem;
        text-align: center;
        box-shadow: 0 2px 6px rgba(0,0,0,0.05);
        transition: 0.2s;
        border: 1px solid #e2e8f0;
    }
    .kpi:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
    .kpi-number { font-size: 2rem; font-weight: 700; color: #0b3b4f; }
    .kpi-label { font-size: 0.8rem; font-weight: 600; color: #4f7a9e; text-transform: uppercase; }
    /* Insight cards */
    .insight {
        background: white;
        border-radius: 16px;
        padding: 1.2rem;
        margin: 1rem 0;
        border-left: 5px solid #1c6e8f;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        color: #1e2a3a;
    }
    .insight b { color: #0b3b4f; }
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0.5rem;
        background: white;
        padding: 0.5rem;
        border-radius: 40px;
        margin-bottom: 1rem;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 30px;
        padding: 0.5rem 1.5rem;
        font-weight: 500;
        background: #eef2f7;
        color: #0b3b4f;
    }
    .stTabs [aria-selected="true"] {
        background: #1c6e8f;
        color: white;
    }
    hr { margin: 1rem 0; border-color: #cbd5e1; }
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------
# DATA LOADING (cached)
# ------------------------------------------------------------
@st.cache_data
def load_and_clean(filepath):
    df = pd.read_excel(filepath)
    df.columns = df.columns.str.strip()
    
    required = ['CLAIM ID', 'MEMBER NUMBER', 'PATIENT NAME', 'SERVICE TYPE',
                'BENEFIT DESC', 'MAIN HOSPITAL', 'AMOUNT', 'ARRIVAL DATE', 'TRANSACTION DATE']
    missing = [c for c in required if c not in df.columns]
    if missing:
        st.error(f"Missing columns: {missing}")
        st.stop()
    
    df['ARRIVAL DATE'] = pd.to_datetime(df['ARRIVAL DATE'], errors='coerce')
    df['TRANSACTION DATE'] = pd.to_datetime(df['TRANSACTION DATE'], errors='coerce')
    df['AMOUNT'] = pd.to_numeric(df['AMOUNT'], errors='coerce')
    df = df.dropna(subset=['AMOUNT', 'ARRIVAL DATE', 'MEMBER NUMBER', 'BENEFIT DESC', 'MAIN HOSPITAL'])
    
    # Unique visit key
    df['VISIT_KEY'] = (df['MEMBER NUMBER'].astype(str) + '_' +
                       df['ARRIVAL DATE'].dt.strftime('%Y-%m-%d') + '_' +
                       df['SERVICE TYPE'].astype(str))
    return df

DATA_PATH = "data/visits for an-april-2026.xlsx"
try:
    df = load_and_clean(DATA_PATH)
    st.sidebar.success(f"✅ Loaded {df.shape[0]:,} rows")
except Exception as e:
    st.error(f"Could not load data: {e}\nCheck path: {DATA_PATH}")
    st.stop()

# ------------------------------------------------------------
# SIDEBAR FILTERS (interactive)
# ------------------------------------------------------------
st.sidebar.title("🔍 Filter dashboard")
date_min = df['TRANSACTION DATE'].min().date()
date_max = df['TRANSACTION DATE'].max().date()
date_range = st.sidebar.date_input("Date range", [date_min, date_max], min_value=date_min, max_value=date_max)
if len(date_range) == 2:
    start, end = date_range
    df = df[(df['TRANSACTION DATE'].dt.date >= start) & (df['TRANSACTION DATE'].dt.date <= end)]

services = df['SERVICE TYPE'].unique().tolist()
sel_services = st.sidebar.multiselect("Service type", services, default=services)
if sel_services:
    df = df[df['SERVICE TYPE'].isin(sel_services)]

hospitals = df['MAIN HOSPITAL'].unique().tolist()
sel_hospitals = st.sidebar.multiselect("Hospital (optional)", hospitals, default=[])
if sel_hospitals:
    df = df[df['MAIN HOSPITAL'].isin(sel_hospitals)]

# ------------------------------------------------------------
# KPIs (top of dashboard)
# ------------------------------------------------------------
total_claims = df['CLAIM ID'].nunique()
total_visits = df['VISIT_KEY'].nunique()
total_amount = df['AMOUNT'].sum()
avg_visit_cost = total_amount / total_visits if total_visits else 0

col1, col2, col3, col4 = st.columns(4)
col1.markdown(f'<div class="kpi"><div class="kpi-number">{total_claims:,}</div><div class="kpi-label">Total claims</div></div>', unsafe_allow_html=True)
col2.markdown(f'<div class="kpi"><div class="kpi-number">{total_visits:,}</div><div class="kpi-label">Unique visits</div></div>', unsafe_allow_html=True)
col3.markdown(f'<div class="kpi"><div class="kpi-number">Ksh {total_amount/1e6:.1f}M</div><div class="kpi-label">Total cost</div></div>', unsafe_allow_html=True)
col4.markdown(f'<div class="kpi"><div class="kpi-number">Ksh {avg_visit_cost:,.0f}</div><div class="kpi-label">Avg cost / visit</div></div>', unsafe_allow_html=True)

st.markdown("---")

# ------------------------------------------------------------
# HERO TITLE
# ------------------------------------------------------------
st.markdown("""
<div class="hero">
    <h1>🏥 Healthcare Intelligence Dashboard</h1>
    <p>Actionable insights from claims data</p>
</div>
""", unsafe_allow_html=True)

# ------------------------------------------------------------
# TABS
# ------------------------------------------------------------
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📋 General view", "🔎 Deep insights", "✨ Attractive visuals", "🏥 Hospital deep dive", "📎 Data & export"
])

# ==================== TAB 1: GENERAL VIEW ====================
with tab1:
    st.subheader("What stands out immediately")
    
    # Two columns: service pie + monthly line
    left, right = st.columns(2)
    with left:
        service_totals = df.groupby('SERVICE TYPE')['AMOUNT'].sum().reset_index()
        fig_pie = px.pie(service_totals, names='SERVICE TYPE', values='AMOUNT', hole=0.4,
                         title="Cost share by service type", color_discrete_sequence=['#1c6e8f', '#4aa3c2'],
                         template='plotly_white')
        st.plotly_chart(fig_pie, use_container_width=True)
    with right:
        monthly = df.groupby(df['TRANSACTION DATE'].dt.to_period('M'))['AMOUNT'].sum().reset_index()
        monthly['Month'] = monthly['TRANSACTION DATE'].dt.strftime('%b')
        fig_line = px.line(monthly, x='Month', y='AMOUNT', markers=True,
                           title="Monthly cost trend", labels={'AMOUNT': 'Cost (Ksh)'},
                           color_discrete_sequence=['#1c6e8f'], template='plotly_white')
        st.plotly_chart(fig_line, use_container_width=True)
    
    # Top hospitals bar chart
    st.subheader("Top 10 hospitals by total cost")
    top_hosp = df.groupby('MAIN HOSPITAL')['AMOUNT'].sum().reset_index().nlargest(10, 'AMOUNT')
    fig_bar = px.bar(top_hosp, x='AMOUNT', y='MAIN HOSPITAL', orientation='h',
                     text=top_hosp['AMOUNT'].apply(lambda x: f'Ksh {x/1e6:.1f}M'),
                     color='AMOUNT', color_continuous_scale='Blues', template='plotly_white')
    fig_bar.update_traces(textposition='outside')
    fig_bar.update_layout(height=450, margin=dict(l=200))
    st.plotly_chart(fig_bar, use_container_width=True)
    
    # Insight summary
    st.markdown("""
    <div class="insight">
        <b>💡 Obvious insights</b><br>
        • Inpatient (IP) drives most of the cost.<br>
        • Cost is concentrated in a few hospitals – focus negotiations there.<br>
        • Monthly peaks may indicate seasonal utilisation or billing cycles.
    </div>
    """, unsafe_allow_html=True)

# ==================== TAB 2: DEEP INSIGHTS ====================
with tab2:
    st.subheader("Actionable intelligence for management")
    
    # Pareto (80/20)
    benefit_totals = df.groupby('BENEFIT DESC')['AMOUNT'].sum().sort_values(ascending=False)
    cumsum = benefit_totals.cumsum() / benefit_totals.sum() * 100
    n_80 = (cumsum <= 80).sum()
    st.metric("Pareto (80/20)", f"{n_80} benefits account for 80% of total cost")
    st.write("**Top benefits by cost:**")
    st.dataframe(benefit_totals.reset_index().head(10).style.format({'AMOUNT': 'Ksh {:,.0f}'}), 
                 use_container_width=True, hide_index=True)
    
    # Cost concentration (top 10% claims)
    top10pct_amount = df.nlargest(int(len(df)*0.1), 'AMOUNT')['AMOUNT'].sum()
    concentration = top10pct_amount / total_amount * 100
    st.metric("Risk concentration", f"Top 10% of claims represent {concentration:.1f}% of total cost")
    
    # Most expensive benefits (cost per visit)
    benefit_cost_per_visit = df.groupby('BENEFIT DESC').agg(
        Visits=('VISIT_KEY', 'nunique'),
        Total=('AMOUNT', 'sum')
    ).reset_index()
    benefit_cost_per_visit['Cost/visit'] = benefit_cost_per_visit['Total'] / benefit_cost_per_visit['Visits']
    expensive = benefit_cost_per_visit.nlargest(10, 'Cost/visit')
    st.subheader("💰 Most expensive benefits (average cost per visit)")
    st.dataframe(expensive[['BENEFIT DESC', 'Cost/visit', 'Visits']].style.format({'Cost/visit': 'Ksh {:,.0f}'}),
                 use_container_width=True, hide_index=True)
    
    # Patient switching (first vs last hospital)
    def first_hosp(g): return g.loc[g['ARRIVAL DATE'].idxmin(), 'MAIN HOSPITAL']
    def last_hosp(g): return g.loc[g['ARRIVAL DATE'].idxmax(), 'MAIN HOSPITAL']
    first = df.groupby('MEMBER NUMBER').apply(first_hosp).reset_index(name='FIRST')
    last = df.groupby('MEMBER NUMBER').apply(last_hosp).reset_index(name='LAST')
    merged = first.merge(last, on='MEMBER NUMBER')
    switched = merged[merged['FIRST'] != merged['LAST']]
    st.metric("Patient churn", f"{len(switched):,} patients switched hospitals ({len(switched)/len(merged)*100:.1f}%)")
    
    # Hospitals losing most patients
    loss = switched.groupby('FIRST').size().reset_index(name='Lost').nlargest(10, 'Lost')
    fig_loss = px.bar(loss, x='Lost', y='FIRST', orientation='h',
                      title="Hospitals losing most patients", color='Lost', color_continuous_scale='Reds',
                      template='plotly_white')
    fig_loss.update_layout(height=400, margin=dict(l=150))
    st.plotly_chart(fig_loss, use_container_width=True)
    
    # Outlier claims
    threshold = df['AMOUNT'].quantile(0.99)
    outliers = df[df['AMOUNT'] >= threshold]
    st.subheader("⚠️ High‑risk claims (top 1% by amount)")
    st.metric("Outlier threshold", f"Ksh {threshold:,.0f}")
    if not outliers.empty:
        st.dataframe(outliers[['CLAIM ID', 'MAIN HOSPITAL', 'BENEFIT DESC', 'AMOUNT']].head(15),
                     use_container_width=True, column_config={'AMOUNT': st.column_config.NumberColumn(format="Ksh %.0f")})
    
    st.markdown("""
    <div class="insight">
        <b>📌 Management actions</b><br>
        • Negotiate pricing for the top 5 benefits and hospitals.<br>
        • Audit outlier claims monthly – they carry disproportionate risk.<br>
        • Investigate hospitals with high patient churn (service quality, billing issues).<br>
        • High cost per visit for certain benefits may indicate overcharging.
    </div>
    """, unsafe_allow_html=True)

# ==================== TAB 3: ATTRACTIVE VISUALS ====================
with tab3:
    st.subheader("Data storytelling – engaging and insightful")
    
    # Sunburst
    sun_data = df.groupby(['SERVICE TYPE', 'BENEFIT DESC'])['AMOUNT'].sum().reset_index()
    fig_sun = px.sunburst(sun_data, path=['SERVICE TYPE', 'BENEFIT DESC'], values='AMOUNT',
                          color='AMOUNT', color_continuous_scale='Blues',
                          title="Cost hierarchy: Service type → Benefit", template='plotly_white')
    st.plotly_chart(fig_sun, use_container_width=True)
    
    # Treemap over months
    monthly_benefit = df.groupby([df['TRANSACTION DATE'].dt.to_period('M'), 'BENEFIT DESC'])['AMOUNT'].sum().reset_index()
    monthly_benefit['Month'] = monthly_benefit['TRANSACTION DATE'].dt.strftime('%b')
    top_benefits = monthly_benefit.groupby('BENEFIT DESC')['AMOUNT'].sum().nlargest(8).index.tolist()
    monthly_top = monthly_benefit[monthly_benefit['BENEFIT DESC'].isin(top_benefits)]
    fig_tree = px.treemap(monthly_top, path=['Month', 'BENEFIT DESC'], values='AMOUNT',
                          color='AMOUNT', color_continuous_scale='Viridis',
                          title="Monthly cost evolution (top 8 benefits)", template='plotly_white')
    st.plotly_chart(fig_tree, use_container_width=True)
    
    # Radar for top 5 hospitals
    top5_hosp = df.groupby('MAIN HOSPITAL')['AMOUNT'].sum().nlargest(5).index.tolist()
    radar_df = df[df['MAIN HOSPITAL'].isin(top5_hosp)].groupby('MAIN HOSPITAL').agg(
        Cost_per_visit=('AMOUNT', 'mean'),
        Avg_claim=('AMOUNT', 'mean'),
        Visit_count=('VISIT_KEY', 'nunique')
    ).reset_index()
    # Normalise
    for col in ['Cost_per_visit', 'Avg_claim', 'Visit_count']:
        radar_df[col] = (radar_df[col] - radar_df[col].min()) / (radar_df[col].max() - radar_df[col].min()) * 100
    fig_radar = px.line_polar(radar_df, r='Cost_per_visit', theta='MAIN HOSPITAL', line_close=True,
                              title="Comparative performance (normalised)", template='plotly_white')
    st.plotly_chart(fig_radar, use_container_width=True)
    
    # Heatmap: day of week vs hour
    df['Day'] = df['ARRIVAL DATE'].dt.day_name()
    df['Hour'] = df['ARRIVAL DATE'].dt.hour
    heat_data = df.groupby(['Day', 'Hour']).size().reset_index(name='Count')
    pivot = heat_data.pivot(index='Day', columns='Hour', values='Count').fillna(0)
    days_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    pivot = pivot.reindex(days_order)
    fig_heat = px.imshow(pivot, labels=dict(x="Hour of day", y="Day of week", color="Visits"),
                         color_continuous_scale='Blues', aspect='auto',
                         title="Patient arrival patterns", template='plotly_white')
    st.plotly_chart(fig_heat, use_container_width=True)

# ==================== TAB 4: HOSPITAL DEEP DIVE ====================
with tab4:
    st.subheader("Compare hospitals side by side")
    hosp_list = df['MAIN HOSPITAL'].unique().tolist()
    selected = st.multiselect("Select hospitals to compare", hosp_list, default=hosp_list[:2] if len(hosp_list)>=2 else hosp_list[:1])
    if selected:
        compare_df = df[df['MAIN HOSPITAL'].isin(selected)]
        
        # Monthly trend comparison
        monthly_comp = compare_df.groupby([compare_df['TRANSACTION DATE'].dt.to_period('M'), 'MAIN HOSPITAL'])['AMOUNT'].sum().reset_index()
        monthly_comp['Month'] = monthly_comp['TRANSACTION DATE'].dt.strftime('%b')
        fig_comp = px.line(monthly_comp, x='Month', y='AMOUNT', color='MAIN HOSPITAL', markers=True,
                           title="Monthly cost comparison", template='plotly_white')
        st.plotly_chart(fig_comp, use_container_width=True)
        
        # Benefit breakdown
        benefit_comp = compare_df.groupby(['MAIN HOSPITAL', 'BENEFIT DESC'])['AMOUNT'].sum().reset_index()
        top_benefits_comp = benefit_comp.groupby('BENEFIT DESC')['AMOUNT'].sum().nlargest(10).index.tolist()
        benefit_comp_top = benefit_comp[benefit_comp['BENEFIT DESC'].isin(top_benefits_comp)]
        fig_bar_comp = px.bar(benefit_comp_top, x='BENEFIT DESC', y='AMOUNT', color='MAIN HOSPITAL',
                              barmode='group', title="Benefit cost comparison", template='plotly_white')
        st.plotly_chart(fig_bar_comp, use_container_width=True)
        
        # Summary metrics table
        summary = compare_df.groupby('MAIN HOSPITAL').agg(
            Total_cost=('AMOUNT', 'sum'),
            Unique_visits=('VISIT_KEY', 'nunique'),
            Unique_patients=('MEMBER NUMBER', 'nunique')
        ).reset_index()
        summary['Avg_cost_per_visit'] = summary['Total_cost'] / summary['Unique_visits']
        st.dataframe(summary.style.format({
            'Total_cost': 'Ksh {:,.0f}',
            'Avg_cost_per_visit': 'Ksh {:,.0f}'
        }), use_container_width=True, hide_index=True)
    else:
        st.info("Please select at least one hospital from the dropdown.")

# ==================== TAB 5: DATA EXPORT ====================
with tab5:
    st.subheader("Raw data preview (first 100 rows)")
    st.dataframe(df.head(100), use_container_width=True)
    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button("📥 Download filtered data (CSV)", data=csv, file_name="healthcare_data.csv", mime="text/csv")
    st.caption(f"Currently showing {len(df):,} rows after filters.")

# ------------------------------------------------------------
# FOOTER
# ------------------------------------------------------------
st.markdown("---")
st.caption("Healthcare Intelligence Dashboard | Built with Streamlit & Plotly | Designed for decision makers")