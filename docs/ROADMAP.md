# Product direction

The current rebuild establishes a working foundation. It has not been benchmarked against commercial budgeting apps, and does not claim to outperform them.

## Delivered

- Separate personal workspaces, session authentication, and persistent storage.
- Manual transactions, cash/investment/debt accounts, and paired transfers.
- CSV inspection, explicit column/date/sign mapping, row review, atomic saving, and duplicate detection.
- Net worth, recorded cash balances, six-month income/spending history, expense categories, monthly budgets, and basic recurring-expense candidates.
- Responsive interface, no external fonts/scripts/chart service, and CSV/JSON exports.
- Automated integration checks and an optional real-browser workflow check.

## Next milestones

1. **Reliable reconciliation:** statement ending balances, discrepancy resolution, dated balance adjustments, import history/undo, pending-to-posted matching, institution-specific import profiles, OFX/QFX support.
2. **Flexible planning:** customizable categories, split transactions, categorization rules, recurring bills, sinking funds, rollover budgets, goals, and household sharing with explicit permissions.
3. **Investments and debt:** holdings/cost basis imports, valuation snapshots, fees and dividends, scenario-based debt planning, and clearly dated optional market-data sources.
4. **Public service readiness:** account recovery, MFA, invitations, password changes, deletion/export policies, schema migrations, audit history, production load tests, and a deployment security review.

## Boundaries

No bank passwords or browser scraping are used. A CSV workflow updates dynamically after each save but does not retrieve transactions automatically. Bank connectivity or a user-authorized export/sync arrangement would be a separate integration. Current reports use USD only. Investments are recorded account values; there are no live securities prices or portfolio-performance calculations.

Before calling the product better than another app, define and measure the target outcomes: import accuracy and coverage, reconciliation error rates, time to complete a weekly review, category correction rate, accessibility, recoverability, and the features its intended users actually need.
