import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ─────────────────────────────────────────────
# 1. Page setup
# ─────────────────────────────────────────────
st.set_page_config(page_title="Expat mortgage simulator", layout="wide")

st.title("Expat mortgage simulator")
st.caption(
    "Strategy: Use your expat salary to qualify for a larger loan → "
    "save a fixed lump sum during the expat phase → recast the mortgage → "
    "affordable payment on your post-expat salary."
)

# ─────────────────────────────────────────────
# 2. Sidebar inputs (Organized into Expanders)
# ─────────────────────────────────────────────
with st.sidebar:
    st.header("Parameters")
    
    with st.expander("🏠 Property & Capital", expanded=True):
        house_price = st.number_input(
            "House price (€)", value=400_000, step=10_000,
            help="Total purchase price of the property."
        )
        total_initial_savings = st.number_input(
            "Total initial capital (€)", value=200_000, step=10_000,
            help="All savings available before buying (invested + liquid)."
        )
        initial_downpayment = st.number_input(
            "Down payment (€)", value=80_000, step=10_000,
            help="Capital allocated to the purchase. Costs are deducted from this; remainder reduces the loan."
        )
        cash_buffer_input = st.number_input(
            "Emergency buffer (€)", value=10_000, step=1_000,
            help="Kept in cash at 0% return. Never invested or used for the lump sum."
        )
        purchasing_costs_pct = st.slider(
            "Purchasing costs (%)", 1.0, 8.0, 3.5, 0.1,
            help="Registration tax + notary fees as a % of the house price."
        )

    with st.expander("💳 Mortgage Details", expanded=True):
        annual_rate = st.slider(
            "Interest rate (%)", 1.0, 6.0, 3.0, 0.1,
            help="Annual fixed interest rate on the mortgage."
        )
        total_years = st.slider(
            "Duration (years)", 10, 30, 25,
            help="Total loan duration."
        )

    with st.expander("✈️ Expat Phase", expanded=True):
        expat_years = st.slider(
            "Years as expat", 1, 10, 2,
            help="How long you keep the expat salary after purchasing."
        )
        expat_monthly_savings = st.number_input(
            "Expat monthly savings (€)", value=4_000, step=500,
            help="Total amount you can save each month during the expat phase."
        )
        target_phase2_payment = st.number_input(
            "Target payment post-recast (€)", value=1_400, step=100,
            help="The maximum monthly payment you can afford on your post-expat salary."
        )

    with st.expander("🏡 Post-Expat Phase", expanded=False):
        future_salary_base = st.number_input(
            "Expected net salary (€/month)", value=3_200, step=100,
        )
        normal_monthly_savings_base = st.number_input(
            "Monthly investments (€)", value=500, step=100,
            help="Amount you'll invest each month after the expat phase."
        )

    with st.expander("📈 Market Assumptions", expanded=False):
        salary_growth_rate = st.slider("Salary growth (%/yr)", 0.0, 10.0, 4.0, 0.5) / 100
        inflation_rate = st.slider("Inflation (%/yr)", 0.0, 10.0, 2.0, 0.5) / 100
        investment_return_rate = st.slider("Market return (%/yr)", 0.0, 15.0, 7.0, 0.5) / 100
        house_appreciation_rate = st.slider("House appreciation (%/yr)", 0.0, 10.0, 3.0, 0.5) / 100

