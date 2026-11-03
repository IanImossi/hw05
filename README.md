# Structure
- "powerbi" folder: contains the power bi file with a model for the relationships of the files in "Wildcat Capital Clean" and a screenshot with those relationships
- "Wildcat Capital Clean" folder: contains the files to be checked
- "check_star_schema": python script to check the row counts, primary keys, foreign keys and grains of csv files within "Wildcat Capital Clean"
- "star_design": contains the answers to Parts A, B, C, E, and F
# How to Use
- Put in all nessecary folders within "Wildcat Capital Clean
- Install the dependencies: "pip install -r requirements.txt" in the terminal
- From the hw05 folder, run `python check_star_schema.py` to check the row counts, primary keys, foreign keys and grains of csv files within "Wildcat Capital Clean"

# Claude Code Findings
- Issues found
1. The `fact_transactions` grain check repeated the primary-key check. Its grain is `txn_id`, which check 2 already proves unique, so it did not show why a smaller grain fails.
   - Now check 6 now also proves `client_id` + `txn_date` is not unique (12,804 repeated rows), which is why the grain must be the single event.
2. Some claims in `star_design.md` Part E were not proven by the script.** These were checked by hand only: fact `advisor_id` equals the client's advisor, 2,410 post-departure transactions, and the different benchmark sets.
   - New check 7 proves all three. Each fact table's `advisor_id` matches `dim_client` on every row, exactly 2,410 rows are flagged `is_post_departure_txn`, and snapshots use benchmarks 1, 3 and 8 while securities use 1, 2, 3, 4, 5 and 7.
3. The "calendar dates, not date_id" check was weak. It only proved the values were not plain numbers.
   - Check 5 now parses every fact date as `YYYY-MM-DD`, confirms all of them match `dim_date[date]`, and confirms none match a `date_id`.
4. 'dim_date` coverage was not checked.
   - Check 5 now confirms `dim_date` has exactly one row per day from 2020-01-01 to 2024-12-31 (1,827 days), with no gaps or duplicates.
5. The pandas dependency was not listed anywhere.
   - Added `requirements.txt` and the install step under How to Use.
6. `security_id` loaded as a decimal (because of the blanks), so the foreign-key match compared 45.0 with 45.
   - All key columns now load as nullable whole numbers (`Int64`), matching the Whole Number type used in Power BI.
