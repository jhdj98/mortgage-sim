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
# 2. Sidebar inputs
# ─────────────────────────────────────────────
with st.sidebar.expander("Property & capital", expanded=True):
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
        help="Capital allocated to the purchase. Purchasing costs are deducted from this first; the remainder reduces the starting loan."
    )
    cash_buffer_input = st.number_input(
        "Emergency cash buffer (€)", value=10_000, step=1_000,
        help="Kept in cash at 0% return. Never invested or used for the lump sum."
    )
    purchasing_costs_pct = st.slider(
        "Purchasing costs (%)", 1.0, 8.0, 3.5, 0.1,
        help=(
            "Registration tax + notary fees as a % of the house price.\n\n"
            "🇧🇪 Flanders (first home): 2% + ~1% notary ≈ 3% total\n"
            "🇧🇪 Brussels: abatement on first €175k + 12.5% above + ~1% notary\n"
            "🇧🇪 Wallonia: 12.5% standard rate + ~1% notary\n\n"
            "Default 3.5% is a reasonable estimate for a first-time buyer in Flanders."
        )
    )

with st.sidebar.expander("Mortgage", expanded=True):
    annual_rate = st.slider(
        "Interest rate (%)", 1.0, 6.0, 3.0, 0.1,
        help="Annual fixed interest rate on the mortgage."
    )
    total_years = st.slider(
        "Mortgage duration (years)", 10, 30, 25,
        help="Total loan duration."
    )

with st.sidebar.expander("Expat phase (post-purchase)", expanded=True):
    expat_years = st.slider(
        "Years as expat after buying", 1, 10, 2,
        help="How long you keep the expat salary after purchasing. This is the window to save the lump sum."
    )
    expat_monthly_savings = st.number_input(
        "Expat monthly savings (€)", value=4_000, step=500,
        help=(
            "Total amount you can save each month during the expat phase. "
            "This will be automatically split: part goes to the recast fund (0% return, earmarked), "
            "the rest is invested in your long-term portfolio."
        )
    )
    target_phase2_payment = st.number_input(
        "Target monthly payment after recast (€)", value=1_400, step=100,
        help="The maximum monthly mortgage payment you can afford on your post-expat salary. The lump sum is sized to hit this exactly."
    )

with st.sidebar.expander("Post-expat phase", expanded=False):
    future_salary_base = st.number_input(
        "Expected net salary post-expat (€/month)", value=3_200, step=100,
        help="Your expected monthly take-home pay after returning from expat life."
    )
    normal_monthly_savings_base = st.number_input(
        "Monthly investments post-expat (€)", value=500, step=100,
        help="Amount you'll invest each month after the expat phase (on top of the mortgage payment). Grows automatically with real salary growth."
    )

with st.sidebar.expander("Market assumptions", expanded=False):
    salary_growth_rate = st.slider("Salary growth (%/year)", 0.0, 10.0, 4.0, 0.5,
        help="Annual increase in your gross salary.") / 100
    inflation_rate = st.slider("Inflation (%/year)", 0.0, 10.0, 2.0, 0.5,
        help="Annual cost-of-living increase. The 'real' growth of your savings capacity = salary growth − inflation.") / 100
    investment_return_rate = st.slider("Investment return (%/year)", 0.0, 15.0, 7.0, 0.5,
        help="Expected compound annual return on your invested portfolio.") / 100
    house_appreciation_rate = st.slider("House appreciation (%/year)", 0.0, 10.0, 3.0, 0.5,
        help="Expected annual increase in the property value.") / 100


