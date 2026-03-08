import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- 1. PAGE SETUP ---
st.set_page_config(page_title="Mortgage Dashboard", layout="wide")
st.title("Expat mortgage simulator")

# --- 2. SIDEBAR INPUTS ---
st.sidebar.header("Property & initial capital")
house_price = st.sidebar.number_input(
    "House price (€)", value=400000, step=10000,
    help="Total property purchase price before taxes and notary fees."
)
total_initial_savings = st.sidebar.number_input(
    "Total initial capital (€)", value=100000, step=10000,
    help="Total capital available (both invested and liquid) before buying the property."
)
initial_downpayment = st.sidebar.number_input(
    "Down payment (€)", value=80000, step=10000,
    help="Capital used for the purchase. Assumes 4% goes to purchasing costs; the rest reduces the starting loan."
)
cash_buffer_input = st.sidebar.number_input(
    "Static cash buffer (€)", value=10000, step=1000,
    help="Emergency fund. Kept in cash, earns 0% interest, and is never invested or used for the lump sum."
)

annual_rate = st.sidebar.slider(
    "Interest rate (%)", min_value=1.0, max_value=6.0, value=3.0, step=0.1,
    help="Annual fixed interest rate of the mortgage."
)
total_years = st.sidebar.slider(
    "Mortgage years", 10, 30, 25,
    help="Total duration of the mortgage loan."
)

st.sidebar.header("Expat phase")
expat_years = st.sidebar.slider(
    "Years as expat", 1, 10, 2,
    help="Duration of the high-income/high-savings phase."
)
expat_monthly_savings = st.sidebar.number_input(
    "Expat monthly savings (€)", value=4000, step=500,
    help="Monthly amount invested into the portfolio during the expat phase."
)

st.sidebar.header("Post-expat phase")
future_salary_base = st.sidebar.number_input(
    "Base net salary (€)", value=3200, step=100,
    help="Expected net monthly salary in today's euros after returning from the expat assignment."
)
target_phase2_payment = st.sidebar.number_input(
    "Target monthly payment (€)", value=1400, step=100,
    help="The maximum monthly mortgage payment you want to pay after the expat phase ends."
)
normal_monthly_savings_base = st.sidebar.number_input(
    "Normal monthly savings (€)", value=500, step=100,
    help="Base monthly investment post-expat. This amount will automatically grow over time based on your salary growth minus inflation."
)

st.sidebar.header("Market assumptions")
salary_growth_rate = st.sidebar.slider(
    "Salary growth (%)", 0.0, 10.0, 4.0, 0.5,
    help="Annual percentage increase in your salary."
) / 100
inflation_rate = st.sidebar.slider(
    "Inflation (%)", 0.0, 10.0, 2.0, 0.5,
    help="Annual cost of living increase. Subtracted from salary growth to calculate the 'real' growth rate of your monthly savings capacity."
) / 100
investment_return_rate = st.sidebar.slider(
    "Investment return (%)", 0.0, 15.0, 7.0, 0.5,
    help="Expected annual compound growth rate of your invested portfolio."
) / 100
house_appreciation_rate = st.sidebar.slider(
    "House appreciation (%)", 0.0, 10.0, 3.0, 0.5,
    help="Expected annual increase in the property's value."
) / 100

# --- 3. CORE LOGIC ---
purchasing_costs = house_price * 0.04
actual_downpayment = initial_downpayment - purchasing_costs
principal = house_price - actual_downpayment

starting_leftover_cash = total_initial_savings - initial_downpayment
actual_cash_buffer = min(starting_leftover_cash, cash_buffer_input) if starting_leftover_cash > 0 else 0
starting_portfolio = max(0, starting_leftover_cash - actual_cash_buffer)

monthly_rate = (annual_rate / 100) / 12
total_months = total_years * 12
expat_months = expat_years * 12

monthly_investment_rate = (1 + investment_return_rate)**(1/12) - 1
monthly_appreciation_rate = (1 + house_appreciation_rate)**(1/12) - 1
real_savings_growth_rate = salary_growth_rate - inflation_rate 

m_initial = principal * (monthly_rate * (1 + monthly_rate)**total_months) / ((1 + monthly_rate)**total_months - 1)

schedule = []
balance = principal
portfolio_value = starting_portfolio 
current_house_value = house_price

for month in range(1, expat_months + 1):
    interest = balance * monthly_rate
    principal_paid = m_initial - interest
    balance -= principal_paid
    portfolio_value = portfolio_value * (1 + monthly_investment_rate) + expat_monthly_savings
    current_house_value *= (1 + monthly_appreciation_rate)
    
    current_year = (month - 1) // 12
    current_normal_salary = future_salary_base * ((1 + salary_growth_rate) ** current_year)
    schedule.append({
        'Month': month, 'Payment': m_initial, 'Balance': balance, 
        'Target Salary': current_normal_salary, 'Investment Portfolio': portfolio_value, 
        'Cash Buffer': actual_cash_buffer, 'House Value': current_house_value,
        'Alt_Payment': m_initial, 'Alt_Balance': balance, 'Alt_Portfolio': portfolio_value
    })
    
