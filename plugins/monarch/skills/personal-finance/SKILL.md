---
name: personal-finance
description: >
  Domain knowledge for interpreting personal finance data from Monarch Money.
  Covers net worth trends, cash flow analysis, budget variance interpretation,
  savings rate benchmarks, and transaction pattern recognition. Use this skill
  whenever presenting financial data, answering questions about spending, budgets,
  net worth, savings, cash flow, or any Monarch Money output. Also use it when
  the user asks about their financial health, spending patterns, or wants to
  understand what their numbers mean — even if they don't mention "finance"
  explicitly.
user-invocable: false
allowed-tools: [Read]
---

# Personal Finance — Interpretation Patterns

<objective>
Provide vocabulary and interpretation frameworks so the monarch agent presents
financial data with meaningful context, not just raw numbers. The goal is to
help the user understand what their data means without prescribing what to do
about it.
</objective>

<concepts>

## Net Worth

Net worth = total assets minus total liabilities. It's the single broadest
measure of financial position, but context matters more than the number itself.

- **Liquid net worth** is cash and cash equivalents (checking, savings, money
  market) minus short-term liabilities (credit cards). More useful for day-to-day
  financial health than total net worth because it reflects what's actually
  available.
- **Trend matters more than snapshot.** A single net worth number is less
  meaningful than the direction over time. Frame it as "up $X from last month"
  or "down $X over three months" when the data supports it.
- **Asset categories:** liquid (checking/savings), invested (brokerage/retirement),
  real (property), other.
- **Liability categories:** revolving (credit cards), installment (auto/personal
  loans), mortgage.

## Cash Flow

Cash flow shows the rhythm of money in and out. It's the best indicator of
whether someone is building wealth or eroding it.

- **Net cash flow** = income minus expenses for a period. Positive means
  accumulating. Negative means drawing down.
- **Savings rate** = (income - expenses) / income * 100. This is the single
  most important health metric to surface.
  - Below 10%: Fragile. One unexpected expense causes debt.
  - 10-20%: Baseline healthy.
  - 20-30%: Strong. Building wealth.
  - Above 30%: Aggressive accumulation.
- **Irregular income:** For variable income, use 3-month rolling average, not
  single-month snapshots. A single good or bad month is noise.
- **Seasonal patterns:** Holiday spending (Nov-Dec), tax refunds (Feb-Apr),
  insurance renewals, and annual subscriptions create predictable variance.
  Don't flag these as anomalies unless they deviate from the user's own history.

## Budget Variance

Budget variance tells the story of intention vs reality. The interesting part
isn't whether someone is over or under — it's the pattern and severity.

- **Under budget:** Good if intentional, concerning if it means deferred
  necessary expenses (skipping maintenance, medical, etc.).
- **Over budget severity:**
  - 1-10% over: Minor. Normal variance. Don't alarm the user.
  - 10-25% over: Notable. Worth mentioning.
  - 25%+ over: Significant. Needs attention.
- **Zero-spend categories:** A budgeted category with zero spend might mean
  the budget is stale, not that spending is controlled. Call this out.
- **Percentage of total:** Show each category's share of total spending. Large
  categories (housing, food, transport) deserve more attention than small ones.

## Transaction Patterns

Transactions are the raw material. The value is in the patterns, not individual
line items.

- **Recurring vs one-time:** Recurring expenses are the baseline. One-time
  expenses are noise unless they're large (relative to monthly income).
- **Merchant clustering:** Multiple charges to the same merchant in a short
  period may indicate subscriptions, installment payments, or fraud. Flag it.
- **Category accuracy:** Monarch auto-categorizes. Miscategorized transactions
  skew budget and cash flow data. If a large transaction seems miscategorized
  based on the merchant name, mention it.

## Interpretation Guidelines

These principles apply to all financial data presentation:

1. **Lead with what matters.** "You're spending 40% of income on housing" is
   more useful than listing every transaction.
2. **Compare to prior periods.** "Dining out is up 30% vs last month" gives
   context that "$450 on dining" alone doesn't.
3. **Don't moralize.** Present data and patterns. The user decides what to do
   about it. No "you should spend less on X" language.
4. **Flag anomalies:** Unusual amounts, new merchants, category spikes, sudden
   changes in recurring charges.
5. **Distinguish structural from discretionary.** Structural = recurring,
   contractual (rent, insurance, subscriptions). Discretionary = variable,
   optional (dining, shopping, entertainment). This distinction helps the user
   understand what they can actually change.

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