# ─────────────────────────────────────────────
# 3. Cached Logic
# ─────────────────────────────────────────────
@st.cache_data
def run_simulation(
    house_price, total_initial_savings, initial_downpayment, cash_buffer_input, purchasing_costs_pct,
    annual_rate, total_years, expat_years, expat_monthly_savings, target_phase2_payment,
    future_salary_base, normal_monthly_savings_base, salary_growth_rate, inflation_rate,
    investment_return_rate, house_appreciation_rate
):
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

    # Phase 1 payment (original amortisation)
    m_initial = (
        principal * (monthly_rate * (1 + monthly_rate) ** total_months)
        / ((1 + monthly_rate) ** total_months - 1)
    ) if monthly_rate > 0 else principal / total_months

    # Pre-simulation: Calculate lump sum target
    _bal = principal
    for _ in range(expat_months):
        _interest = _bal * monthly_rate
        _bal -= (m_initial - _interest)
    balance_at_recast = _bal

    # Balance needed to hit the target payment over the remaining term.
    if remaining_months > 0:
        target_balance_for_recast = (
            target_phase2_payment
            * ((1 + monthly_rate) ** remaining_months - 1)
            / (monthly_rate * (1 + monthly_rate) ** remaining_months)
        )
    else:
        target_balance_for_recast = 0

    required_net_drop = max(0, balance_at_recast - target_balance_for_recast)

    # Gross lump sum accounts for the 3-month interest penalty.
    required_gross_lump_sum = required_net_drop / (1 - 3 * monthly_rate) if required_net_drop > 0 else 0
    penalty                 = required_gross_lump_sum * monthly_rate * 3
    net_lump_sum            = required_gross_lump_sum - penalty

    monthly_recast_contribution  = required_gross_lump_sum / expat_months if expat_months > 0 else 0
    monthly_invest_contribution   = max(0, expat_monthly_savings - monthly_recast_contribution)
    monthly_shortfall             = max(0, monthly_recast_contribution - expat_monthly_savings)

    recast_fund_final = monthly_recast_contribution * expat_months
    actual_gross_lump_sum = min(required_gross_lump_sum, recast_fund_final)

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
            "Month": month,
            "Payment": m_initial, "Balance": balance,
            "Investment portfolio": portfolio_value, "Recast fund": recast_fund,
            "Cash buffer": actual_cash_buffer, "House value": house_value,
            "Target salary": salary_now,
            "Alt_payment": m_initial, "Alt_balance": balance, "Alt_portfolio": alt_portfolio,
        })

    portfolio_before_recast = portfolio_value
    balance -= net_lump_sum
    portfolio_value_after_recast = portfolio_value
    alt_balance = balance_at_recast

    if remaining_months > 0:
        m_new = (
            balance * (monthly_rate * (1 + monthly_rate) ** remaining_months)
            / ((1 + monthly_rate) ** remaining_months - 1)
        )
    else:
        m_new = 0

    for month in range(expat_months + 1, total_months + 1):
        interest  = balance * monthly_rate
        balance  -= (m_new - interest)

        yr = (month - 1) // 12
        salary_now = future_salary_base * ((1 + salary_growth_rate) ** yr)
        monthly_savings_now = normal_monthly_savings_base * (
            (1 + real_savings_growth) ** (yr - expat_years)
        )

        portfolio_value = portfolio_value * (1 + monthly_inv_rate) + monthly_savings_now
        house_value    *= (1 + monthly_appr_rate)

        alt_interest = alt_balance * monthly_rate
        alt_balance -= (m_initial - alt_interest)
        alt_savings  = max(0, monthly_savings_now - (m_initial - m_new))
        alt_portfolio = alt_portfolio * (1 + monthly_inv_rate) + alt_savings

        schedule.append({
            "Month": month,
            "Payment": m_new, "Balance": max(0, balance),
            "Investment portfolio": portfolio_value, "Recast fund": 0,
            "Cash buffer": actual_cash_buffer, "House value": house_value,
            "Target salary": salary_now,
            "Alt_payment": m_initial, "Alt_balance": max(0, alt_balance), "Alt_portfolio": alt_portfolio,
        })

    df = pd.DataFrame(schedule)
    df["Year"] = df["Month"] / 12
    df["Total liquid assets"]     = df["Investment portfolio"] + df["Cash buffer"]
    df["Total assets"]            = df["House value"] + df["Total liquid assets"] - df["Balance"]
    df["Alt_total liquid assets"] = df["Alt_portfolio"] + df["Cash buffer"]
    df["Alt_total assets"]        = df["House value"] + df["Alt_total liquid assets"] - df["Alt_balance"]

    total_phase1      = m_initial * expat_months
    total_phase2      = m_new     * remaining_months
    total_to_bank     = total_phase1 + total_phase2 + actual_gross_lump_sum
    total_interest    = total_to_bank - principal
    total_out_pocket  = initial_downpayment + total_to_bank

    return {
        "df": df,
        "m_initial": m_initial, "m_new": m_new,
        "required_gross_lump_sum": required_gross_lump_sum, "penalty": penalty,
        "monthly_recast_contribution": monthly_recast_contribution,
        "monthly_invest_contribution": monthly_invest_contribution,
        "monthly_shortfall": monthly_shortfall,
        "recast_fund_final": recast_fund_final,
        "actual_gross_lump_sum": actual_gross_lump_sum,
        "principal": principal, "balance_at_recast": balance_at_recast,
        "target_balance_for_recast": target_balance_for_recast, "net_lump_sum": net_lump_sum,
        "purchasing_costs": purchasing_costs, "actual_downpayment": actual_downpayment,
        "actual_cash_buffer": actual_cash_buffer, "starting_portfolio": starting_portfolio,
        "total_phase1": total_phase1, "total_phase2": total_phase2,
        "total_out_pocket": total_out_pocket, "total_interest": total_interest,
        "expat_months": expat_months, "remaining_months": remaining_months,
        "real_savings_growth": real_savings_growth
    }