remaining_months = total_months - expat_months
target_balance = target_phase2_payment * (((1 + monthly_rate)**remaining_months - 1) / (monthly_rate * (1 + monthly_rate)**remaining_months))
required_net_drop = balance - target_balance

required_gross_lump_sum = max(0, required_net_drop / (1 - 3 * monthly_rate))
portfolio_value_before_recast = portfolio_value
actual_gross_lump_sum = min(required_gross_lump_sum, portfolio_value_before_recast)
shortfall = required_gross_lump_sum - actual_gross_lump_sum

penalty = actual_gross_lump_sum * monthly_rate * 3
net_lump_sum = actual_gross_lump_sum - penalty
balance -= net_lump_sum
portfolio_value -= actual_gross_lump_sum 

m_new = balance * (monthly_rate * (1 + monthly_rate)**remaining_months) / ((1 + monthly_rate)**remaining_months - 1)

alt_balance = schedule[-1]['Alt_Balance']
alt_portfolio = schedule[-1]['Alt_Portfolio']

for month in range(expat_months + 1, total_months + 1):
    interest = balance * monthly_rate
    principal_paid = m_new - interest
    balance -= principal_paid
    
    current_year = (month - 1) // 12
    current_normal_salary = future_salary_base * ((1 + salary_growth_rate) ** current_year)
    current_monthly_savings = normal_monthly_savings_base * ((1 + real_savings_growth_rate) ** (current_year - expat_years))
    
    portfolio_value = portfolio_value * (1 + monthly_investment_rate) + current_monthly_savings
    current_house_value *= (1 + monthly_appreciation_rate)
    
    alt_interest = alt_balance * monthly_rate
    alt_principal_paid = m_initial - alt_interest
    alt_balance -= alt_principal_paid
    
    alt_monthly_savings = current_monthly_savings - (m_initial - m_new)
    alt_portfolio = alt_portfolio * (1 + monthly_investment_rate) + alt_monthly_savings

    schedule.append({
        'Month': month, 'Payment': m_new, 'Balance': max(0, balance), 
        'Target Salary': current_normal_salary, 'Investment Portfolio': portfolio_value, 
        'Cash Buffer': actual_cash_buffer, 'House Value': current_house_value,
        'Alt_Payment': m_initial, 'Alt_Balance': max(0, alt_balance), 'Alt_Portfolio': alt_portfolio
    })

df = pd.DataFrame(schedule)
df['Total Liquid Assets'] = df['Investment Portfolio'] + df['Cash Buffer']
df['Total Assets'] = df['House Value'] + df['Total Liquid Assets'] - df['Balance']

df['Alt_Total Liquid Assets'] = df['Alt_Portfolio'] + df['Cash Buffer']
df['Alt_Total Assets'] = df['House Value'] + df['Alt_Total Liquid Assets'] - df['Alt_Balance']

total_phase1_payments = m_initial * expat_months
total_phase2_payments = m_new * remaining_months
total_paid_to_bank = total_phase1_payments + total_phase2_payments + actual_gross_lump_sum
total_interest_and_penalties = total_paid_to_bank - principal
total_out_of_pocket = initial_downpayment + total_paid_to_bank

# --- 4. TOP DASHBOARD METRICS ---
col1, col2, col3, col4 = st.columns(4)
col1.metric("Down payment", f"€{initial_downpayment:,.0f}")
col2.metric("Lump sum paid", f"€{actual_gross_lump_sum:,.0f}")
col3.metric("New payment", f"€{m_new:,.0f}")
col4.metric(f"Final total assets", f"€{df.iloc[-1]['Total Assets']:,.0f}")

st.markdown("---")

# --- 5. PLOTLY VISUALIZATIONS (DARK MODE) ---
c_networth = '#F3F4F6'  
c_house = '#10B981'     
c_portfolio = '#6366F1' 
c_debt = '#EF4444'      
c_alt = '#8B5CF6'       
c_bg_dark = '#111827'   

fig = make_subplots(
    rows=3, cols=1, 
    shared_xaxes=True, 
    vertical_spacing=0.08,
    subplot_titles=(
        "1. Monthly cash flow", 
        "2. Assets & debt", 
        "3. Recast vs. No recast (Total assets)"
    )
)

# Plot 1: Cash Flow
fig.add_trace(go.Scatter(x=df['Month'], y=df['Payment'], name="Recast payment", fill='tozeroy', fillcolor='rgba(239, 68, 68, 0.15)', line=dict(color=c_debt, width=3)), row=1, col=1)
fig.add_trace(go.Scatter(x=df['Month'], y=df['Alt_Payment'], name="No recast payment", line=dict(color='#9CA3AF', width=2, dash='dash')), row=1, col=1)
fig.add_trace(go.Scatter(x=df['Month'], y=df['Target Salary']*0.33, name="33% salary limit", line=dict(color=c_house, width=2, dash='dot')), row=1, col=1)

