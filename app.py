import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ─────────────────────────────────────────────
# 1. PAGE SETUP
# ─────────────────────────────────────────────
st.set_page_config(page_title="Expat Mortgage Simulator", layout="wide")

st.title("Expat Mortgage Simulator")
st.caption(
    "Strategy: Use your expat salary to qualify for a larger loan → "
    "save a fixed lump sum during the expat phase → recast the mortgage → "
    "affordable payment on your post-expat salary."
)

# ─────────────────────────────────────────────
# 2. SIDEBAR INPUTS
# ─────────────────────────────────────────────
st.sidebar.header("Property & Capital")

house_price = st.sidebar.number_input(
    "House price (€)", value=400_000, step=10_000,
    help="Total purchase price of the property."
)
total_initial_savings = st.sidebar.number_input(
    "Total initial capital (€)", value=200_000, step=10_000,
    help="All savings available before buying (invested + liquid)."
)
initial_downpayment = st.sidebar.number_input(
    "Down payment (€)", value=80_000, step=10_000,
    help="Capital allocated to the purchase. Purchasing costs are deducted from this first; the remainder reduces the starting loan."
)
cash_buffer_input = st.sidebar.number_input(
    "Emergency cash buffer (€)", value=10_000, step=1_000,
    help="Kept in cash at 0% return. Never invested or used for the lump sum."
)
purchasing_costs_pct = st.sidebar.slider(
    "Purchasing costs (%)", 1.0, 8.0, 3.5, 0.1,
    help=(
        "Registration tax + notary fees as a % of the house price.\n\n"
        "🇧🇪 Flanders (first home): 2% + ~1% notary ≈ 3% total\n"
        "🇧🇪 Brussels: abatement on first €175k + 12.5% above + ~1% notary\n"
        "🇧🇪 Wallonia: 12.5% standard rate + ~1% notary\n\n"
        "Default 3.5% is a reasonable estimate for a first-time buyer in Flanders."
    )
)

st.sidebar.header("Mortgage")

annual_rate = st.sidebar.slider(
    "Interest rate (%)", 1.0, 6.0, 3.0, 0.1,
    help="Annual fixed interest rate on the mortgage."
)
total_years = st.sidebar.slider(
    "Mortgage duration (years)", 10, 30, 25,
    help="Total loan duration."
)

st.sidebar.header("Expat Phase (post-purchase)")

expat_years = st.sidebar.slider(
    "Years as expat after buying", 1, 10, 2,
    help="How long you keep the expat salary after purchasing. This is the window to save the lump sum."
)
expat_monthly_savings = st.sidebar.number_input(
    "Expat monthly savings (€)", value=4_000, step=500,
    help=(
        "Total amount you can save each month during the expat phase. "
        "This will be automatically split: part goes to the recast fund (0% return, earmarked), "
        "the rest is invested in your long-term portfolio."
    )
)
target_phase2_payment = st.sidebar.number_input(
    "Target monthly payment after recast (€)", value=1_400, step=100,
    help="The maximum monthly mortgage payment you can afford on your post-expat salary. The lump sum is sized to hit this exactly."
)

st.sidebar.header("Post-Expat Phase")

future_salary_base = st.sidebar.number_input(
    "Expected net salary post-expat (€/month)", value=3_200, step=100,
    help="Your expected monthly take-home pay after returning from expat life."
)
normal_monthly_savings_base = st.sidebar.number_input(
    "Monthly investments post-expat (€)", value=500, step=100,
    help="Amount you'll invest each month after the expat phase (on top of the mortgage payment). Grows automatically with real salary growth."
)

st.sidebar.header("Market Assumptions")

salary_growth_rate = st.sidebar.slider("Salary growth (%/year)", 0.0, 10.0, 4.0, 0.5,
    help="Annual increase in your gross salary.") / 100
inflation_rate = st.sidebar.slider("Inflation (%/year)", 0.0, 10.0, 2.0, 0.5,
    help="Annual cost-of-living increase. The 'real' growth of your savings capacity = salary growth − inflation.") / 100
investment_return_rate = st.sidebar.slider("Investment return (%/year)", 0.0, 15.0, 7.0, 0.5,
    help="Expected compound annual return on your invested portfolio.") / 100