res = run_simulation(
    house_price, total_initial_savings, initial_downpayment, cash_buffer_input, purchasing_costs_pct,
    annual_rate, total_years, expat_years, expat_monthly_savings, target_phase2_payment,
    future_salary_base, normal_monthly_savings_base, salary_growth_rate, inflation_rate,
    investment_return_rate, house_appreciation_rate
)
df = res["df"]

# ─────────────────────────────────────────────
# 4. Headline metrics — The strategy at a glance
# ─────────────────────────────────────────────
st.markdown("### The strategy at a glance")
st.caption(
    "The three phases of your plan — and whether your expat savings are enough to fund it."
)

c1, c2, c3 = st.columns(3)
c1.metric(
    "① Phase 1 payment  *(expat)*",
    f"€{res['m_initial']:,.0f} / month",
    help=(
        "Your fixed monthly mortgage payment during the expat phase. "
        "This is higher than what you'd qualify for post-expat — "
        "that's the whole point of leveraging your expat salary."
    )
)
c2.metric(
    "② Lump sum to recast",
    f"€{res['required_gross_lump_sum']:,.0f}",
    delta=f"= €{res['monthly_recast_contribution']:,.0f} / month × {res['expat_months']} months",
    delta_color="off",
    help=(
        f"The one-off payment at the end of year {expat_years} that brings the loan balance "
        f"down enough to hit your target monthly payment.\n\n"
        f"Includes a 3-month interest early-repayment penalty: €{res['penalty']:,.0f}.\n\n"
        f"Saved in a dedicated 0% recast fund — not invested, because you know "
        f"exactly when you'll need this money."
    )
)
c3.metric(
    "③ Phase 2 payment  *(post-expat)*",
    f"€{res['m_new']:,.0f} / month",
    delta=f"Target: €{target_phase2_payment:,.0f}",
    delta_color="off",
    help=(
        f"Your new monthly payment after the recast, over the remaining "
        f"{res['remaining_months'] // 12} years and {res['remaining_months'] % 12} months of the loan.\n\n"
        f"As a % of your expected post-expat salary: "
        f"{(res['m_new'] / future_salary_base) * 100:.1f}% of €{future_salary_base:,.0f}/month."
    )
)

st.markdown("")

c4, c5, c6 = st.columns(3)
c4.metric(
    "Monthly recast saving",
    f"€{res['monthly_recast_contribution']:,.0f} / month",
    help=(
        "Of your total expat savings, this portion is ring-fenced for the recast fund each month. "
        "It earns 0% — kept in a separate account (or term deposit) so it is safe and accessible on recast day. "
        "You could also put this in a termijnrekening (Belgian term deposit) to earn a small return over your horizon."
    )
)
c5.metric(
    "Monthly investment savings",
    f"€{res['monthly_invest_contribution']:,.0f} / month",
    delta=f"Remainder of your €{expat_monthly_savings:,.0f} / month",
    delta_color="normal" if res['monthly_invest_contribution'] >= 0 else "inverse",
    help=(
        "What is left for your long-term equity portfolio after the recast fund is funded. "
        "This goes into the market and compounds at your assumed investment return."
    )
)