# ─────────────────────────────────────────────
# 3. Logic: Cached Simulation Function
# ─────────────────────────────────────────────
@st.cache_data
def run_simulation(
    house_price, total_initial_savings, initial_downpayment, cash_buffer_input, purchasing_costs_pct,
    annual_rate, total_years, expat_years, expat_monthly_savings, target_phase2_payment,
    future_salary_base, normal_monthly_savings_base, salary_growth_rate, inflation_rate,
    investment_return_rate, house_appreciation_rate
):
    # Derived constants
    purchasing_costs    = house_price * (purchasing_costs_pct / 100)
    actual_downpayment  = initial_downpayment - purchasing_costs
    principal           = house_price - actual_downpayment

    starting_leftover   = total_initial_savings - initial_downpayment
    actual_cash_buffer  = min(max(0, starting_leftover), cash_buffer_input)
    starting_portfolio  = max(0, starting_leftover - actual_cash_buffer)

    monthly_rate            = (annual_rate / 100) / 12
    total_months            = total_years * 12
    expat_months            = expat_years * 12
    remaining_months        = total_months - expat_months
    monthly_inv_rate        = (1 + investment_return_rate) ** (1 / 12) - 1
    monthly_appr_rate       = (1 + house_appreciation_rate) ** (1 / 12) - 1
    real_savings_growth     = salary_growth_rate - inflation_rate

    # Phase 1 payment
    m_initial = (
        principal * (monthly_rate * (1 + monthly_rate) ** total_months)
        / ((1 + monthly_rate) ** total_months - 1)
    )

    # Pre-simulation: Calculate lump sum
    _bal = principal
    for _ in range(expat_months):
        _interest = _bal * monthly_rate
        _bal -= (m_initial - _interest)
    balance_at_recast = _bal

    target_balance_for_recast = (
        target_phase2_payment
        * ((1 + monthly_rate) ** remaining_months - 1)
        / (monthly_rate * (1 + monthly_rate) ** remaining_months)
    ) if remaining_months > 0 else 0

    required_net_drop = max(0, balance_at_recast - target_balance_for_recast)
    required_gross_lump_sum = required_net_drop / (1 - 3 * monthly_rate) if required_net_drop > 0 else 0
    penalty                 = required_gross_lump_sum * monthly_rate * 3
    net_lump_sum            = required_gross_lump_sum - penalty

    monthly_recast_contribution  = required_gross_lump_sum / expat_months if expat_months > 0 else 0
    monthly_invest_contribution   = max(0, expat_monthly_savings - monthly_recast_contribution)
    monthly_shortfall             = max(0, monthly_recast_contribution - expat_monthly_savings)

    # Full simulation
    schedule = []
    balance           = principal
    portfolio_value   = starting_portfolio
    recast_fund       = 0.0
    house_value       = house_price
    alt_portfolio     = starting_portfolio

    for month in range(1, expat_months + 1):
        interest       = balance * monthly_rate
        balance       -= (m_initial - interest)
        recast_fund   += monthly_recast_contribution
        portfolio_value = portfolio_value * (1 + monthly_inv_rate) + monthly_invest_contribution
        alt_portfolio   = alt_portfolio   * (1 + monthly_inv_rate) + expat_monthly_savings
        house_value    *= (1 + monthly_appr_rate)
        yr = (month - 1) // 12
        salary_now = future_salary_base * ((1 + salary_growth_rate) ** yr)

        schedule.append({
            "Month": month, "Payment": m_initial, "Balance": balance,
            "Investment portfolio": portfolio_value, "Recast fund": recast_fund,
            "Cash buffer": actual_cash_buffer, "House value": house_value,
            "Target salary": salary_now, "Alt_payment": m_initial, "Alt_balance": balance, "Alt_portfolio": alt_portfolio,
        })

    balance -= net_lump_sum
    alt_balance = balance_at_recast

    m_new = (
        balance * (monthly_rate * (1 + monthly_rate) ** remaining_months)
        / ((1 + monthly_rate) ** remaining_months - 1)
    ) if remaining_months > 0 else 0

    for month in range(expat_months + 1, total_months + 1):
        interest  = balance * monthly_rate
        balance  -= (m_new - interest)
        yr = (month - 1) // 12
        salary_now = future_salary_base * ((1 + salary_growth_rate) ** yr)
        monthly_savings_now = normal_monthly_savings_base * ((1 + real_savings_growth) ** (yr - expat_years))

        portfolio_value = portfolio_value * (1 + monthly_inv_rate) + monthly_savings_now
        house_value    *= (1 + monthly_appr_rate)

        alt_interest = alt_balance * monthly_rate
        alt_balance -= (m_initial - alt_interest)
        alt_savings  = max(0, monthly_savings_now - (m_initial - m_new))
        alt_portfolio = alt_portfolio * (1 + monthly_inv_rate) + alt_savings

        schedule.append({
            "Month": month, "Payment": m_new, "Balance": max(0, balance),
            "Investment portfolio": portfolio_value, "Recast fund": 0,
            "Cash buffer": actual_cash_buffer, "House value": house_value,
            "Target salary": salary_now, "Alt_payment": m_initial, "Alt_balance": max(0, alt_balance), "Alt_portfolio": alt_portfolio,
        })

    df = pd.DataFrame(schedule)
    df["Year"] = df["Month"] / 12
    df["Total liquid assets"]     = df["Investment portfolio"] + df["Cash buffer"]
    df["Total assets"]            = df["House value"] + df["Total liquid assets"] - df["Balance"]
    df["Alt_total liquid assets"] = df["Alt_portfolio"] + df["Cash buffer"]
    df["Alt_total assets"]        = df["House value"] + df["Alt_total liquid assets"] - df["Alt_balance"]

    results = {
        "df": df,
        "m_initial": m_initial,
        "m_new": m_new,
        "required_gross_lump_sum": required_gross_lump_sum,
        "penalty": penalty,
        "monthly_recast_contribution": monthly_recast_contribution,
        "monthly_invest_contribution": monthly_invest_contribution,
        "monthly_shortfall": monthly_shortfall,
        "principal": principal,
        "balance_at_recast": balance_at_recast,
        "target_balance_for_recast": target_balance_for_recast,
        "net_lump_sum": net_lump_sum,
        "purchasing_costs": purchasing_costs,
        "actual_downpayment": actual_downpayment,
        "actual_cash_buffer": actual_cash_buffer,
        "starting_portfolio": starting_portfolio,
        "expat_months": expat_months,
        "remaining_months": remaining_months,
        "real_savings_growth": real_savings_growth
    }
    return results