house_appreciation_rate = st.sidebar.slider("House appreciation (%/year)", 0.0, 10.0, 3.0, 0.5,
    help="Expected annual increase in the property value.") / 100

# ─────────────────────────────────────────────
# 3. DERIVED CONSTANTS
# ─────────────────────────────────────────────
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
)

# ─────────────────────────────────────────────
# 4. PRE-SIMULATION: CALCULATE LUMP SUM TARGET
# ─────────────────────────────────────────────
# Run a quick pass to find the loan balance at the recast date.
_bal = principal
for _ in range(expat_months):
    _interest = _bal * monthly_rate
    _bal -= (m_initial - _interest)
balance_at_recast = _bal

# Balance needed to hit the target payment over the remaining term.
target_balance_for_recast = (
    target_phase2_payment
    * ((1 + monthly_rate) ** remaining_months - 1)
    / (monthly_rate * (1 + monthly_rate) ** remaining_months)
) if remaining_months > 0 else 0

required_net_drop = max(0, balance_at_recast - target_balance_for_recast)

# Gross lump sum accounts for the 3-month interest penalty.
# gross × (1 − 3 × monthly_rate) = net_drop  →  gross = net_drop / (1 − 3 × monthly_rate)
required_gross_lump_sum = required_net_drop / (1 - 3 * monthly_rate) if required_net_drop > 0 else 0
penalty                 = required_gross_lump_sum * monthly_rate * 3
net_lump_sum            = required_gross_lump_sum - penalty

# ─────────────────────────────────────────────
# 5. TWO-BUCKET SPLIT OF EXPAT SAVINGS
# ─────────────────────────────────────────────
# Bucket A – Recast fund: 0% return, kept safe, exact target known upfront.
# Bucket B – Investment portfolio: the remainder goes to long-term equities.
monthly_recast_contribution  = required_gross_lump_sum / expat_months if expat_months > 0 else 0
monthly_invest_contribution   = max(0, expat_monthly_savings - monthly_recast_contribution)
monthly_shortfall             = max(0, monthly_recast_contribution - expat_monthly_savings)

recast_fund_final = monthly_recast_contribution * expat_months  # exactly the target (0% interest)
actual_gross_lump_sum = min(required_gross_lump_sum, recast_fund_final)

# ─────────────────────────────────────────────
# 6. FULL SIMULATION
# ─────────────────────────────────────────────
schedule = []
balance           = principal
portfolio_value   = starting_portfolio
recast_fund       = 0.0
house_value       = house_price

# Alt scenario: no recast – full expat savings all invested, no lump sum paid.
alt_portfolio = starting_portfolio

# ── PHASE 1: Expat ──────────────────────────
for month in range(1, expat_months + 1):
    interest       = balance * monthly_rate
    balance       -= (m_initial - interest)
    recast_fund   += monthly_recast_contribution           # 0% — pure accumulation
    portfolio_value = portfolio_value * (1 + monthly_inv_rate) + monthly_invest_contribution
    alt_portfolio   = alt_portfolio   * (1 + monthly_inv_rate) + expat_monthly_savings  # all invested
    house_value    *= (1 + monthly_appr_rate)

    yr = (month - 1) // 12
    salary_now = future_salary_base * ((1 + salary_growth_rate) ** yr)

    schedule.append({
        "Month": month,
        "Payment": m_initial, "Balance": balance,
        "Investment Portfolio": portfolio_value, "Recast Fund": recast_fund,
        "Cash Buffer": actual_cash_buffer, "House Value": house_value,
        "Target Salary": salary_now,
        "Alt_Payment": m_initial, "Alt_Balance": balance, "Alt_Portfolio": alt_portfolio,
    })

# ── RECAST EVENT ────────────────────────────
portfolio_before_recast = portfolio_value  # snapshot for summary table
balance -= net_lump_sum                    # apply lump sum net of penalty
portfolio_value_after_recast = portfolio_value  # investment portfolio unchanged
alt_balance = balance_at_recast           # alt: no reduction

m_new = (
    balance * (monthly_rate * (1 + monthly_rate) ** remaining_months)
    / ((1 + monthly_rate) ** remaining_months - 1)
) if remaining_months > 0 else 0

