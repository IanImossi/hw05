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

## Part E — Relationships and design questions

The model is a star with three fact tables. "dim_client", "dim_advisor" and "dim_date" are conformed dimensions: one shared copy of each filters all three fact tables, so one slicer on client, advisor or date applies to fees, snapshots and transactions at once. "dim_security" filters only "fact_transactions", and "dim_benchmark" filters only "fact_portfolio_snapshot". All 11 fact-to-dimension relationships are Many to one with Single cross-filter direction. The two dimension-to-dimension relationships, "dim_client" → "dim_advisor" and "dim_security" → "dim_benchmark", were created but kept inactive; (b) and (d) explain why.

- (a) The reason some transaction rows have no "security_id" is because they count as either a deposit, withdrawal or an advisory fee. Since these transactions are cash moving into or out of an account, and not a trade in a stock or fund, there will be no security to point to. The null values are not defects and are there because there is no security required in the transaction.

- (b) The "advisor_id" relationships that were kept active were the three "fact" → "dim_advisor" relationships, while "dim_client" → "dim_advisor" remained inactive. The fact table's "advisor_id" records which advisor handled that specific fee, snapshot or transaction when it happened. "dim_client" only stores each client's advisor as one value with no history, so it would credit a client's whole past to whoever is listed there now. That matters here because 2,410 transactions are flagged "is_post_departure_txn", which shows advisors do leave. In the current data the two paths agree on every row, but the direct links stay correct if clients are reassigned later. They also keep the model a true star, and one advisor slicer filters all three facts directly.

- (c) The facts join on "dim_date[date]". The fact tables store calendar dates (fee_date, snapshot_date, txn_date), but not "date_id" numbers. "date_id" contains row numbers from 1 to 1,827 that no fact table contains. If it were joined, it would match nothing or incorrect data. However, "dim_date[date]" is unique, has every fact date from 2020-01-01 to 2024-12-31, and is the column used to mark "dim_date" as the date table.

- (d) There are two links in the data that connect one dimension to another: "dim_client[advisor_id]" → "dim_advisor" and "dim_security[benchmark_id]" → "dim_benchmark". Using either as an active relationship would make the model a snowflake. I kept both relationships in the model, but as inactive relationships, which keeps the model a star. The advisor link is explained in (b). The benchmark link is inactive because the two benchmarks mean different things. A snapshot's "benchmark_id" is the index that client's whole portfolio is measured against, and only IDs 1, 3 and 8 appear. A security's "benchmark_id" is the index for that one security's asset class, and IDs 1, 2, 3, 4, 5 and 7 appear. If both remained active, the benchmark slicer would filter snapshots by portfolio benchmark and transactions by security benchmark at the same time, and the results would be easy to misread. If an analysis needs securities grouped by benchmark, a DAX measure can turn the link on with USERELATIONSHIP.


## Part F — Reflection
### Fees
- How much fee revenue did each advisor bring in each year, broken down by fee type?
- This can be answered without a DAX workaround. Since fee amount is additive, the table will have: "dim_advisor[advisor_id]" on rows (not "last_name", because advisors 1 and 5 are both Johnson and would be combined), "dim_date[year]" and "fact_fees[fee_type]" on columns, and Sum of amount as the value gives the right totals at every level. 
### Portfolio Snapshot
- What was each advisor’s AUM at the end of each year, and did their clients beat the benchmark?
- This cannot be answered without a DAX workaround because AUM is semi-additive. Putting the year on the axis and Sum of AUM as the value adds up all twelve monthly balances instead of just the last month. For 2024 that shows about $135.5 billion, when the firm actually managed about $12.7 billion in December 2024. A DAX measure is needed to pick only the last month of each period. The benchmark half of the question has the same problem: "return_ytd" and "active_alpha_ytd" are percentages, so they cannot be summed, and a plain average treats a $1,000 account the same as an $80 million one. Comparing clients with the benchmark needs an AUM-weighted average, which also needs DAX. To fix this, each snapshot should be dated at the month's end (snapshots are dated the 1st, so the "is_month_end" and "is_year_end" flags in "dim_date" never match them), and returns should also be stored as dollar amounts (investment gain and beginning AUM), which are additive, so a weighted return becomes a simple sum divided by a sum.
### Transactions
- What was each advisor’s net new money (deposits minus withdrawals) each quarter?
- This question cannot be answered without a DAX workaround. This is because every amount is stored as a positive number, and whether money came in or went out is only shown by the text in "txn_type". This will cause withdrawals to be added to the total as well, when they should be subtracted. This can be fixed by adding signs to each amount whether they are deposited or withdrawn. After this change, then they can be added normally.