---
name: personal-finance
description: >
  Domain knowledge for interpreting personal finance data from Monarch Money.
  Covers net worth, cash flow analysis, budget variance, and savings rate.
  Interpretation patterns only. Not investment advice.
user-invocable: false
allowed-tools: [Read]
---

# Personal Finance — Interpretation Patterns

<objective>
Provide vocabulary and interpretation frameworks for personal finance data.
This skill helps the monarch agent present financial data with meaningful
context, not just raw numbers.
</objective>

<concepts>

## Net Worth
- **Definition**: Total assets minus total liabilities.
- **Liquid net worth**: Cash and cash equivalents (checking, savings, money market) minus short-term liabilities (credit cards). More useful for day-to-day financial health than total net worth.
- **Trend matters more than snapshot**: A single net worth number is less meaningful than the direction over time.
- **Asset categories**: Liquid (checking/savings), invested (brokerage/retirement), real (property), other.
- **Liability categories**: Revolving (credit cards), installment (auto/personal loans), mortgage.

## Cash Flow
- **Net cash flow**: Income minus expenses for a period. Positive = accumulating. Negative = drawing down.
- **Savings rate**: (Income - Expenses) / Income * 100. A key health metric.
  - Below 10%: Fragile. One unexpected expense causes debt.
  - 10-20%: Baseline healthy.
  - 20-30%: Strong. Building wealth.
  - Above 30%: Aggressive accumulation.
- **Irregular income**: For variable income, use 3-month rolling average, not single-month snapshots.
- **Seasonal patterns**: Holiday spending (Nov-Dec), tax refunds (Feb-Apr), insurance renewals, and annual subscriptions create predictable variance. Don't flag these as anomalies.

## Budget Variance
- **Under budget**: Spent less than planned. Good if intentional, concerning if it means deferred necessary expenses.
- **Over budget**: Spent more than planned. Flag severity:
  - 1-10% over: Minor. Normal variance.
  - 10-25% over: Notable. Worth reviewing.
  - 25%+ over: Significant. Needs attention.
- **Zero-spend categories**: A budgeted category with zero spend might mean the budget is stale, not that spending is controlled.
- **Percentage of total**: Show each category's share of total spending. Large categories deserve more attention.

## Transaction Patterns
- **Recurring vs one-time**: Recurring expenses are the baseline. One-time expenses are noise unless they're large.
- **Merchant clustering**: Multiple charges to the same merchant in a short period may indicate subscriptions, installment payments, or fraud.
- **Category accuracy**: Monarch auto-categorizes. Miscategorized transactions skew budget and cash flow data. Flag if a large transaction seems miscategorized.

## Interpretation Guidelines
- Lead with what matters: "You're spending 40% of income on housing" is more useful than listing every transaction.
- Compare to prior periods: "Dining out is up 30% vs last month" gives context that "$450 on dining" alone doesn't.
- Don't moralize. Present data and patterns. The user decides what to do about it.
- Flag anomalies: unusual amounts, new merchants, category spikes.
- Distinguish between structural (recurring, contractual) and discretionary (variable, optional) spending.

</concepts>

<boundaries>
## What This Skill Does NOT Cover
- Investment advice, asset allocation, or portfolio optimization
- Tax planning or tax optimization strategies
- Insurance adequacy or recommendations
- Debt payoff strategy recommendations (present the data, don't prescribe)
- Financial product recommendations
- Projections or forecasting (only present historical data)
</boundaries>