if res['monthly_shortfall'] > 0:
    c6.metric(
        "⚠️ Monthly shortfall",
        f"€{res['monthly_shortfall']:,.0f} / month",
        delta="Savings insufficient for target",
        delta_color="inverse",
        help=(
            "Your expat savings aren't enough to fill the recast fund in time. "
            "To fix this: extend the expat phase, increase savings, or raise the target monthly payment."
        )
    )
else:
    surplus = expat_monthly_savings - res['monthly_recast_contribution']
    c6.metric(
        "✅ Plan is feasible",
        f"€{surplus:,.0f} / month surplus",
        delta="Recast fund fully covered",
        delta_color="normal",
        help=(
            "After ring-fencing the recast contribution, you have this much left each month "
            "for long-term investing. The lump sum is guaranteed regardless of market conditions."
        )
    )

# Validation errors
if initial_downpayment > total_initial_savings:
    st.error("❌ Down payment exceeds total initial capital. Please adjust your inputs.")

st.markdown("---")

# ─────────────────────────────────────────────
# 5. Charts
# ─────────────────────────────────────────────
C_WHITE    = "#F3F4F6"
C_GREEN    = "#10B981"
C_INDIGO   = "#6366F1"
C_RED      = "#EF4444"
C_PURPLE   = "#8B5CF6"
C_AMBER    = "#F59E0B"
C_BG       = "#111827"
C_GRID     = "#374151"
C_GREY     = "#9CA3AF"

fig = make_subplots(
    rows=3, cols=1,
    shared_xaxes=True,
    vertical_spacing=0.08,
    subplot_titles=(
        "1 — Monthly mortgage payment",
        "2 — Net worth breakdown over time",
        "3 — Recast vs. No recast (total net worth)",
    )
)

# Plot 1: Monthly Payment
fig.add_trace(go.Scatter(
    x=df["Year"], y=df["Payment"], name="Recast payment",
    fill="tozeroy", fillcolor="rgba(239,68,68,0.12)",
    line=dict(color=C_RED, width=2.5)
), row=1, col=1)
fig.add_trace(go.Scatter(
    x=df["Year"], y=df["Alt_payment"], name="No-recast payment",
    line=dict(color=C_GREY, width=1.8, dash="dash")
), row=1, col=1)
fig.add_trace(go.Scatter(
    x=df["Year"], y=df["Target salary"] * 0.33, name="33% of projected salary",
    line=dict(color=C_GREEN, width=1.8, dash="dot")
), row=1, col=1)

# Plot 2: Assets & Debt
fig.add_trace(go.Scatter(
    x=df["Year"], y=df["Total assets"], name="Total net worth",
    fill="tozeroy", fillcolor="rgba(243,244,246,0.04)",
    line=dict(color=C_WHITE, width=2.5)
), row=2, col=1)
fig.add_trace(go.Scatter(
    x=df["Year"], y=df["House value"], name="House value",
    line=dict(color=C_GREEN, width=1.8, dash="dash")
), row=2, col=1)
fig.add_trace(go.Scatter(
    x=df["Year"], y=df["Total liquid assets"], name="Liquid assets",
    line=dict(color=C_INDIGO, width=1.8, dash="dash")
), row=2, col=1)
fig.add_trace(go.Scatter(
    x=df["Year"], y=df["Balance"], name="Debt remaining",
    line=dict(color=C_RED, width=1.8)
), row=2, col=1)

# Plot 3: Recast vs No-Recast
fig.add_trace(go.Scatter(
    x=df["Year"], y=df["Total assets"], name="Net worth (recast)",
    line=dict(color=C_WHITE, width=2.5)
), row=3, col=1)
fig.add_trace(go.Scatter(
    x=df["Year"], y=df["Alt_total assets"], name="Net worth (no recast)",
    line=dict(color=C_PURPLE, width=2.5, dash="dash")
), row=3, col=1)

fig.update_traces(hovertemplate="€%{y:,.0f}")

for i in range(1, 4):
    fig.add_vline(
        x=expat_years, line_width=1.2, line_dash="dash", line_color=C_GREY,
        annotation_text="Recast", annotation_position="top left",
        row=i, col=1
    )
    fig.update_yaxes(showgrid=True, gridcolor=C_GRID, zeroline=False,
                     tickprefix="€", tickformat=",.0f", row=i, col=1)
    fig.update_xaxes(showgrid=False, zeroline=False, ticksuffix=" yr", row=i, col=1)

