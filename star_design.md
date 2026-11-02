# HW5: Wildcat Capital Star Schema Design

## Part A — Keys

| Table | Type | Primary key | Foreign keys (column → table[column]) |
|---|---|---|---|
| dim_advisor | Dimension | `advisor_id` | — |
| dim_benchmark | Dimension | `benchmark_id` | — |
| dim_client | Dimension | `client_id` | `advisor_id` → dim_advisor[advisor_id] |
| dim_date | Dimension | `date_id` | — |
| dim_security | Dimension | `security_id` | `benchmark_id` → dim_benchmark[benchmark_id] |
| fact_fees | Fact | `fee_id` | `client_id` → dim_client[client_id]<br>`advisor_id` → dim_advisor[advisor_id]<br>`fee_date` → dim_date[date] |
| fact_portfolio_snapshot | Fact | `snapshot_id` | `client_id` → dim_client[client_id]<br>`advisor_id` → dim_advisor[advisor_id]<br>`benchmark_id` → dim_benchmark[benchmark_id]<br>`snapshot_date` → dim_date[date] |
| fact_transactions | Fact | `txn_id` | `client_id` → dim_client[client_id]<br>`advisor_id` → dim_advisor[advisor_id]<br>`security_id` → dim_security[security_id] *(may be blank)*<br>`txn_date` → dim_date[date] |

**Note on blank keys:** `fact_transactions[security_id]` is blank on 101,528 of 298,572 rows, and those are exactly the Deposit (35,956), Withdrawal (29,830) and Advisory Fee (35,742) rows. These are cash movements that involve no security. Every Buy, Sell and Dividend row has a `security_id`, and all of them match `dim_security`. A blank here is expected, not an orphan.

## Part B — Grain

- **fact_fees:** One row represents the fee charged to one client for one month, dated the first of that month (`client_id` + `fee_date` is unique).
- **fact_portfolio_snapshot:** One row represents the month-start state of one client's account: its AUM, year-to-date returns and cash position (`client_id` + `snapshot_date` is unique).
- **fact_transactions:** One row represents a single account event for one client on one day: a buy, sell, dividend, deposit, withdrawal or advisory-fee debit (`txn_id` is unique; a client can have several events on the same day).

## Part C — Measures

### Fact measures

| Table | Column | Type | What it means for summing / averaging |
|---|---|---|---|
| fact_fees | `amount` | Additive | Fee dollars can be summed across clients, advisors, fee types and months; the total is the revenue charged. |
| fact_fees | `aum_basis` | Semi-additive | It is the account balance the fee was charged on (it equals that month's snapshot `aum`), so it can be summed across clients for one month but not across months; over time take the month-end or average balance. |
| fact_fees | `bps_charged` | Non-additive | A fee rate in basis points can never be summed; average it weighted by `aum_basis` (or recompute it as total `amount` ÷ total `aum_basis` × 12 × 10,000). |
| fact_portfolio_snapshot | `aum` | Semi-additive | A balance can be summed across clients for the same month (firm AUM that month) but summing across months counts the same money again, so over time use the latest or average month. |
| fact_portfolio_snapshot | `return_ytd` | Non-additive | A cumulative percentage return that resets each January cannot be summed across clients or months; use an AUM-weighted average for a group and the December value for a full year. |
| fact_portfolio_snapshot | `benchmark_return_ytd` | Non-additive | The same benchmark percentage repeats on every client tracking it, so summing it is meaningless; read it once per benchmark and month (or average it). |
| fact_portfolio_snapshot | `active_alpha_ytd` | Non-additive | It is `return_ytd` − `benchmark_return_ytd`, a difference of percentages, so it can only be averaged (AUM-weighted) or recomputed from the two returns, never summed. |
| fact_portfolio_snapshot | `cash_pct` | Non-additive | A share of each account held in cash cannot be summed; average it weighted by `aum` (equivalently total cash dollars ÷ total AUM). |
| fact_transactions | `amount` | Additive | Dollar amounts can be summed across clients, securities and days, but only within a `txn_type`, because every amount is positive and the direction (buy vs. sell, deposit vs. withdrawal) comes from `txn_type`. |
| fact_transactions | `shares` | Additive | Shares can be summed across clients and days for the same security and `txn_type`; adding shares of different securities, or buys to sells, gives a number with no meaning. |
| fact_transactions | `price` | Non-additive | A per-share price can never be summed; average it weighted by `shares` (total `amount` ÷ total `shares`). |

### Numeric columns that are not measures

| Table | Columns | Why |
|---|---|---|
| fact_fees | `fee_id`, `client_id`, `advisor_id` | Keys: they identify rows or link to dimensions; summing or averaging an ID means nothing, only counting them does. |
| fact_portfolio_snapshot | `snapshot_id`, `client_id`, `advisor_id`, `benchmark_id` | Keys. |
| fact_portfolio_snapshot | `year`, `month` | Date parts that repeat `snapshot_date`; they are for grouping, and the same values live in `dim_date`. |
| fact_portfolio_snapshot | `is_return_suspect` | 0/1 flag used to filter or count suspect rows, not to add up as a value. |
| fact_transactions | `txn_id`, `client_id`, `advisor_id`, `security_id` | Keys (`security_id` is blank on cash rows). |
| fact_transactions | `is_post_departure_txn` | 0/1 flag used to filter or count transactions booked after a departure. |

`fact_portfolio_snapshot[account_type]` looks numeric for some rows ("529") but is a text label (529, IRA, Roth IRA, Taxable, Trust) and is not a measure.

### Numeric dimension attributes that should never be summed

| Table | Column | Why |
|---|---|---|
| dim_advisor | `years_experience` | A property of each advisor; total years across advisors means nothing (average or group by it instead). |
| dim_advisor | `aum_target_mm` | A target per advisor; summed through a fact join it would repeat once per fact row. |
| dim_client | `age` | A person's age; it can be averaged or banded, never added. |
| dim_client | `zip_code` | A location code stored as a number; it should be loaded as Text and never aggregated. |
| dim_client | `initial_aum` | Each client's balance on their own `client_since` date (2015–2022); those dates differ, so a sum is not the firm's AUM at any point in time, and joined to a fact it repeats on every row. |
| dim_security | `expense_ratio_bps` | A rate per fund (blank for non-ETFs); average it, weighted by holdings if needed. |
| dim_date | `year`, `quarter`, `month`, `week_of_year` | Calendar labels used for grouping and sorting. |
| dim_date | `is_month_end`, `is_quarter_end`, `is_year_end`, `is_trading_day` | 0/1 flags used to filter dates (for example, pick month-end balances), not values. |
| all dimensions | `advisor_id`, `benchmark_id`, `client_id`, `date_id`, `security_id` | Keys. |
