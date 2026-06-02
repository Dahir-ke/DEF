import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import warnings
import os
from pathlib import Path

warnings.filterwarnings('ignore')

# ============================================
# PAGE CONFIG
# ============================================
st.set_page_config(page_title="Healthcare Claims Analytics", page_icon="🏥", layout="wide")

# ============================================
# SESSION STATE FOR AUTHENTICATION
# ============================================
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

# ============================================
# LOGIN PAGE
# ============================================
def show_login():
    st.markdown("""
        <style>
        .login-container {
            max-width: 400px;
            margin: 10rem auto;
            padding: 2rem;
            background: white;
            border-radius: 16px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.1);
            text-align: center;
        }
        .login-container h1 {
            color: #1a4a6e;
            margin-bottom: 0.5rem;
        }
        .login-container p {
            color: #5a6e7c;
            margin-bottom: 2rem;
        }
        </style>
    """, unsafe_allow_html=True)
    
    with st.container():
        st.markdown('<div class="login-container">', unsafe_allow_html=True)
        st.markdown("<h1>DEFMIS</h1>", unsafe_allow_html=True)
        st.markdown("<p>Healthcare Claims Analytics</p>", unsafe_allow_html=True)
        
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Login", use_container_width=True)
            
            if submitted:
                if username == "DEFMIS" and password == "2026":
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("Invalid credentials. Please try again.")
        st.markdown('</div>', unsafe_allow_html=True)

# ============================================
# ROBUST DATA LOADING (FIXED FOR 'OTHER NUMBER' ERROR)
# ============================================
@st.cache_data
def load_data(filepath):
    """Load Excel safely by reading all columns as strings, then convert needed columns."""
    parquet_path = Path(filepath).with_suffix('.parquet')
    
    # If Parquet cache exists and is newer than Excel, use it
    if parquet_path.exists() and os.path.getmtime(parquet_path) > os.path.getmtime(filepath):
        df = pd.read_parquet(parquet_path)
    else:
        # Read everything as string to avoid conversion errors (e.g., 'OTHER NUMBER' column)
        df = pd.read_excel(filepath, dtype=str)
        df.columns = df.columns.str.strip()
        
        required = ['CLAIM ID', 'MEMBER NUMBER', 'PATIENT NAME', 'SERVICE TYPE',
                    'BENEFIT DESC', 'MAIN HOSPITAL', 'AMOUNT', 'ARRIVAL DATE', 
                    'TRANSACTION DATE', 'DOB']
        for col in required:
            if col not in df.columns:
                st.error(f"Missing column: {col}")
                st.stop()
        
        # Convert dates - handle errors gracefully
        for col in ['ARRIVAL DATE', 'TRANSACTION DATE', 'DOB']:
            df[col] = pd.to_datetime(df[col], errors='coerce')
        
        # Convert AMOUNT to numeric
        df['AMOUNT'] = pd.to_numeric(df['AMOUNT'], errors='coerce')
        
        # Drop rows missing critical data
        df = df.dropna(subset=['AMOUNT', 'ARRIVAL DATE', 'MEMBER NUMBER'])
        
        # Create visit key
        df['VISIT_KEY'] = (df['MEMBER NUMBER'].astype(str) + '_' +
                           df['ARRIVAL DATE'].dt.strftime('%Y-%m-%d') + '_' +
                           df['SERVICE TYPE'].astype(str))
        
        # Age at visit
        df['AGE_AT_VISIT'] = (df['ARRIVAL DATE'] - df['DOB']).dt.days // 365
        df['AGE_AT_VISIT'] = df['AGE_AT_VISIT'].clip(0, 120)
        
        # Downcast numeric columns to save memory
        for col in ['AMOUNT', 'AGE_AT_VISIT']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], downcast='float')
        
        # Save as compressed Parquet for next run
        df.to_parquet(parquet_path, compression='snappy')
    
    return df