fig.update_xaxes(title_text="Timeline (years)", row=3, col=1)
fig.update_layout(
    template="plotly_dark",
    plot_bgcolor=C_BG, paper_bgcolor=C_BG,
    height=950,
    hovermode="x unified",
    hoverlabel=dict(namelength=-1),
    legend=dict(orientation="h", yanchor="bottom", y=1.04, xanchor="center", x=0.5),
    font=dict(color="#F9FAFB"),
    margin=dict(t=60, b=40, l=40, r=40),
)

st.plotly_chart(fig, use_container_width=True, theme=None)

st.markdown("---")

# ─────────────────────────────────────────────
# 6. Financial breakdown
# ─────────────────────────────────────────────
st.subheader("Full financial breakdown")
st.caption("Every number in the simulation, step by step — so you can explain it to anyone.")

left, right = st.columns([1.35, 1])

with left:

    # ── PURCHASE ─────────────────────────────
    st.markdown("#### 🏠 Purchase")
    st.markdown(
        f"You buy for **€{house_price:,.0f}**. "
        f"Purchasing costs ({purchasing_costs_pct}%) are **€{res['purchasing_costs']:,.0f}**, "
        f"paid from your down payment. The remainder of the down payment "
        f"(**€{res['actual_downpayment']:,.0f}**) reduces the loan."
    )
    st.markdown(f"""
| | Amount |
|:--|--:|
| House price | €{house_price:,.0f} |
| Purchasing costs ({purchasing_costs_pct}%) | − €{res['purchasing_costs']:,.0f} |
| Net down payment | − €{res['actual_downpayment']:,.0f} |
| **Starting loan** | **€{res['principal']:,.0f}** |
| Cash buffer (never touched) | €{res['actual_cash_buffer']:,.0f} |
| Initial investment portfolio | €{res['starting_portfolio']:,.0f} |
    """)

    # ── PHASE 1: EXPAT ───────────────────────
    st.markdown(f"#### ✈️ Phase 1 — Expat ({expat_years} years, {res['expat_months']} months)")
    st.markdown(
        f"You pay **€{res['m_initial']:,.0f}/month** on the mortgage. "
        f"Your €{expat_monthly_savings:,.0f}/month savings are split into two separate buckets:"
    )
    st.markdown(f"""
| Bucket | Monthly | Total after {res['expat_months']} months | Return |
|:--|--:|--:|:--|
| 🔒 Recast fund | €{res['monthly_recast_contribution']:,.0f} | €{res['recast_fund_final']:,.0f} | 0% — kept safe |
| 📈 Investment portfolio | €{res['monthly_invest_contribution']:,.0f} | *(grows with market)* | {investment_return_rate*100:.1f}%/yr |
    """)
    st.caption(
        "The recast fund earns 0% by design. Since you know exactly when and how much you need, "
        "putting it in the market creates unnecessary timing risk. Consider a termijnrekening (term deposit) "
        "if you want a risk-free return over your exact horizon."
    )

    # ── RECAST EVENT ─────────────────────────
    st.markdown(f"#### 🔄 Recast — End of year {expat_years}")
    st.markdown(
        f"The recast fund is used to make a single lump sum payment, "
        f"bringing the loan balance down to the level needed to hit your target monthly payment."
    )
    st.markdown(f"""
| | Amount | Explanation |
|:--|--:|:--|
| Loan balance at recast | €{res['balance_at_recast']:,.0f} | After {res['expat_months']} months of normal payments |
| Target balance needed | €{res['target_balance_for_recast']:,.0f} | To hit €{target_phase2_payment:,.0f}/month over {res['remaining_months']//12} yrs |
| Required lump sum (gross) | €{res['required_gross_lump_sum']:,.0f} | Includes the early-repayment penalty |
| Early repayment penalty | − €{res['penalty']:,.0f} | 3 months interest (standard Belgian law) |
| Net reduction to loan | €{res['net_lump_sum']:,.0f} | Actual debt reduction applied |
| **New monthly payment** | **€{res['m_new']:,.0f}** | Recalculated over remaining {res['remaining_months']//12} yrs {res['remaining_months']%12} mths |
    """)

    # ── PHASE 2: POST-EXPAT ──────────────────
    st.markdown(f"#### 🏡 Phase 2 — Post-expat (year {expat_years + 1} → {total_years})")
    st.markdown(
        f"You pay **€{res['m_new']:,.0f}/month** — "
        f"**{(res['m_new'] / future_salary_base)*100:.1f}%** of your expected "
        f"€{future_salary_base:,.0f}/month net salary. "
        f"The investment portfolio continues to compound."
    )
    st.markdown(f"""
| | Amount |
|:--|--:|
| Monthly mortgage payment | €{res['m_new']:,.0f} |
| Payment as % of post-expat salary | {(res['m_new']/future_salary_base)*100:.1f}% |
| Starting monthly investments | €{normal_monthly_savings_base:,.0f} |
| Real savings growth (salary − inflation) | {(res['real_savings_growth']*100):.1f}%/yr |
| **Final total net worth** | **€{df.iloc[-1]['Total assets']:,.0f}** |
    """)