# ─────────────────────────────────────────────
# 4. Main execution
# ─────────────────────────────────────────────
if initial_downpayment > total_initial_savings:
    st.error("❌ Down payment exceeds total initial capital. Please adjust your inputs.")
    st.stop()

res = run_simulation(
    house_price, total_initial_savings, initial_downpayment, cash_buffer_input, purchasing_costs_pct,
    annual_rate, total_years, expat_years, expat_monthly_savings, target_phase2_payment,
    future_salary_base, normal_monthly_savings_base, salary_growth_rate, inflation_rate,
    investment_return_rate, house_appreciation_rate
)

df = res["df"]

# ─────────────────────────────────────────────
# 5. UI: Headline Metrics
# ─────────────────────────────────────────────
st.markdown("### The strategy at a glance")
c1, c2, c3 = st.columns(3)
c1.metric("① Phase 1 payment", f"€{res['m_initial']:,.0f} / mo")
c2.metric("② Lump sum to recast", f"€{res['required_gross_lump_sum']:,.0f}")
c3.metric("③ Phase 2 payment", f"€{res['m_new']:,.0f} / mo", delta=f"Target: €{target_phase2_payment:,.0f}", delta_color="off")

c4, c5, c6 = st.columns(3)
c4.metric("Monthly recast saving", f"€{res['monthly_recast_contribution']:,.0f} / mo")
c5.metric("Monthly invest saving", f"€{res['monthly_invest_contribution']:,.0f} / mo")

if res['monthly_shortfall'] > 0:
    c6.metric("⚠️ Monthly shortfall", f"€{res['monthly_shortfall']:,.0f} / mo", delta="Insufficient savings", delta_color="inverse")
else:
    c6.metric("✅ Plan is feasible", f"€{expat_monthly_savings - res['monthly_recast_contribution']:,.0f} surplus", delta_color="normal")

st.markdown("---")

# ─────────────────────────────────────────────
# 6. UI: Charts
# ─────────────────────────────────────────────
C_WHITE, C_GREEN, C_INDIGO, C_RED, C_PURPLE, C_AMBER, C_BG, C_GRID, C_GREY = \
    "#F3F4F6", "#10B981", "#6366F1", "#EF4444", "#8B5CF6", "#F59E0B", "#111827", "#374151", "#9CA3AF"

fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.08,
                    subplot_titles=("Monthly mortgage payment", "Net worth breakdown", "Recast vs. No recast"))