def dashboard():
    DATA_PATH = "data\visit_for_jan_to_end_of_May.csv"
    
    with st.spinner("Loading and optimizing data... first load may take a few seconds."):
        try:
            df = load_data(DATA_PATH)
            st.sidebar.success(f"✅ Loaded {df.shape[0]:,} rows")
        except Exception as e:
            st.error(f"Failed to load data: {e}")
            st.stop()
    
    # Custom CSS (same as before)
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
        .block-container { padding-top: 1rem; }
    </style>
    """, unsafe_allow_html=True)
    
    # ============================================
    # SIDEBAR FILTERS (unchanged)
    # ============================================
    st.sidebar.title("🎛️ Dashboard Filters")
    
    min_date = df['TRANSACTION DATE'].min().date()
    max_date = df['TRANSACTION DATE'].max().date()
    date_range = st.sidebar.date_input("Transaction Date Range", [min_date, max_date],
                                        min_value=min_date, max_value=max_date)
    
    all_services = df['SERVICE TYPE'].dropna().unique().tolist()
    selected_services = st.sidebar.multiselect("Service Type", all_services, default=all_services)
    
    all_main_hospitals = sorted(df['MAIN HOSPITAL'].dropna().unique().tolist())
    selected_main_hospitals = st.sidebar.multiselect(
        "Main Hospital (Group)",
        options=all_main_hospitals,
        default=[],
        help="Select one or more main hospitals. Branches will be filtered accordingly."
    )
    
    if 'PROVIDER NAME' not in df.columns:
        st.sidebar.warning("⚠️ Column 'PROVIDER NAME' not found. Branch filtering disabled.")
        selected_providers = []
        provider_options = []
    else:
        if selected_main_hospitals:
            provider_mask = df['MAIN HOSPITAL'].isin(selected_main_hospitals)
            branch_df = df.loc[provider_mask, ['MAIN HOSPITAL', 'PROVIDER NAME']].drop_duplicates()
            branch_counts = branch_df.groupby('MAIN HOSPITAL')['PROVIDER NAME'].nunique()
            if len(selected_main_hospitals) == 1:
                hospital = selected_main_hospitals[0]
                count = branch_counts.get(hospital, 0)
                st.sidebar.info(f"🏥 **{hospital}** has **{count}** branch(es).")
                branches = branch_df[branch_df['MAIN HOSPITAL'] == hospital]['PROVIDER NAME'].tolist()
                if branches:
                    with st.sidebar.expander("📋 See branches"):
                        for b in branches:
                            st.write(f"- {b}")
            else:
                total_branches = branch_df['PROVIDER NAME'].nunique()
                st.sidebar.info(f"📊 Across the selected {len(selected_main_hospitals)} hospitals, there are **{total_branches}** unique branches.")
                with st.sidebar.expander("🏥 Branch count per hospital"):
                    for hosp, cnt in branch_counts.items():
                        st.write(f"- **{hosp}**: {cnt} branch(es)")
        else:
            st.sidebar.info("💡 Select a main hospital to see branch information.")
        
        if selected_main_hospitals:
            provider_options = sorted(df.loc[provider_mask, 'PROVIDER NAME'].dropna().unique().tolist())
        else:
            provider_options = sorted(df['PROVIDER NAME'].dropna().unique().tolist())
        
        selected_providers = st.sidebar.multiselect(
            "Provider Name (Branch)",
            options=provider_options,
            default=[],
            help="Select specific branches. If none selected, all branches under the chosen main hospitals are included."
        )
    
    # ============================================
    # APPLY FILTERS (unchanged)
    # ============================================
    df_filtered = df.copy()
    if len(date_range) == 2:
        start, end = date_range
        df_filtered = df_filtered[(df_filtered['TRANSACTION DATE'].dt.date >= start) &
                                  (df_filtered['TRANSACTION DATE'].dt.date <= end)]
    if selected_services:
        df_filtered = df_filtered[df_filtered['SERVICE TYPE'].isin(selected_services)]
    if selected_main_hospitals:
        df_filtered = df_filtered[df_filtered['MAIN HOSPITAL'].isin(selected_main_hospitals)]
    if 'PROVIDER NAME' in df.columns and selected_providers:
        df_filtered = df_filtered[df_filtered['PROVIDER NAME'].isin(selected_providers)]
    
    if df_filtered.empty:
        st.sidebar.warning("No data matches filters. Showing all data.")
        df_filtered = df.copy()
    
    # KPIs (unchanged)
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
    # TABS (all unchanged - exactly as in original)
    # ============================================
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "📊 Service & Benefit", "🏥 Provider Scorecard", "📈 Monthly Trends",
        "⚠️ Outlier Detection", "🔍 Member Lookup", "🔄 Retention & Export",
        "🔄 OP‑IP Transitions"
    ])
    
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
    
    with tab2:
        st.subheader("🏥 Provider Efficiency Scorecard")
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
        provider['RETENTION_RATE'] = provider['RETENTION_RATE'].fillna(100).round(1)
        
        top_providers = provider.sort_values('TOTAL_COST', ascending=False).head(15).copy()
        display_provider = top_providers.copy()
        display_provider['TOTAL_COST'] = display_provider['TOTAL_COST'].apply(lambda x: f"Ksh {x:,.2f}")
        display_provider['COST_PER_VISIT'] = display_provider['COST_PER_VISIT'].apply(lambda x: f"Ksh {x:,.2f}")
        display_provider['COST_PER_PATIENT'] = display_provider['COST_PER_PATIENT'].apply(lambda x: f"Ksh {x:,.2f}")
        display_provider['RETENTION_RATE'] = display_provider['RETENTION_RATE'].apply(lambda x: f"{x:.1f}%")
        display_provider = display_provider.rename(columns={
            'MAIN HOSPITAL': 'MAIN HOSPITAL',
            'TOTAL_COST': 'TOTAL COST',
            'UNIQUE_VISITS': 'UNIQUE VISITS',
            'COST_PER_VISIT': 'COST PER VISIT',
            'COST_PER_PATIENT': 'COST PER PATIENT',
            'RETENTION_RATE': 'RETENTION RATE'
        })
        st.dataframe(display_provider, use_container_width=True, hide_index=True, height=600)
        
        c1, c2, c3 = st.columns(3)
        with c1: st.metric("Total Providers", f"{provider['MAIN HOSPITAL'].nunique():,}")
        with c2: st.metric("Average Cost per Visit", f"Ksh {provider['COST_PER_VISIT'].mean():,.2f}")
        with c3: st.metric("Average Retention Rate", f"{provider['RETENTION_RATE'].mean():.1f}%")
        st.markdown("<br>", unsafe_allow_html=True)
        
        fig_eff = px.scatter(provider, x='COST_PER_VISIT', y='RETENTION_RATE', size='TOTAL_COST', color='TOTAL_COST',
                             hover_name='MAIN HOSPITAL', color_continuous_scale='Viridis',
                             labels={'COST_PER_VISIT': 'Cost per Visit (Ksh)', 'RETENTION_RATE': 'Retention Rate (%)'},
                             title='Provider Cost Efficiency vs Retention')
        fig_eff.update_layout(height=550, title_x=0.5, paper_bgcolor='white', plot_bgcolor='white')
        fig_eff.update_traces(marker=dict(line=dict(width=1, color='white')))
        st.plotly_chart(fig_eff, use_container_width=True)
    
    with tab3:
        st.subheader("Monthly Performance with MoM Changes")
        monthly = df_filtered.groupby(df_filtered['TRANSACTION DATE'].dt.to_period('M')).agg(
            AMOUNT=('AMOUNT', 'sum'), CLAIMS=('CLAIM ID', 'count'), VISITS=('VISIT_KEY', 'nunique')).reset_index()
        monthly['MONTH_NAME'] = monthly['TRANSACTION DATE'].dt.strftime('%b')
        monthly['AMOUNT_MOM'] = monthly['AMOUNT'].pct_change() * 100
        monthly['CLAIMS_MOM'] = monthly['CLAIMS'].pct_change() * 100
        monthly['VISITS_MOM'] = monthly['VISITS'].pct_change() * 100
        
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(go.Bar(x=monthly['MONTH_NAME'], y=monthly['AMOUNT'], name='Amount (Ksh)', marker_color='#2c7a7a'), secondary_y=False)
        fig.add_trace(go.Scatter(x=monthly['MONTH_NAME'], y=monthly['CLAIMS'], name='Claims', mode='lines+markers', line=dict(color='#f4a261', width=3)), secondary_y=True)
        fig.add_trace(go.Scatter(x=monthly['MONTH_NAME'], y=monthly['VISITS'], name='Unique Visits', mode='lines+markers', line=dict(color='#2a9d8f', dash='dot')), secondary_y=True)
        fig.update_layout(title='Monthly Trends', height=450, hovermode='x unified')
        fig.update_yaxes(title_text="Amount (Ksh)", secondary_y=False)
        fig.update_yaxes(title_text="Count", secondary_y=True)
        st.plotly_chart(fig, use_container_width=True)
        
        st.subheader("Month-over-Month Change (%)")
        mom_table = monthly[['MONTH_NAME', 'AMOUNT_MOM', 'CLAIMS_MOM', 'VISITS_MOM']].dropna()
        if not mom_table.empty:
            for col in ['AMOUNT_MOM', 'CLAIMS_MOM', 'VISITS_MOM']:
                mom_table[col] = pd.to_numeric(mom_table[col], errors='coerce')
            styled = mom_table.style.format({'AMOUNT_MOM': '{:.1f}%', 'CLAIMS_MOM': '{:.1f}%', 'VISITS_MOM': '{:.1f}%'})
            st.dataframe(styled, use_container_width=True)
        else:
            st.info("Not enough months to calculate MoM changes.")
    
    with tab4:
        st.subheader("Cost Outlier Detection (Top 1% Claims)")
        if len(df_filtered) > 0:
            threshold = df_filtered['AMOUNT'].quantile(0.99)
            outliers = df_filtered[df_filtered['AMOUNT'] >= threshold]
            st.metric("99th Percentile Threshold", f"Ksh {threshold:,.0f}")
            st.write(f"**{len(outliers)} claims** exceed this threshold (top 1%).")
            if not outliers.empty:
                st.dataframe(outliers[['CLAIM ID', 'MEMBER NUMBER', 'PATIENT NAME', 'MAIN HOSPITAL', 'AMOUNT', 'SERVICE TYPE']].head(50),
                             use_container_width=True, column_config={'AMOUNT': st.column_config.NumberColumn(format="Ksh %.0f")})
            sample = df_filtered.sample(min(5000, len(df_filtered)))
            fig_out = px.scatter(sample, x='TRANSACTION DATE', y='AMOUNT', color='SERVICE TYPE', title='Claim Amount Distribution (sampled)',
                                 labels={'AMOUNT': 'Claim Amount (Ksh)'})
            fig_out.add_hline(y=threshold, line_dash="dash", line_color="red", annotation_text=f"99th percentile: {threshold:,.0f}")
            st.plotly_chart(fig_out, use_container_width=True)
        else:
            st.info("No data for outlier analysis.")
    
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
                        st.dataframe(member_data[['ARRIVAL DATE', 'MAIN HOSPITAL', 'SERVICE TYPE', 'AMOUNT']],
                                     column_config={'AMOUNT': st.column_config.NumberColumn(format="Ksh %.0f")})
            else:
                st.warning("No matching member found.")
    
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
            fig_switch = px.bar(top_switch, x='Switched', y='FIRST', orientation='h', text='Switched', color='Retention %',
                                color_continuous_scale='Reds', title='Hospitals with Most Patients Ending at Different Hospital')
            fig_switch.update_traces(texttemplate='%{text}', textposition='outside')
            fig_switch.update_layout(height=450, margin=dict(l=150))
            st.plotly_chart(fig_switch, use_container_width=True)
        else:
            st.info("Not enough data for switching analysis.")
        
        st.subheader("Export Data")
        csv = df_filtered.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download Filtered Data as CSV", data=csv, file_name="filtered_claims.csv", mime="text/csv")
        st.caption(f"Filtered dataset: {len(df_filtered):,} rows | {df_filtered['MEMBER NUMBER'].nunique():,} unique members")
    
    with tab7:
        st.subheader("Same‑Day Outpatient → Inpatient Transitions")
        st.markdown("""
        This analysis identifies members who had **both an Outpatient (OP) and an Inpatient (IP) claim on the same day**.
        For each such event, we attribute it to the **hospital where the IP claim occurred**.
        **Note:** Hospital/branch filters from the sidebar are ignored here. Only the date range applies.
        """)
        df_transition = df.copy()
        if len(date_range) == 2:
            start, end = date_range
            df_transition = df_transition[(df_transition['TRANSACTION DATE'].dt.date >= start) &
                                        (df_transition['TRANSACTION DATE'].dt.date <= end)]
        same_day = df_transition.groupby(['MEMBER NUMBER', 'ARRIVAL DATE']).filter(lambda g: set(g['SERVICE TYPE']) == {'OP', 'IP'})
        if same_day.empty:
            st.info("No same-day OP-IP transitions found with the selected date range.")
        else:
            ip_events = same_day[same_day['SERVICE TYPE'] == 'IP'].drop_duplicates(subset=['MEMBER NUMBER', 'ARRIVAL DATE'])
            op_events = same_day[same_day['SERVICE TYPE'] == 'OP'].drop_duplicates(subset=['MEMBER NUMBER', 'ARRIVAL DATE'])
            transition_data = ip_events[['MEMBER NUMBER', 'ARRIVAL DATE', 'MAIN HOSPITAL', 'TRANSACTION DATE', 'AMOUNT']].copy()
            transition_data.rename(columns={'AMOUNT': 'IP_AMOUNT', 'TRANSACTION DATE': 'IP_TRANSACTION_TIME'}, inplace=True)
            op_info = op_events[['MEMBER NUMBER', 'ARRIVAL DATE', 'AMOUNT', 'TRANSACTION DATE']].copy()
            op_info.rename(columns={'AMOUNT': 'OP_AMOUNT', 'TRANSACTION DATE': 'OP_TRANSACTION_TIME'}, inplace=True)
            transition = transition_data.merge(op_info, on=['MEMBER NUMBER', 'ARRIVAL DATE'], how='left')
            transition['ORDER'] = transition.apply(lambda r: 'OP → IP' if pd.notnull(r['OP_TRANSACTION_TIME']) and pd.notnull(r['IP_TRANSACTION_TIME']) and r['OP_TRANSACTION_TIME'] < r['IP_TRANSACTION_TIME'] else ('IP → OP' if pd.notnull(r['OP_TRANSACTION_TIME']) and pd.notnull(r['IP_TRANSACTION_TIME']) and r['IP_TRANSACTION_TIME'] < r['OP_TRANSACTION_TIME'] else 'unknown'), axis=1)
            
            hospital_events = transition.groupby('MAIN HOSPITAL').size().reset_index(name='same_day_OP_IP_events')
            hospital_events = hospital_events.sort_values('same_day_OP_IP_events', ascending=False)
            top10_events = hospital_events.head(10)
            st.subheader("🏥 Top 10 Hospitals by Same‑Day OP‑IP Events")
            st.dataframe(top10_events, use_container_width=True, hide_index=True)
            fig_events = px.bar(top10_events, x='same_day_OP_IP_events', y='MAIN HOSPITAL', orientation='h', text='same_day_OP_IP_events', title='Number of Same‑Day OP‑IP Events per Hospital', color='same_day_OP_IP_events', color_continuous_scale='Blues')
            fig_events.update_traces(texttemplate='%{text}', textposition='outside')
            fig_events.update_layout(height=450, margin=dict(l=150))
            st.plotly_chart(fig_events, use_container_width=True)
            
            hospital_members = transition.groupby('MAIN HOSPITAL')['MEMBER NUMBER'].nunique().reset_index(name='unique_members')
            hospital_members = hospital_members.sort_values('unique_members', ascending=False)
            top10_members = hospital_members.head(10)
            st.subheader("👥 Top 10 Hospitals by Unique Members with Same‑Day OP‑IP")
            st.dataframe(top10_members, use_container_width=True, hide_index=True)
            fig_members = px.bar(top10_members, x='unique_members', y='MAIN HOSPITAL', orientation='h', text='unique_members', title='Unique Members per Hospital', color='unique_members', color_continuous_scale='Tealgrn')
            fig_members.update_traces(texttemplate='%{text}', textposition='outside')
            fig_members.update_layout(height=450, margin=dict(l=150))
            st.plotly_chart(fig_members, use_container_width=True)
            
            st.subheader("🔍 Member Details by Hospital")
            hospital_list = sorted(transition['MAIN HOSPITAL'].unique())
            if hospital_list:
                selected_hosp = st.selectbox("Select a hospital to see members who transitioned:", hospital_list)
                if selected_hosp:
                    hosp_members = transition[transition['MAIN HOSPITAL'] == selected_hosp].copy()
                    hosp_members = hosp_members.sort_values('ARRIVAL DATE', ascending=False)
                    member_names = df_transition[['MEMBER NUMBER', 'PATIENT NAME']].drop_duplicates()
                    hosp_members = hosp_members.merge(member_names, on='MEMBER NUMBER', how='left')
                    st.write(f"**{len(hosp_members)} transition events** at **{selected_hosp}**")
                    display_cols = ['ARRIVAL DATE', 'MEMBER NUMBER', 'PATIENT NAME', 'OP_AMOUNT', 'IP_AMOUNT', 'ORDER']
                    st.dataframe(hosp_members[display_cols], use_container_width=True,
                                 column_config={'ARRIVAL DATE': st.column_config.DateColumn("Date"),
                                                'OP_AMOUNT': st.column_config.NumberColumn("OP Amount (Ksh)", format="Ksh %.0f"),
                                                'IP_AMOUNT': st.column_config.NumberColumn("IP Amount (Ksh)", format="Ksh %.0f")},
                                 hide_index=True)
                    csv_hosp = hosp_members[display_cols].to_csv(index=False).encode('utf-8')
                    st.download_button(f"📥 Download {selected_hosp} transition data (CSV)", data=csv_hosp, file_name=f"{selected_hosp}_op_ip_transitions.csv", mime="text/csv")
            else:
                st.info("No hospitals with transition events.")
            
            st.subheader("📊 Quick Stats")
            col_a, col_b, col_c = st.columns(3)
            with col_a: st.metric("Total Transition Events", len(transition))
            with col_b: st.metric("Unique Members", transition['MEMBER NUMBER'].nunique())
            with col_c: st.metric("Unique Hospitals", transition['MAIN HOSPITAL'].nunique())
            with st.expander("📋 View all transition events (filtered data)"):
                member_names = df_transition[['MEMBER NUMBER', 'PATIENT NAME']].drop_duplicates()
                all_trans = transition.merge(member_names, on='MEMBER NUMBER', how='left')
                st.dataframe(all_trans[['ARRIVAL DATE', 'MEMBER NUMBER', 'PATIENT NAME', 'MAIN HOSPITAL', 'OP_AMOUNT', 'IP_AMOUNT', 'ORDER']],
                             use_container_width=True, hide_index=True)
    
    st.markdown("---")
    st.caption("Healthcare Claims Dashboard | Built with Streamlit & Plotly | Data period: Jan–Apr 2026")

# ============================================
# ROUTING
# ============================================
if st.session_state.authenticated:
    dashboard()
else:
    show_login()