# Plot 2: Main Assets
fig.add_trace(go.Scatter(x=df['Month'], y=df['Total Assets'], name="Total assets", fill='tozeroy', fillcolor='rgba(243, 244, 246, 0.05)', line=dict(color=c_networth, width=3)), row=2, col=1)
fig.add_trace(go.Scatter(x=df['Month'], y=df['House Value'], name="House value", line=dict(color=c_house, width=2, dash='dash')), row=2, col=1)
fig.add_trace(go.Scatter(x=df['Month'], y=df['Total Liquid Assets'], name="Liquid assets", line=dict(color=c_portfolio, width=2, dash='dash')), row=2, col=1)
fig.add_trace(go.Scatter(x=df['Month'], y=df['Balance'], name="Debt", line=dict(color=c_debt, width=2)), row=2, col=1)

# Plot 3: Comparison
fig.add_trace(go.Scatter(x=df['Month'], y=df['Total Assets'], name="Assets (Recast)", line=dict(color=c_networth, width=3)), row=3, col=1)
fig.add_trace(go.Scatter(x=df['Month'], y=df['Alt_Total Assets'], name="Assets (No recast)", line=dict(color=c_alt, width=3, dash='dash')), row=3, col=1)

# Force the tooltips to use clean euro formatting without decimals
fig.update_traces(hovertemplate="€%{y:,.0f}")

# Styling & Vertical Lines
for i in range(1, 4):
    fig.add_vline(x=expat_months, line_width=1.5, line_dash="dash", line_color="#9CA3AF", annotation_text="Recast", annotation_position="top left", row=i, col=1)
    fig.update_yaxes(showgrid=True, gridcolor='#374151', zeroline=False, tickprefix="€", tickformat=",.0f", row=i, col=1)
    fig.update_xaxes(showgrid=False, zeroline=False, row=i, col=1)

fig.update_xaxes(title_text="Timeline (months)", row=3, col=1)

fig.update_layout(
    template="plotly_dark",
    plot_bgcolor=c_bg_dark, 
    paper_bgcolor=c_bg_dark,
    height=900, 
    hovermode="x unified",
    hoverlabel=dict(namelength=-1), # Prevents truncation of line names in the tooltip
    legend=dict(
        orientation="h", 
        yanchor="bottom", 
        y=1.05, 
        xanchor="center", 
        x=0.5
    ),
    font=dict(color='#F9FAFB'),
    margin=dict(t=60, b=40, l=40, r=40)
)

st.plotly_chart(fig, use_container_width=True, theme=None)

st.markdown("---")

# --- 6. DATA SUMMARY ---
st.subheader("Financial summary")

if shortfall > 0:
    st.warning(f"Shortfall: €{shortfall:,.0f}. Invested savings fully depleted. Target payment not reached.")
elif initial_downpayment > total_initial_savings:
    st.error("Error: Down payment exceeds total initial capital.")

col_text, col_chart = st.columns([1.5, 1])

with col_text:
    st.markdown(f"""
| Metric | Amount | Description |
| :--- | :--- | :--- |
| **Starting loan** | **€{principal:,.0f}** | House price minus down payment (incl. 4% fees). |
| **Cash buffer** | **€{actual_cash_buffer:,.0f}** | Static emergency fund. |
| **Initial investment** | **€{starting_portfolio:,.0f}** | Remaining capital invested at month 1. |
| **Investments at recast** | **€{portfolio_value_before_recast:,.0f}** | Liquid investments available before recast. |
| **Required lump sum** | **€{required_gross_lump_sum:,.0f}** | Amount needed to reach target payment. |
| **Actual lump sum** | **€{actual_gross_lump_sum:,.0f}** | Amount paid (capped by available investments). |
| **Bank penalty** | **€{penalty:,.0f}** | 3 months interest fee. |
| **Total cash paid** | **€{total_out_of_pocket:,.0f}** | Total amount paid over {total_years} years. |
| **Total interest & fees** | **€{total_interest_and_penalties:,.0f}** | Total bank profit. |
    """)

with col_chart:
    labels = ['Down payment', 'Lump sum', 'Phase 1 payments', 'Phase 2 payments']
    values = [initial_downpayment, actual_gross_lump_sum, total_phase1_payments, total_phase2_payments]
    colors = [c_house, '#3B82F6', '#8B5CF6', c_debt]
    
    fig_donut = go.Figure(data=[go.Pie(
        labels=labels, values=values, hole=0.6,
        marker=dict(colors=colors, line=dict(color=c_bg_dark, width=2)),
        hovertemplate="%{label}<br>€%{value:,.0f} (%{percent})<extra></extra>" # Clean formatting here too
    )])
    
    fig_donut.update_layout(
        template="plotly_dark",
        plot_bgcolor=c_bg_dark, 
        paper_bgcolor=c_bg_dark,
        font=dict(color='#F9FAFB'),
        annotations=[dict(text=f"Total paid:<br>€{total_out_of_pocket:,.0f}", x=0.5, y=0.5, font_size=14, showarrow=False, font_weight='bold', font_color='#F9FAFB')],
        showlegend=True, 
        legend=dict(orientation="h", yanchor="top", y=-0.1, xanchor="center", x=0.5),
        margin=dict(t=20, b=20, l=20, r=20)
    )
    
    st.plotly_chart(fig_donut, use_container_width=True, theme=None)