# ── PHASE 2: Post-expat ─────────────────────
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

    # Alt: still paying m_initial → can save less (savings reduced by payment difference)
    alt_interest = alt_balance * monthly_rate
    alt_balance -= (m_initial - alt_interest)
    alt_savings  = max(0, monthly_savings_now - (m_initial - m_new))
    alt_portfolio = alt_portfolio * (1 + monthly_inv_rate) + alt_savings

    schedule.append({
        "Month": month,
        "Payment": m_new, "Balance": max(0, balance),
        "Investment Portfolio": portfolio_value, "Recast Fund": 0,
        "Cash Buffer": actual_cash_buffer, "House Value": house_value,
        "Target Salary": salary_now,
        "Alt_Payment": m_initial, "Alt_Balance": max(0, alt_balance), "Alt_Portfolio": alt_portfolio,
    })

# ── DataFrame ───────────────────────────────
df = pd.DataFrame(schedule)
df["Year"] = df["Month"] / 12
df["Total Liquid Assets"]     = df["Investment Portfolio"] + df["Cash Buffer"]
df["Total Assets"]            = df["House Value"] + df["Total Liquid Assets"] - df["Balance"]
df["Alt_Total Liquid Assets"] = df["Alt_Portfolio"] + df["Cash Buffer"]
df["Alt_Total Assets"]        = df["House Value"] + df["Alt_Total Liquid Assets"] - df["Alt_Balance"]

# ── Totals ──────────────────────────────────
total_phase1      = m_initial * expat_months
total_phase2      = m_new     * remaining_months
total_to_bank     = total_phase1 + total_phase2 + actual_gross_lump_sum
total_interest    = total_to_bank - principal
total_out_pocket  = initial_downpayment + total_to_bank

# ─────────────────────────────────────────────
# 7. HEADLINE METRICS — THE STRATEGY AT A GLANCE
# ─────────────────────────────────────────────
st.markdown("### The Strategy at a Glance")
st.caption(
    "The three phases of your plan — and whether your expat savings are enough to fund it."
)

c1, c2, c3 = st.columns(3)
c1.metric(
    "① Phase 1 payment  *(expat)*",
    f"€{m_initial:,.0f} / month",
    help=(
        "Your fixed monthly mortgage payment during the expat phase. "
        "This is higher than what you'd qualify for post-expat — "
        "that's the whole point of leveraging your expat salary."
    )
)
c2.metric(
    "② Lump sum to recast",
    f"€{required_gross_lump_sum:,.0f}",
    delta=f"= €{monthly_recast_contribution:,.0f} / month × {expat_months} months",
    delta_color="off",
    help=(
        f"The one-off payment at the end of year {expat_years} that brings the loan balance "
        f"down enough to hit your target monthly payment.\n\n"
        f"Includes a 3-month interest early-repayment penalty: €{penalty:,.0f}.\n\n"
        f"Saved in a dedicated 0% recast fund — not invested, because you know "
        f"exactly when you'll need this money."
    )
)
c3.metric(
    "③ Phase 2 payment  *(post-expat)*",
    f"€{m_new:,.0f} / month",
    delta=f"Target: €{target_phase2_payment:,.0f}",
    delta_color="off",
    help=(
        f"Your new monthly payment after the recast, over the remaining "
        f"{remaining_months // 12} years and {remaining_months % 12} months of the loan.\n\n"
        f"As a % of your expected post-expat salary: "
        f"{(m_new / future_salary_base) * 100:.1f}% of €{future_salary_base:,.0f}/month."
    )
)

st.markdown("")

c4, c5, c6 = st.columns(3)
c4.metric(
    "Monthly recast saving",
    f"€{monthly_recast_contribution:,.0f} / month",
    help=(
        "Of your total expat savings, this portion is ring-fenced for the recast fund each month. "
        "It earns 0% — kept in a separate account (or term deposit) so it is safe and accessible on recast day. "
        "You could also put this in a termijnrekening (Belgian term deposit) to earn a small return over your horizon."
    )
)
c5.metric(
    "Monthly investment savings",
    f"€{monthly_invest_contribution:,.0f} / month",
    delta=f"Remainder of your €{expat_monthly_savings:,.0f} / month",
    delta_color="normal" if monthly_invest_contribution >= 0 else "inverse",
    help=(
        "What is left for your long-term equity portfolio after the recast fund is funded. "
        "This goes into the market and compounds at your assumed investment return."
    )
)

