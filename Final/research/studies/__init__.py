"""Every closed study as a tracked module with `NAME`, `DEPENDS`, `FILES` (declared outputs and their metadata)
and `run(ctx)`. `python -m research.run_all` runs them in this order and writes the result contract."""
from research.studies import (attribution, critical_tests, data_audit, diagnostics, fmp, longshort, optimization,
                              paper_targets, rank_buffer, replication)
from research.studies import mean_variance, professor_checks, feedback_costs, uk_comparison

REGISTRY = {m.NAME: m for m in [data_audit, replication, attribution, critical_tests, paper_targets, diagnostics, fmp, longshort,
                                 optimization, rank_buffer, mean_variance, professor_checks, feedback_costs, uk_comparison]}
