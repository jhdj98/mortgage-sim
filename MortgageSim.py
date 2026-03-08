import pandas as pd
import matplotlib.pyplot as plt

def advanced_mortgage_sim(
    house_price=500000, 
    initial_downpayment=200000, 
    annual_rate=3.0, 
    total_years=25,
    expat_years=2,
    expat_monthly_savings=4000,
    future_salary_base=3200,
    salary_growth_rate=0.04,
    inflation_rate=0.02, 
    target_phase2_payment=1400,
    normal_monthly_savings_base=500,
    investment_return_rate=0.07,
    house_appreciation_rate=0.03
):
    # --- 1. INITIAL SETUP ---
    purchasing_costs = house_price * 0.04
    actual_downpayment = initial_downpayment - purchasing_costs
    principal = house_price - actual_downpayment
    
    monthly_rate = (annual_rate / 100) / 12
    total_months = total_years * 12
    expat_months = expat_years * 12
    
    monthly_investment_rate = (1 + investment_return_rate)**(1/12) - 1
    monthly_appreciation_rate = (1 + house_appreciation_rate)**(1/12) - 1
    real_savings_growth_rate = salary_growth_rate - inflation_rate 
    
    m_initial = principal * (monthly_rate * (1 + monthly_rate)**total_months) / ((1 + monthly_rate)**total_months - 1)
    
    # --- 2. THE EXPAT PHASE (Phase 1) ---
    schedule = []
    balance = principal
    portfolio_value = 0 
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
            'Month': month, 
            'Payment': m_initial, 
            'Balance': balance, 
            'Target Salary': current_normal_salary,
            'Investment Portfolio': portfolio_value,
            'House Value': current_house_value
        })
        
    # --- 3. REVERSE-ENGINEERING THE RECAST ---
    remaining_months = total_months - expat_months
    old_balance_before_recast = balance
    
    target_balance = target_phase2_payment * (((1 + monthly_rate)**remaining_months - 1) / (monthly_rate * (1 + monthly_rate)**remaining_months))
    required_net_drop = balance - target_balance
    required_gross_lump_sum = required_net_drop / (1 - 3 * monthly_rate)
    
    if required_gross_lump_sum > portfolio_value:
        actual_gross_lump_sum = portfolio_value
    elif required_gross_lump_sum <= 0:
        actual_gross_lump_sum = 0
    else:
        actual_gross_lump_sum = required_gross_lump_sum
        
    penalty = actual_gross_lump_sum * monthly_rate * 3
    net_lump_sum = actual_gross_lump_sum - penalty
    
    balance -= net_lump_sum
    portfolio_value -= actual_gross_lump_sum 
    
    m_new = balance * (monthly_rate * (1 + monthly_rate)**remaining_months) / ((1 + monthly_rate)**remaining_months - 1)
    
    # --- 4. THE NORMAL PHASE (Phase 2) ---
    for month in range(expat_months + 1, total_months + 1):
        interest = balance * monthly_rate
        principal_paid = m_new - interest
        balance -= principal_paid
        
        current_year = (month - 1) // 12
        current_normal_salary = future_salary_base * ((1 + salary_growth_rate) ** current_year)
        current_monthly_savings = normal_monthly_savings_base * ((1 + real_savings_growth_rate) ** (current_year - expat_years))
        
        portfolio_value = portfolio_value * (1 + monthly_investment_rate) + current_monthly_savings
        current_house_value *= (1 + monthly_appreciation_rate)
        
        schedule.append({
            'Month': month, 
            'Payment': m_new, 
            'Balance': balance, 
            'Target Salary': current_normal_salary,
            'Investment Portfolio': portfolio_value,
            'House Value': current_house_value
        })
        
    df = pd.DataFrame(schedule)
    df['Total Net Worth'] = df['House Value'] + df['Investment Portfolio'] - df['Balance']
    
    # --- 5. CALCULATIONS FOR OUTPUT ---
    total_phase1_payments = m_initial * expat_months
    total_phase2_payments = m_new * remaining_months
    total_paid_to_bank = total_phase1_payments + total_phase2_payments + actual_gross_lump_sum
    total_interest_and_penalties = total_paid_to_bank - principal
    total_out_of_pocket = initial_downpayment + total_paid_to_bank
    
    crossover_df = df[df['Investment Portfolio'] >= df['Balance']]
    if not crossover_df.empty:
        crossover_month = crossover_df.iloc[0]['Month']
        crossover_text = f"Year {crossover_month // 12}, Month {crossover_month % 12}"
    else:
        crossover_text = "Does not cross during mortgage term."

    starting_normal_salary = df.loc[expat_months, 'Target Salary']
    total_saved_during_expat = expat_months * expat_monthly_savings
    
    # --- 6. PRINT COMPREHENSIVE SUMMARY ---
    print("\n" + "="*65)
    print("📊 COMPLETE MORTGAGE & WEALTH SIMULATION METRICS")
    print("="*65)
    print("\n🏠 1. INITIAL LOAN SETUP")
    print("-" * 65)
    print(f"House Price:             €{house_price:,.2f}")
    print(f"Purchasing Costs (4%):   €{purchasing_costs:,.2f}")
    print(f"Total Savings Used:      €{initial_downpayment:,.2f}")
    print(f"Initial Loan Principal:  €{principal:,.2f} (after fees)")
    print(f"Interest Rate:           {annual_rate}% fixed for {total_years} years")
    
    print("\n💼 2. PHASE 1: EXPAT LIFE")
    print("-" * 65)
    print(f"Duration:                {expat_years} years")
    print(f"Phase 1 Monthly Payment: €{m_initial:,.2f}")
    print(f"Total Savings Generated: €{total_saved_during_expat:,.2f} (€{expat_monthly_savings}/mo)")
    
    print("\n🔄 3. THE TRANSITION (MORTGAGE RECAST)")
    print("-" * 65)
    print(f"Target Phase 2 Payment:  €{target_phase2_payment:,.2f}")
    print(f"Lump Sum Paid to Bank:   €{actual_gross_lump_sum:,.2f} (taken from portfolio)")
    print(f"Bank Penalty (3mo int):  €{penalty:,.2f} (included in lump sum)")
    print(f"Loan Balance Drop:       €{old_balance_before_recast:,.2f} -> €{old_balance_before_recast - net_lump_sum:,.2f}")
    print(f"Remaining Liquid Buffer: €{portfolio_value:,.2f} (Kept invested!)")
    
    print("\n🏡 4. PHASE 2: NORMAL LIFE")
    print("-" * 65)
    print(f"Duration:                {total_years - expat_years} years")
    print(f"Phase 2 Monthly Payment: €{m_new:,.2f}")
    print(f"Salary upon Quitting:    €{starting_normal_salary:,.2f} net (with 4% growth)")
    print(f"Future Salary Burden:    {(m_new / starting_normal_salary) * 100:.1f}% of net income")
    
    print("\n💰 5. LIFETIME COSTS & WEALTH (AT YEAR 25)")
    print("-" * 65)
    print(f"Total Cash Out of Pocket:€{total_out_of_pocket:,.2f} (Includes downpayment & payments)")
    print(f"Bank's Total Profit:     €{total_interest_and_penalties:,.2f} (Total Interest + Penalty)")
    print(f"Liquid Crossover Date:   {crossover_text} (When investments > debt)")
    print(f"Final House Value:       €{df.iloc[-1]['House Value']:,.2f} (3% appreciation)")
    print(f"Final Portfolio Value:   €{df.iloc[-1]['Investment Portfolio']:,.2f} (7% return)")
    print(f"👉 FINAL NET WORTH:      €{df.iloc[-1]['Total Net Worth']:,.2f}")
    print("="*65 + "\n")

    # --- 7. DESIGNER VISUALIZATION ---
    c_networth = '#111827'   
    c_house = '#10B981'      
    c_portfolio = '#6366F1'  
    c_debt = '#EF4444'       
    c_bg = '#F9FAFB'         
    c_grid = '#E5E7EB'       
    
    # 📉 CHANGED THIS LINE: Now 12x7 to fit perfectly on a laptop screen
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 7), sharex=True)
    fig.patch.set_facecolor(c_bg)
    
    for ax in [ax1, ax2]:
        ax.set_facecolor(c_bg)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_visible(False)
        ax.spines['bottom'].set_color(c_grid)
        ax.grid(axis='y', color=c_grid, linestyle='--', linewidth=1, alpha=0.8)
        ax.tick_params(axis='both', which='both', length=0, labelsize=9, colors='#4B5563')

    # Plot 1: Payment Transition
    ax1.plot(df['Month'], df['Payment'], color=c_debt, linewidth=3, label='Monthly Mortgage Payment')
    ax1.fill_between(df['Month'], df['Payment'], color=c_debt, alpha=0.1)
    
    ax1.plot(df['Month'], df['Target Salary'] * 0.33, color=c_house, linestyle=':', linewidth=2, label='Max Recommended (33% of Salary)')
    ax1.axvline(x=expat_months, color='#9CA3AF', linestyle='--', linewidth=1.5, zorder=0)
    ax1.text(expat_months + 2, df['Payment'].max() * 0.9, '← Expat Job Recast', color='#6B7280', fontsize=9, fontweight='bold')
    
    ax1.set_title('Monthly Cash Flow Transition', fontsize=12, fontweight='bold', color=c_networth, loc='left', pad=10)
    ax1.legend(frameon=False, loc='upper right', fontsize=9)

    # Plot 2: Wealth Accumulation
    ax2.plot(df['Month'], df['Total Net Worth'], color=c_networth, linewidth=3.5, label='Total Net Worth')
    ax2.fill_between(df['Month'], df['Total Net Worth'], color=c_networth, alpha=0.05)
    
    ax2.plot(df['Month'], df['House Value'], color=c_house, linewidth=2, linestyle='-', alpha=0.8, label='Property Value')
    ax2.plot(df['Month'], df['Investment Portfolio'], color=c_portfolio, linewidth=2, linestyle='-', alpha=0.8, label='Liquid Portfolio')
    
    ax2.plot(df['Month'], df['Balance'], color=c_debt, linewidth=2, label='Remaining Debt')
    ax2.fill_between(df['Month'], df['Balance'], color=c_debt, alpha=0.1)

    ax2.axvline(x=expat_months, color='#9CA3AF', linestyle='--', linewidth=1.5, zorder=0)
    
    ax2.set_title('Total Net Worth Accumulation (Assets vs. Liabilities)', fontsize=12, fontweight='bold', color=c_networth, loc='left', pad=10)
    ax2.set_xlabel(f'Timeline ({total_years} Years)', fontsize=10, fontweight='bold', color='#4B5563', labelpad=8)
    
    ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, loc: f"€{int(x):,}"))
    ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, loc: f"€{int(x):,}"))
    
    ax2.legend(frameon=False, loc='upper left', fontsize=9, ncol=2)
    
    # 📉 CHANGED THIS LINE: Tighter layout padding to maximize space
    plt.tight_layout(pad=2.0)
    plt.show()

# Run the scenario
advanced_mortgage_sim()