if monthly_shortfall > 0:
    c6.metric(
        "⚠️ Monthly shortfall",
        f"€{monthly_shortfall:,.0f} / month",
        delta="Savings insufficient for target",
        delta_color="inverse",
        help=(
            "Your expat savings aren't enough to fill the recast fund in time. "
            "To fix this: extend the expat phase, increase savings, or raise the target monthly payment."
        )
    )
else:
    surplus = expat_monthly_savings - monthly_recast_contribution
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
# 8. CHARTS
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
        "3 — Recast vs. No recast  (total net worth)",
    )
)

# Plot 1: Monthly Payment
fig.add_trace(go.Scatter(
    x=df["Year"], y=df["Payment"], name="Recast payment",
    fill="tozeroy", fillcolor="rgba(239,68,68,0.12)",
    line=dict(color=C_RED, width=2.5)
), row=1, col=1)
fig.add_trace(go.Scatter(
    x=df["Year"], y=df["Alt_Payment"], name="No-recast payment",
    line=dict(color=C_GREY, width=1.8, dash="dash")
), row=1, col=1)
fig.add_trace(go.Scatter(
    x=df["Year"], y=df["Target Salary"] * 0.33, name="33% of projected salary",
    line=dict(color=C_GREEN, width=1.8, dash="dot")
), row=1, col=1)

# Plot 2: Assets & Debt
fig.add_trace(go.Scatter(
    x=df["Year"], y=df["Total Assets"], name="Total net worth",
    fill="tozeroy", fillcolor="rgba(243,244,246,0.04)",
    line=dict(color=C_WHITE, width=2.5)
), row=2, col=1)
fig.add_trace(go.Scatter(
    x=df["Year"], y=df["House Value"], name="House value",
    line=dict(color=C_GREEN, width=1.8, dash="dash")
), row=2, col=1)
fig.add_trace(go.Scatter(
    x=df["Year"], y=df["Total Liquid Assets"], name="Liquid assets",
    line=dict(color=C_INDIGO, width=1.8, dash="dash")
), row=2, col=1)
fig.add_trace(go.Scatter(
    x=df["Year"], y=df["Balance"], name="Debt remaining",
    line=dict(color=C_RED, width=1.8)
), row=2, col=1)