with right:

    # ── DONUT CHART ───────────────────────────
    st.markdown("#### Total cash outflows")
    labels = ["Down payment", "Lump sum (recast)", "Phase 1 payments", "Phase 2 payments"]
    values = [initial_downpayment, res['actual_gross_lump_sum'], res['total_phase1'], res['total_phase2']]
    colors = [C_GREEN, C_AMBER, C_PURPLE, C_RED]

    fig_donut = go.Figure(data=[go.Pie(
        labels=labels, values=values, hole=0.62,
        marker=dict(colors=colors, line=dict(color=C_BG, width=2)),
        hovertemplate="%{label}<br>€%{value:,.0f}  (%{percent})<extra></extra>",
        textfont_size=12,
    )])
    fig_donut.update_layout(
        template="plotly_dark",
        plot_bgcolor=C_BG, paper_bgcolor=C_BG,
        font=dict(color="#F9FAFB"),
        annotations=[dict(
            text=f"Total paid<br><b>€{res['total_out_pocket']:,.0f}</b>",
            x=0.5, y=0.5, font_size=13, showarrow=False, font_color="#F9FAFB"
        )],
        showlegend=True,
        legend=dict(orientation="h", yanchor="top", y=-0.05, xanchor="center", x=0.5),
        margin=dict(t=10, b=10, l=10, r=10),
        height=320,
    )
    st.plotly_chart(fig_donut, use_container_width=True, theme=None)

    # ── TOTALS TABLE ──────────────────────────
    st.markdown("#### Cost summary")
    st.markdown(f"""
| | Amount |
|:--|--:|
| Down payment | €{initial_downpayment:,.0f} |
| Phase 1 payments ({res['expat_months']} mths × €{res['m_initial']:,.0f}) | €{res['total_phase1']:,.0f} |
| Lump sum (recast) | €{res['actual_gross_lump_sum']:,.0f} |
| Phase 2 payments ({res['remaining_months']} mths × €{res['m_new']:,.0f}) | €{res['total_phase2']:,.0f} |
| **Total paid out of pocket** | **€{res['total_out_pocket']:,.0f}** |
| of which: interest & fees | €{res['total_interest']:,.0f} |
| of which: principal repaid | €{res['principal']:,.0f} |
    """)

    st.markdown("#### Comparison at end of mortgage")
    final_recast    = df.iloc[-1]["Total assets"]
    final_norecast  = df.iloc[-1]["Alt_total assets"]
    diff = final_recast - final_norecast
    st.markdown(f"""
| Scenario | Final net worth |
|:--|--:|
| **Recast** (this strategy) | **€{final_recast:,.0f}** |
| No recast | €{final_norecast:,.0f} |
| Difference | {"+" if diff >= 0 else ""}€{diff:,.0f} |
    """)
    if diff >= 0:
        st.success(f"The recast strategy ends **€{diff:,.0f} ahead** in total net worth.")
    else:
        st.warning(f"No recast ends **€{abs(diff):,.0f} ahead** in total net worth. Consider whether the payment comfort is worth the trade-off.")

st.markdown("---")
st.download_button(
    "📥 Download full monthly simulation data (CSV)",
    data=df.to_csv(index=False).encode('utf-8'),
    file_name="mortgage_simulation.csv",
    mime="text/csv"
)