fig.add_trace(go.Scatter(x=df["Year"], y=df["Payment"], name="Recast payment", fill="tozeroy", line=dict(color=C_RED, width=2.5)), row=1, col=1)
fig.add_trace(go.Scatter(x=df["Year"], y=df["Alt_payment"], name="No-recast payment", line=dict(color=C_GREY, width=1.5, dash="dash")), row=1, col=1)
fig.add_trace(go.Scatter(x=df["Year"], y=df["Total assets"], name="Total net worth", fill="tozeroy", line=dict(color=C_WHITE, width=2.5)), row=2, col=1)
fig.add_trace(go.Scatter(x=df["Year"], y=df["House value"], name="House value", line=dict(color=C_GREEN, width=1.5, dash="dash")), row=2, col=1)
fig.add_trace(go.Scatter(x=df["Year"], y=df["Balance"], name="Debt", line=dict(color=C_RED, width=1.5)), row=2, col=1)
fig.add_trace(go.Scatter(x=df["Year"], y=df["Total assets"], name="Recast NW", line=dict(color=C_WHITE, width=2)), row=3, col=1)
fig.add_trace(go.Scatter(x=df["Year"], y=df["Alt_total assets"], name="No-recast NW", line=dict(color=C_PURPLE, width=2, dash="dash")), row=3, col=1)

fig.update_layout(template="plotly_dark", plot_bgcolor=C_BG, paper_bgcolor=C_BG, height=900, hovermode="x unified", legend=dict(orientation="h", y=1.05, x=0.5, xanchor="center"))
fig.update_yaxes(tickprefix="€", tickformat=",.0f", gridcolor=C_GRID)
st.plotly_chart(fig, use_container_width=True, theme=None)

# ─────────────────────────────────────────────
# 7. UI: Breakdown Tabs
# ─────────────────────────────────────────────
st.markdown("### Full financial breakdown")
t1, t2, t3 = st.tabs(["📊 Breakdown", "💰 Cash flow", "📥 Export"])

with t1:
    col_l, col_r = st.columns([1.5, 1])
    with col_l:
        st.markdown(f"#### 🏠 Purchase & Expat phase")
        st.write(f"Starting loan: **€{res['principal']:,.0f}**. Initial portfolio: **€{res['starting_portfolio']:,.0f}**.")
        st.write(f"Expat phase: Paying **€{res['m_initial']:,.0f}/mo** for {expat_years} years.")
        
        st.markdown(f"#### 🔄 Recast Event (End of Year {expat_years})")
        st.markdown(f"""
        | Item | Amount |
        | :--- | ---: |
        | Balance at recast | €{res['balance_at_recast']:,.0f} |
        | Lump sum (gross) | €{res['required_gross_lump_sum']:,.0f} |
        | Penalty (3mo int) | €{res['penalty']:,.0f} |
        | **New payment** | **€{res['m_new']:,.0f}/mo** |
        """)
    with col_r:
        st.markdown("#### Cost summary")
        total_p1 = res['m_initial'] * res['expat_months']
        total_p2 = res['m_new'] * res['remaining_months']
        total_paid = initial_downpayment + total_p1 + total_p2 + res['required_gross_lump_sum']
        st.info(f"Total out-of-pocket: **€{total_paid:,.0f}**")
        
        diff = df.iloc[-1]["Total assets"] - df.iloc[-1]["Alt_total assets"]
        if diff >= 0: st.success(f"Recast strategy ends **€{diff:,.0f} ahead**.")
        else: st.warning(f"No recast ends **€{abs(diff):,.0f} ahead**.")

with t2:
    labels = ["Down payment", "Lump sum", "Phase 1 payments", "Phase 2 payments"]
    values = [initial_downpayment, res['required_gross_lump_sum'], total_p1, total_p2]
    fig_pie = go.Figure(data=[go.Pie(labels=labels, values=values, hole=.5, marker_colors=[C_GREEN, C_AMBER, C_PURPLE, C_RED])])
    fig_pie.update_layout(template="plotly_dark", height=400, margin=dict(t=20, b=20))
    st.plotly_chart(fig_pie, use_container_width=True)

with t3:
    st.write("Download the full monthly simulation data for Excel or Sheets.")
    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button("Download CSV", data=csv, file_name="mortgage_simulation.csv", mime="text/csv")