# Plot 3: Recast vs No-Recast
fig.add_trace(go.Scatter(
    x=df["Year"], y=df["Total Assets"], name="Net worth (recast)",
    line=dict(color=C_WHITE, width=2.5)
), row=3, col=1)
fig.add_trace(go.Scatter(
    x=df["Year"], y=df["Alt_Total Assets"], name="Net worth (no recast)",
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
# 9. FINANCIAL BREAKDOWN
# ─────────────────────────────────────────────
st.subheader("Full Financial Breakdown")
st.caption("Every number in the simulation, step by step — so you can explain it to anyone.")

left, right = st.columns([1.35, 1])

with left:

    # ── PURCHASE ─────────────────────────────
    st.markdown("#### 🏠 Purchase")
    st.markdown(
        f"You buy for **€{house_price:,.0f}**. "
        f"Purchasing costs ({purchasing_costs_pct}%) are **€{purchasing_costs:,.0f}**, "
        f"paid from your down payment. The remainder of the down payment "
        f"(**€{actual_downpayment:,.0f}**) reduces the loan."
    )
    st.markdown(f"""
| | Amount |
|:--|--:|
| House price | €{house_price:,.0f} |
| Purchasing costs ({purchasing_costs_pct}%) | − €{purchasing_costs:,.0f} |
| Net down payment | − €{actual_downpayment:,.0f} |
| **Starting loan** | **€{principal:,.0f}** |
| Cash buffer (never touched) | €{actual_cash_buffer:,.0f} |
| Initial investment portfolio | €{starting_portfolio:,.0f} |
    """)

    # ── PHASE 1: EXPAT ───────────────────────
    st.markdown(f"#### ✈️ Phase 1 — Expat ({expat_years} years, {expat_months} months)")
    st.markdown(
        f"You pay **€{m_initial:,.0f}/month** on the mortgage. "
        f"Your €{expat_monthly_savings:,.0f}/month savings are split into two separate buckets:"
    )
    st.markdown(f"""
| Bucket | Monthly | Total after {expat_months} months | Return |
|:--|--:|--:|:--|
| 🔒 Recast fund | €{monthly_recast_contribution:,.0f} | €{recast_fund_final:,.0f} | 0% — kept safe |
| 📈 Investment portfolio | €{monthly_invest_contribution:,.0f} | *(grows with market)* | {investment_return_rate*100:.1f}%/yr |
    """)
    st.caption(
        "The recast fund earns 0% by design. Since you know exactly when and how much you need, "
        "putting it in the market creates unnecessary timing risk. Consider a termijnrekening (term deposit) "
        "if you want a risk-free return over your exact horizon."
    )

    # ── RECAST EVENT ─────────────────────────
    st.markdown(f"#### 🔄 Recast — End of Year {expat_years}")
    st.markdown(
        f"The recast fund is used to make a single lump sum payment, "
        f"bringing the loan balance down to the level needed to hit your target monthly payment."
    )
    st.markdown(f"""
| | Amount | Explanation |
|:--|--:|:--|
| Loan balance at recast | €{balance_at_recast:,.0f} | After {expat_months} months of normal payments |
| Target balance needed | €{target_balance_for_recast:,.0f} | To hit €{target_phase2_payment:,.0f}/month over {remaining_months//12} yrs |
| Required lump sum (gross) | €{required_gross_lump_sum:,.0f} | Includes the early-repayment penalty |
| Early repayment penalty | − €{penalty:,.0f} | 3 months interest (standard Belgian law) |
| Net reduction to loan | €{net_lump_sum:,.0f} | Actual debt reduction applied |
| **New monthly payment** | **€{m_new:,.0f}** | Recalculated over remaining {remaining_months//12} yrs {remaining_months%12} mths |
    """)

    # ── PHASE 2: POST-EXPAT ──────────────────
    st.markdown(f"#### 🏡 Phase 2 — Post-Expat (year {expat_years + 1} → {total_years})")
    st.markdown(
        f"You pay **€{m_new:,.0f}/month** — "
        f"**{(m_new / future_salary_base)*100:.1f}%** of your expected "
        f"€{future_salary_base:,.0f}/month net salary. "
        f"The investment portfolio continues to compound."
    )
    st.markdown(f"""
| | Amount |
|:--|--:|
| Monthly mortgage payment | €{m_new:,.0f} |
| Payment as % of post-expat salary | {(m_new/future_salary_base)*100:.1f}% |
| Starting monthly investments | €{normal_monthly_savings_base:,.0f} |
| Real savings growth (salary − inflation) | {(real_savings_growth*100):.1f}%/yr |
| **Final total net worth** | **€{df.iloc[-1]["Total Assets"]:,.0f}** |
    """)

with right:

    # ── DONUT CHART ───────────────────────────
    st.markdown("#### Total Cash Outflows")
    labels = ["Down payment", "Lump sum (recast)", "Phase 1 payments", "Phase 2 payments"]
    values = [initial_downpayment, actual_gross_lump_sum, total_phase1, total_phase2]
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
            text=f"Total paid<br><b>€{total_out_pocket:,.0f}</b>",
            x=0.5, y=0.5, font_size=13, showarrow=False, font_color="#F9FAFB"
        )],
        showlegend=True,
        legend=dict(orientation="h", yanchor="top", y=-0.05, xanchor="center", x=0.5),
        margin=dict(t=10, b=10, l=10, r=10),
        height=320,
    )
    st.plotly_chart(fig_donut, use_container_width=True, theme=None)

    # ── TOTALS TABLE ──────────────────────────
    st.markdown("#### Cost Summary")
    st.markdown(f"""
| | Amount |
|:--|--:|
| Down payment | €{initial_downpayment:,.0f} |
| Phase 1 payments ({expat_months} mths × €{m_initial:,.0f}) | €{total_phase1:,.0f} |
| Lump sum (recast) | €{actual_gross_lump_sum:,.0f} |
| Phase 2 payments ({remaining_months} mths × €{m_new:,.0f}) | €{total_phase2:,.0f} |
| **Total paid out of pocket** | **€{total_out_pocket:,.0f}** |
| of which: interest & fees | €{total_interest:,.0f} |
| of which: principal repaid | €{principal:,.0f} |
    """)

    st.markdown("#### Comparison at End of Mortgage")
    final_recast    = df.iloc[-1]["Total Assets"]
    final_norecast  = df.iloc[-1]["Alt_Total Assets"]
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