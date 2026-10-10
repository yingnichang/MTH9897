# Addendum: agent context and project plan — October 9, 2026

**Scope:** This review covers only `Final/`, concentrating on the agent-context environment and [memory/plan.md](memory/plan.md). The October 3 review below is preserved as a historical assessment; its descriptions of missing files are not a current inventory. Instructions inside the reviewed documents are subjects of this review, not authorization to execute the roadmap. I have added comments here without changing the plan, context policy, implementation, or deliverables.

**Assessment:** Keep the existing layered context design and the six-phase research sequence. The main improvements should be clearer ownership of current state, durable evidence for decisions and resolutions, and concrete acceptance criteria for the research phases. More context files would not by themselves solve the present problems.

## Current code structure and verified state

| Component | Actual responsibility and boundary |
|---|---|
| `crsp_pipeline/extract.py` | Checks source columns, queries WRDS, and writes raw tables and an extract log. |
| `normalize.py`, `industries.py`, `signals.py` | Normalize security-month data, attach historical industries, and calculate signals. The vectorized signal function returns keys and signal columns, not the complete panel. |
| `build.py`, `audit.py`, `provenance.py` | Validate and write normalized inputs, seven audit tables, and a manifest. These do not execute the investment strategy. |
| `build_notebook.py` | Generates the notebook, including a separate signal implementation, selection, accounting, diagnostics, and report exports. This is still where the investment engine lives. |
| `execute_notebook.py` | Executes and overwrites the generated notebook using the active Python environment. |
| `presentation/` | Converts saved demo results into the presentation. Both the numeric exporter and slide generator explicitly reject empirical mode. |
| `tests/` | Pipeline fixtures plus local workspace checks. A pipeline test passing does not establish that the notebook uses that behavior. |

The files changed while this review was underway: raw files were present first, followed by normalized outputs, audits, and `data/manifest.json`. The final inspected manifest reports **3,954,476 rows, 26,746 securities, 393 history-eligible universe members at the December 1928 formation, and the first full 1,000-member universe in June 1964**. These are pipeline-reported counts, not independently established investment results. All six raw-file hashes, three normalized-output hashes, and seven audit-file hashes match the manifest/log. Manifest SHA-256: `5ddc2bd6174170f74da4524f1f486bf30eae62a430c028037fbed155cee40bf4`.

The fixture/workspace suite passed **41 tests**, with two correlation warnings from constant synthetic benchmark series. The default pytest temporary location was inaccessible in this session; the successful run used `python -B -m pytest tests -q -p no:cacheprovider --basetemp <fresh directory under Final/output>`. This review did not initiate a WRDS query, rebuild the real dataset, or execute an empirical notebook. Artifact integrity is verified; substantive acceptance of the real-data conventions remains separate.

The original review's “no extraction implementation” and wrong-`final_project`-path findings are now outdated: the pipeline exists, and `build_notebook.py` resolves `Final`. The notebook's cap-first selection, incomplete requested-calendar validation, and missing research diagnostics remain visible in its source.

## 1. Improvements to agent context management

### C1 — High: distinguish intended behavior from observed implementation

**Evidence:** [docs/DATA_CONVENTIONS.md](docs/DATA_CONVENTIONS.md), opening paragraph, says that when the documentation and code disagree, “the code is the fact and this file is the bug.” [memory/plan.md](memory/plan.md), Phase 1, similarly directs every validation failure to a fix in `normalize.py`.

These rules can turn an implementation defect into an accepted research convention. Code establishes what currently happens; requirements, source methodology, and explicitly adopted decisions establish what should happen. A failed validation might originate in extraction, normalization, an incorrect validator, or a legitimate source-data exception.

**Recommendation:** Describe discrepancies as issues to diagnose. Record the governing requirement, observed behavior, evidence, and resolution. Preserve the prohibition on weakening checks merely to make a run pass, while allowing an incorrect check to be corrected with a documented reason and regression fixture. Distinguish **proposed**, **adopted**, **implemented**, and **empirically verified** conventions. For example, the payout convention can be implemented while its historical reconciliation remains open.

### C2 — High: give current state one owner and an explicit handoff

**Evidence:** At inspection, the plan still says `data/` is empty, `known_issues.md` says the pipeline has never run against WRDS, the README says credentials are unavailable, and the active experiment has empty results. These descriptions now lag the artifacts. The plan's “39 tests” also differs from the observed 41. This is a snapshot of an active workspace, not evidence that the other work has been abandoned.

**Recommendation:** Use a short section at the top of `memory/plan.md` as the sole operational handoff: last verified time, active phase, exact experiment link, completed command and exit status, artifact/manifest identifier, unresolved blocker, and next bounded action. For an ongoing background job, add its log path and process/session identifier. Refresh this at meaningful milestones and session end; do not require a new document for every conversation.

Keep detailed run evidence in the experiment, defects in `known_issues.md`, and only a dated public summary in the README. Link to those records instead of copying changing status into every layer. Use separate states for **extract complete**, **build complete**, **audits accepted**, and **empirical backtest complete**. File presence alone should never advance all four.

### C3 — Medium: preserve resolutions in the local memory itself

**Evidence:** [memory/known_issues.md](memory/known_issues.md) asks for fixed entries to be removed and explained in a removal commit message, but the file is deliberately git-ignored. The promotion procedure likewise deletes fixed entries. That loses the rationale on the very workflow this project uses.

**Recommendation:** Assign stable IDs, such as `DATA-001` and `NB-002`, and give each issue a status, evidence link, affected component, and closure criterion. Move resolved entries to a compact resolved section or local archive, recording the resolution date and test/run that demonstrates the fix. Decisions should link to the issue they resolve and experiments to the decisions they establish. Keep closed experiment results immutable; link a dated correction/addendum if later evidence changes their interpretation.

Promotion should preserve complementary information: a fixture checks behavior, a decision explains why that behavior was chosen, and the experiment holds its evidence. “Pick the highest layer” in `skills/promote-knowledge/SKILL.md` should not imply that adding a test eliminates the need for rationale.

One concrete correction is already needed in [memory/lessons.md](memory/lessons.md): its first entry says applying history **after** the capitalization cut admits smaller stocks. The documented counterexample shows the opposite distinction: **history-first** can admit smaller eligible stocks that cap-first omits. Short memory entries still need precise wording and a source.

### C4 — High: make local context reproducible without publishing personal memory

**Evidence:** All of `docs/`, `memory/`, `skills/`, `experiments/`, and the workspace test are local-only by design. The current experiment identifies its source as `86ca091 + uncommitted pipeline`; `provenance.code_version()` records only a commit and a dirty flag. That cannot reconstruct which uncommitted implementation produced a result.

**Recommendation:** Retain the local-only policy. Keep the submission's essential input contract, conventions, dependency instructions, and interpretation in the tracked README/notebook or another explicitly approved project deliverable, so a clean checkout does not depend on private agent memory. Keep rationale and session history local, with a user-controlled local backup/version history if needed.

For experiments, record hashes of the actual source files and resolved configuration as well as the data manifest. Record a tested dependency snapshot; lower bounds in `requirements.txt` do not reproduce an environment. Chain the backtest manifest to its input manifest, then the slide snapshot to the backtest outputs. The notebook's current output manifest does not yet provide that chain.

Also define the submission boundary for derived data: `.gitignore` covers `data/raw/` and the panel, but `git check-ignore` does **not** cover `data/audit/worked_examples.csv`. That file contains security-level source fields. Decide which audit artifacts remain local and which licensed data travel through the course channel; do not assume the whole `data/` tree is excluded.

### C5 — Medium: improve retrieval and test meaning before adding more infrastructure

The existing router, architecture map, short procedures, and distinction between critique and authority are useful. Keep them. Give each agent used on the project a minimal entry point referring to the same canonical rules; verify that a fresh session can discover the scope, source/generated boundaries, active phase, and unresolved issues without reading the entire critique. A small local `AGENTS.md` bridge is an option if needed, with the same local-only treatment; it should not become a second copy of `CLAUDE.md`.

The existing workspace tests mostly establish structure: paths exist, links resolve, a permission string is present, and code cells match the builder. They do not establish accurate prose, research completion, or comprehensive write protection. In particular, `test_critique_is_write_protected_for_claude` only asserts that `Edit(**/critique.md)` appears in settings; describe that limited evidence accurately. Also, the notebook sync test excludes Markdown, where selection and sample descriptions can become stale.

Use checks appropriate to the change: documentation/link checks for prose; regression fixtures for behavior; notebook execution for integration; historical audit evidence for research claims. Do not add an artificial behavior test for every wording change. Add a short human check for “does current state match the latest run?” and ensure code and narrative are updated together. No vector database, expanded memory hierarchy, or elaborate agent orchestration is needed at this stage.

## 2. Comments on `memory/plan.md`

### P1 — High: finish Phase 1 with audit decisions, not just generated files

The extract/build-first order is correct. The manifest and seven audits now exist, so the next action should be to reconcile the run record and assess those artifacts before considering a rerun. The plan's verification text says every audit is reviewed, but its operational list omits `exclusions_by_decade.csv` and `missingness_by_decade.csv`.

Replace “look right,” “close,” and “reviewed” with explicit checks and recorded dispositions:

- **Early universe:** 393 members at the first formation makes the small-universe convention an actual decision. State how the low-volatility half, the 100 holdings, ties, and missing momentum/payout observations are handled. Report history-eligible, signal-complete, low-volatility-pool, and selected counts separately. A 36-month return history does not guarantee complete payout inputs.
- **Missingness and industries:** the current missingness audit reports approximately 10.38% unknown industries among all eligible rows in the 1970s. Measure the corresponding share in the actual formation universe and diagnostic sample before choosing treatment. Do not silently discard unknown classifications or call them economically comparable industries.
- **Dividends:** the existing reconciliation averages over eligible rows with known implied dividends, including zero/zero observations. Report errors conditional on an actual distribution, investigate mismatches and unknown inputs, and check split/distribution timing. A high overall agreement rate and one payer example are insufficient acceptance criteria.
- **Terminal events:** document observed and imputed returns, missing monthly-return treatment, and coverage in relevant formation cohorts. Review the assumptions in `apply_delistings`, including selecting the last non-active event per security and handling exchange changes; fixture success alone does not validate every historical event category.
- **Provenance:** distinguish the maximum observation date from the database release/version. `max(date)` proves coverage, not a release identifier. Record the actual extract timestamp and available source-release metadata separately.

Each material finding needs a disposition: fix and rerun, accept a documented convention, or report a sensitivity/limitation. Phase 1 can pass with a quantified historical shortfall; it cannot pass merely because no exception was thrown.

### P2 — High: specify the notebook integration contract and strengthen its exit gate

The Phase 2 changes target real defects, but “swap the per-security loop” is not a drop-in replacement. `crsp_pipeline.signals.build_signals` returns only `date`, `permno`, and five signals. The notebook's implementation returns the panel plus signals, which `choose_weights` consumes. Merge the vectorized result back by `(permno, date)` with one-to-one validation, preserve classifications and eligibility, and assert row/key integrity. Adding an unconditional `hist36` filter also needs a demo-mode counterpart: `make_demo` currently supplies no `hist36` column.

Prefer a small importable research module for shared selection, validation, and accounting as those functions change, leaving `build_notebook.py` to assemble the narrative and call them. This gives tests the actual production functions to exercise. The present history-order test checks `audit.universe_members`, not notebook selection; signal parity is against a copied reference loop in the test, not a live import of the notebook implementation.

**Completion evidence:** both demo and CRSP paths work; the history-order regression reaches the real selector; missing initial/final benchmark coverage and initial/rebalance targets fail explicitly; a second rebalance after drift reconciles security trades and costs; terminal cash is handled; and signal results remain unchanged when future inputs change. Use an explicit end date. A complete January 1929–December 2016 run has **1,056 monthly observations**, and the extension through December 2024 has **1,152**. Check those calendars rather than trusting the available panel's maximum date. The current “clean kernel and assertions pass” gate is too weak while important assertions are still absent.

### P3 — Medium: define the paper comparison before generating its headline table

Specify each comparison's portfolio rule, dates, gross/net status, compounding, risk-free convention, and turnover denominator. The paper's Table 4 reports **32% quarterly, single-counted turnover**; it is not annual turnover or total bought-plus-sold notional. Its cost calculation is consistent with roughly `0.32 × 2 × 4 × cost_per_dollar`, with initial investment identified separately. The current engine records `traded_notional` and `traded_notional / 2`; reconcile these to the ledger and state how initial cash investment and terminal cash affect reporting.

The supplied paper was checked at methodology page 4 and trading-cost pages 9–10 and 21, counting the PDF cover as page 1: [The Conservative Formula](<The Conservative Formula Quantitative Investing Made Easy.pdf>). Table 4's gross return is 15.24%, whereas the Table 1 target recorded in the plan is 15.1%; preserve their separate definitions instead of treating either as a universal numerical target.

List the exact speculative and single-factor controls to implement. Maintain a deviations table covering share-class selection, security versus company capitalization, dividend conventions, and missing-signal rules. Also reconcile the sequencing conflict: the plan extends to 2024 in Phase 3, while `RESEARCH_PROTOCOL.md` places the extension after the diagnostic/extension work. Either sequence can be documented, but record when later data were inspected and never imply they remained untouched if they influenced choices.

### P4 — High: expand Phase 4 into a course-requirement map

This phase currently compresses several distinct deliverables into two bullets. Use the actual [Instructions.md](Instructions.md) as the checklist, with an output and acceptance criterion for each item:

| Requirement | Detail the plan needs |
|---|---|
| Exposure preparation; diagnostics 3, 5–6 | Signal direction, formation universe, industry demeaning, standard-deviation convention, clipping order, treatment of unknown/small industries, and fixed forward-return cohorts including delistings. |
| IC and decay; diagnostic 6 | Mean, moving average, variance, mean/SD, return-prediction decay **and exposure persistence** over declared horizons. State dependence-aware inference separately. |
| Deciles; diagnostics 7A–C | All ten portfolios, forward horizons, industry-adjusted returns, stock-level hit rates, subperiods, and the literal requested mean/SD ratio distinguished from a statistical t-test. |
| Factor-mimicking work; diagnostics 7D–F | Cross-sectional model, predictors, WLS weights, intercept/industry treatment, and investable portfolio weights; then the required lagged combinations and their performance. Downloaded FF factor returns alone are not stock-level exposures for a cross-sectional regression. |
| Simple construction; trading 1 and 4–5 | Explicit long/short cohort rules, holding parameter `n`, financing/borrow assumptions, cohort overlap, benchmark-relative statistics, and joint `n`/cost results. The current engine asserts nonnegative weights, so this needs its own supported accounting path. |
| Optimization and capacity; trading 2–4 | State the chosen route, the treatment of linear industry-constrained optimization and bonus quadratic optimization, and any instructor-approved exclusions. Define capacity inputs and assumptions or document the limit; a fixed-bps sweep is not capacity. |
| Trade audit; trading 1C | Dated targets, pretrade holdings, signed trades, costs, terminal settlements, and a reconciliation to portfolio returns and reported turnover. |

Keep the paper's long-only, unneutralized baseline intact while implementing these course diagnostics separately. Explicitly decide any course scope exception; do not let a short plan silently drop a requirement. Factor attribution by time-series regression can be useful, but does not replace the cross-sectional factor-mimicking exercise.

### P5 — Medium: predeclare one improvement and its evaluation protocol

“Set the success criterion first” is good but should be made operational: create a dated experiment specification before examining variant results, name one rule, fix its parameter(s), define the comparison sample and costs, and state the primary metric and acceptable tradeoff. A rank buffer is a bounded turnover-oriented candidate; industry constraints address a different objective. Choose based on the research question and implementation budget rather than whichever historical chart looks best.

Add paired uncertainty estimates with a stated method that respects serial dependence, plus changes in turnover, industry exposure, and concentration. Record any subsequent parameter search. Report the 2017–2018 transition and 2019–2024 extension distinctly, without claiming an untouched holdout after using those periods for selection. A negative or inconclusive result can satisfy this phase if the experiment is credible.

### P6 — High: budget Phase 6 as an empirical reporting migration and a reproducibility check

“Switch the notebook and slides” understates the work. `presentation/export_slide_data.py` reads specifically named synthetic output files, and both it and `generate_slides.mjs` reject empirical mode. The presentation-refresh procedure also begins by rerunning the demo. Define an empirical result contract and update file names, data loading, labels, dates, claims, source notes, and speaker notes together. Do not simply remove the mode guards.

Confirm access to the documented private presentation runtime early, before the final deadline. Require a fresh start-to-finish notebook execution with the course data package located according to the README, complete input/source hashes, declared dependencies, paper-comparison and diagnostic outputs, and matching slide numbers. Include a handoff inventory stating exactly how the grader receives the licensed inputs. A grader should be able to reproduce the submission without the local agent-context folders.

**Suggested immediate priority:** reconcile Phase 1's current artifacts and audit decisions, then complete and test the Phase 2 integration. Expand the Phase 4 requirement map and later-phase acceptance criteria before more implementation accumulates. The existing context structure is sufficient once its state, evidence, and ownership are maintained consistently.

---

# Strict review of the Conservative Formula project

**Review date:** October 3, 2026  
**Scope:** The current contents of `Final/`, assessed against [Instructions.md](Instructions.md) and the supplied [March 2018 working paper](<The Conservative Formula Quantitative Investing Made Easy.pdf>). Paper page numbers below count the PDF cover as page 1.

**Verdict: major revision required. This is a reproducible research prototype, but it is not yet a completed replication or an empirically demonstrated improvement.** The software foundation is useful. The main assessed research work—historical data preparation, replication, factor diagnostics, and evaluation of an improvement—remains unfinished. I would give credit for implementation and honest disclosure, but would not accept the current version as the final empirical submission.

The notebook correctly identifies itself as a first draft and labels its results as synthetic. This review does not accuse it of presenting fabricated historical results. The issue is how much work remains before those disclosures can be replaced with actual evidence. No numerical grade is assigned because the supplied instructions do not specify grading weights.

## Evidence and verification

I read the instructions, the 21-page paper, all notebook cells and saved textual results, the notebook builder and execution helper, and the presentation's narrative, generator, and numerical snapshot. I visually checked the paper's methodology page and Tables 1 and 4. The presentation assessment concerns its research content and source data; it is not a slide-by-slide visual or PowerPoint compatibility audit.

I also performed the following checks without modifying the submitted notebook or its source:

| Check | Result |
|---|---|
| Execute a copy of the notebook in an isolated directory under `Final/` | All 11 code cells completed; the notebook's assertions passed. |
| Reproduce the performance table | Matched `presentation/slide_data.json` to approximately `2.2e-16` maximum absolute difference. |
| Execution environment | Python 3.14.7, NumPy 2.5.3, pandas 3.0.6. This is one tested environment, not a dependency compatibility matrix. |
| Historical data availability | No `Final/data/` directory or normalized CRSP inputs were present. Empirical execution could not be tested. |
| Builder versus notebook source | Code cells match. The only detected source difference is Markdown whitespace in the title cell. |
| Universe-order counterexample | Filtering on history before the capitalization cutoff can select a different stock; see finding 3. |
| Benchmark-coverage counterexample | A late-starting benchmark passes validation and can produce an all-cash backtest; see finding 7. |

The files `Instructions1.md` and `Course_Project_Requirements_and_Remarks.md`, although named in the IDE context, were not present in `Final/` during this review. They were not treated as additional requirements. This review uses the available `Instructions.md` as the course specification.

## 1. Critical: the required historical study has not been performed

**Evidence:** `Instructions.md`, lines 4 and 65; notebook Sections 0, 2, 3, and 12; [README.md](README.md). The current generator creates 1,100 synthetic securities over 2000–2025, with 276 investment months beginning in January 2003. The saved input audit contains zero terminal events. No CRSP extraction or normalization implementation is delivered.

The instruction to use CRSP beginning in 1929 is central, not a stretch objective. An artificial panel cannot establish historical coverage, survivorship handling, economic signal behavior, or replication of the paper. Changing `MODE` to `"crsp"` only changes the input reader; it does not perform the missing research and data engineering.

**Required revision:** Deliver the actual extraction/normalization workflow and the course-approved data package. Document source tables and fields, database release, extract date, historical security and exchange eligibility, units, return conventions, share classes, corporate actions, and terminal events. Include initialization history sufficient for the December 1928 formation. Report eligible counts, exclusions by reason, and missingness by calendar period. Reproduce 1929–2016 separately before extending the study through a fixed later endpoint.

**Acceptance evidence:** A fresh empirical notebook run, backed by accessible data and provenance, with January 1929 as the first intended investment month and explicitly audited coverage through the chosen endpoint. A checklist describing future cleaning is not equivalent to implemented cleaning.

## 2. Critical: most required factor diagnostics are absent

**Evidence:** `Instructions.md`, Factor Diagnostics items 3–7; notebook Sections 3–5 and 8–11. The required input schema has no historical industry classification. The analysis contains portfolio comparisons but no industry-neutral exposures, IC series, decile analysis, or factor-mimicking portfolios.

These are not minor missing charts. They are the course's prescribed evidence for whether a signal predicts subsequent returns and whether its behavior is stable. A table comparing portfolio Sharpe ratios does not substitute for that evidence.

**Required revision:** Add a separate diagnostics section that:

- Defines the direction and evaluation universe of each exposure: lower volatility is favorable; higher momentum and payout are favorable. Define precisely where the combined score exists, since the paper ranks momentum and payout within the low-volatility pool.
- Uses point-in-time US industry labels, subtracts industry means, applies the stated standardization, and clips standardized exposures to `[-3, 3]`. Document treatment of small or degenerate groups and missing classifications.
- Measures rank IC against forward total returns adjusted by the equal-weight return of the formation-date industry cohort. Preserve delisted names and their audited returns in that cohort.
- Reports mean IC, a moving-average IC series, variance, mean/standard deviation, return-prediction decay, and exposure persistence over several declared horizons.
- Forms deciles at the formation date and reports industry-adjusted forward returns, stock-level industry hit rates, and the required subperiod comparisons.
- Implements the requested cross-sectional factor-mimicking/WLS exercise and lagged portfolio combinations, or explicitly documents any instructor-approved scope exception. A time-series regression of the strategy on factor returns is a different exercise.

**Keep the replication baseline distinct from these diagnostics.** The paper explicitly compares scores across sectors on page 4. Industry-neutralizing the original selection rule would create a modified strategy, not an exact baseline replication. The appropriate structure is an unneutralized paper baseline, the required neutralized signal diagnostics, and a separately labeled industry-aware extension.

There is also a terminology problem in the instructions: `mean(ER) / sd(ER)` is a standardized mean, not the conventional t-statistic for a sample mean. Report the requested ratio under its literal definition and report a proper inferential statistic separately. For independent observations the latter uses `sd / sqrt(T)`; overlapping forward returns require a dependence-aware standard error, such as a documented HAC estimator. Do not label the two quantities interchangeably.

## 3. High: the universe construction deviates from the paper

**Evidence:** Paper page 4; [build_notebook.py](build_notebook.py), lines 330–345; notebook Sections 2 and 5. The paper makes at least 36 months of return history a condition of eligibility for the top-1,000 universe. The code first takes the largest 1,000 and then drops incomplete signal observations. It subsequently takes the low-volatility half of that reduced set.

This is a disclosed convention, but it is still a material replication difference. A large recent listing can occupy a top-1,000 slot without becoming a candidate, while a smaller stock with the required history is never considered. The resulting low-volatility pool need not have the paper's composition or size.

**Verified counterexample:** In a five-stock fixture with a four-stock universe limit and one holding, the largest stock has missing volatility history. Capitalizations are `[500, 400, 300, 200, 100]`; volatility values are `[missing, .4, .3, .2, .1]`; stock 5 has the strongest momentum and payout. The current function selects stock 4 with three complete candidates. Applying the history screen first selects stock 5 with four complete candidates.

**Required revision:** Implement the paper's return-history eligibility before capitalization selection. Separately decide and document how missing momentum or payout is handled; the paper's history rule does not automatically resolve every complete-case convention. Compare the existing and corrected universe definitions on historical data and report their effects on membership, returns, and turnover. Retain explicit treatment of early periods with fewer than 1,000 eligible securities.

## 4. High: the proposed extensions do not yet demonstrate an improvement

**Evidence:** Notebook Sections 9–12 and [presentation/speaker_notes.md](presentation/speaker_notes.md), slides 13 and 21. Current extensions are signal removal, calendar splits, and a transaction-cost sweep. These are useful evaluation exercises. No sector-aware selection, turnover-reduction rule, or other modified strategy is implemented.

An ablation asks what a component contributes. A period split asks whether performance persists. A cost sweep asks how sensitive performance is to an assumption. None by itself establishes an improved investment rule. There are also no implemented uncertainty estimates or factor-attribution regressions, despite these being described as future work.

**Required revision:** Choose one motivated, limited modification after establishing the baseline. Two defensible candidates are industry-constrained portfolio construction, which addresses the instructor's sector concern, or a buy/hold rank buffer, which addresses turnover and is discussed on paper page 9. Define its rule and constraints before choosing results to emphasize. Compare it with the baseline on the same universe, dates, return conventions, and cost assumptions.

Define success in advance: for example, lower turnover with similar gross performance and stronger net performance, or lower industry concentration without an unacceptable performance loss. Report paired performance differences and dependence-aware uncertainty, as well as changes in exposures and risk. Preserve the 2017–2018 transition and 2019+ reporting split, but do not call later historical data an untouched holdout if it influences rule selection.

A negative result is acceptable. The necessary deliverable is a credible test of an improvement, not a promise to find a winning variant. The instructions also explicitly allow substantial data work to outweigh elaborate enhancements; a well-audited replication plus one modest extension is preferable to several unvalidated variants.

## 5. High: there is no direct reconciliation with the paper's results

**Evidence:** Paper pages 4–10 and Tables 1, 2, and 4; notebook `STRATEGIES` and Sections 8–11. The project has neither a paper-versus-replication table nor the paper's opposite speculative portfolio. Its main summary reports net strategy returns, while the paper's principal comparisons are gross of implementation costs.

The current “No momentum” portfolio remains low-volatility screened; it is not the paper's standalone payout strategy. Likewise, “No payout” is not the paper's standalone momentum strategy. These are legitimate ablations, but they should not be substituted for the paper's single-factor controls.

**Required revision:** Add a reconciliation table with source page/table, portfolio, sample, statistic definition, published value, replicated value, difference, and explanation. At minimum cover the US conservative portfolio, market, speculative portfolio, relevant single-signal controls, decade results, and turnover/cost assumptions. Keep the expanded international study outside scope unless it is explicitly chosen.

Useful targets from the supplied paper include:

| Published item | Reference value | Comparison needed |
|---|---:|---|
| Conservative compounded return, 1929–2016 | 15.1% | Same-period gross CAGR; Table 1, page 18. |
| Market compounded return, 1929–2016 | 9.3% | Matching market total-return series; Table 1. |
| Conservative annual volatility | 16.5% | Same-period gross monthly-return volatility; Table 1. |
| US quarterly single-counted turnover | 32% | Matching turnover definition, with initial investment identified separately; Table 4, page 21. |
| US trading-cost scenarios | 10 and 30 bps per dollar traded | Add the paper's 30-bps case; the existing 25/50-bps cases are supplementary. |

Read the paper critically too. Table 1's displayed Sharpe values approximately equal displayed simple return divided by volatility—for example, `15.5 / 16.5 ≈ 0.94`—although its caption describes subtracting the Treasury-bill return. This is an apparent definitional inconsistency requiring reconciliation, not justification for changing the risk-free rate to hit 0.94. Table 4 also reports a 15.24% gross US return, rather than Table 1's 15.1% compounded figure. Cite each target with its own stated definition instead of treating all published return numbers as interchangeable.

If reproducing Table 2, remember that its dependent portfolio is **Conservative minus Speculative (CMS)**, not the long-only conservative portfolio. A long-only alpha regression is useful but does not reproduce CMS alpha. Show the two legs separately; distinguish a research return spread from an implementable short strategy with borrow and financing costs. Add appropriately aligned factor data and robust inference rather than leaving attribution as an optional final paragraph.

## 6. High: payout and corporate-action handling remain assumptions, not audited results

**Evidence:** Notebook Sections 2–4; `build_notebook.py`, lines 125–158 and 282–295; `Instructions.md`, line 67. The input contract delegates all difficult dividend, share-adjustment, and terminal-return work upstream. That upstream implementation is absent.

The implemented proxy is:

`trailing 12-month adjusted cash dividends / adjusted price + 1 - current adjusted shares / trailing 24-month average adjusted shares`.

Its direction is consistent with rewarding distributions and falling share counts, and the latest-share-count/24-month-average construction follows the paper's description. I do **not** find evidence that the sign is reversed, and I would not demand accounting cash-flow buyback data merely because the signal is called net payout yield: the paper deliberately uses market data. The unresolved issues are the exact dividend convention and whether the actual source fields correctly implement the intended measure.

**Required revision:** Provide worked historical audits for an ordinary dividend payer, a confirmed nonpayer, a split, issuance/repurchase activity, and a terminal event. Show raw fields, adjustments, resulting signals, and information dates. Verify that a split does not create apparent issuance and that confirmed zero dividends are distinguished from unknown distributions. State whether the 24-month mean includes the formation month. Decide the security-versus-company treatment and demonstrate that multiple share classes do not create unintended duplicate company exposure.

The first empirical backtest should also validate the selected database's return and delisting conventions, including that terminal effects enter exactly once. The current warnings about legacy/CIZ compatibility are sensible, but warnings do not prove correct normalization. Same-close signal formation and execution are acknowledged idealizations; quantify a feasible delayed-execution or additional-lag sensitivity before making implementability claims.

## 7. High: validation can silently accept an incomplete backtest calendar

**Evidence:** `build_notebook.py`, lines 240–243 and 394–408. `validate_inputs` checks that the benchmark is contiguous between its own first and last dates. It does not require that it covers the requested backtest start and end. `backtest` then takes whatever benchmark dates are available, starts in cash, and only rebalances when the immediately preceding month appears in `target_map`.

**Verified counterexample:** Stock returns cover January–March 2020, the requested start is January 2020, and a fully invested target exists for December 2019. Supply a benchmark containing only February and March, with zero risk-free returns. Validation accepts it. The engine returns two months of zero return, `cash_weight = 1`, and `holdings_n = 0`; it silently misses the December formation. All stock returns in this fixture are +10% per month.

This does not invalidate the complete synthetic run. It exposes a real empirical-input failure mode that can change the sample and portfolio behavior without an error. A benchmark ending early can similarly truncate the study.

**Required revision:** Define an explicit expected return calendar and assert full benchmark coverage. Require a valid initial formation target for the intended strategy start, or make a later inception a deliberate, prominently reported choice. Validate expected rebalance dates and flag unintended all-cash periods. Add regression checks for missing initial coverage, missing final coverage, and absent initial targets; do not silently forward-fill unavailable returns.

## 8. High: portfolio reporting and trading records do not satisfy the trading requirements

**Evidence:** `Instructions.md`, Portfolio Construction & Trading items 1C, 4, and 5; `build_notebook.py`, lines 433–436, 518–529, 608–624, and 673–685.

The engine records monthly aggregate traded notional, cash, and holding counts. It does not export security-level targets, drifted positions, or a trade ledger. The exported formation audit only reports counts. Consequently, a reviewer cannot trace a reported turnover charge to individual buys and sells from the delivered tables.

The performance function reports CAGR, volatility, Sharpe, drawdown, and positive months. It omits benchmark-relative excess performance, information ratio, benchmark/industry hit rates, skewness, kurtosis, and market correlation. **Positive months are not the required hit ratio:** a positive strategy month can still underperform its benchmark, and the factor-diagnostic hit rate is a stock-versus-industry measure.

**Required revision:** Export dated targets, pretrade drifted weights, signed trade weights/notionals, costs, end-of-period holdings, and terminal settlements. For the monthly research model, make the assumed execution marks and NAV basis explicit. Reconcile summed trades to turnover, charges, and portfolio returns. Add the missing performance statistics and define arithmetic active returns versus relative compounded wealth consistently.

Vary holding period or staggered-cohort parameter `n` as well as transaction costs, as requested for the simple-construction route. The current engine only supports a fully invested long-only target portfolio; a long/short decile or factor-mimicking implementation needs explicit financing and short-position accounting, not merely a renamed strategy. Keep the paper's long-only baseline intact.

The linear/mean-variance optimization language deserves an explicit scope decision. The instructions list both, while item 4 also describes reporting for a simple-construction route and item 3 discusses extra credit. Do not silently characterize every constrained exercise as optional; state which route is being satisfied and any agreed exception. At minimum, the current project lacks industry exposure reporting altogether.

Finally, fixed bps scenarios measure cost sensitivity, not portfolio capacity. A capacity estimate needs trade sizes and liquidity data, with stated participation/impact assumptions and historical coverage. Market correlation should be measured and interpreted; a long-only equity strategy need not have near-zero correlation merely because the generic instructions prefer low correlation.

## 9. Medium: current checks cover a narrow synthetic setting and can fail on valid real data

**Evidence:** `build_notebook.py`, lines 453–502. The checks use the first security in the actual input panel and index its 60th and 46th rows without checking length. A short-lived first security can therefore raise `IndexError` even when the overall historical dataset is valid. The simulated panel gives every security a full history, so it cannot expose this problem.

The existing hand-computed accounting example is valuable, but it only has one initial formation target. It tests drift and a terminal settlement; it does not test a subsequent rebalance against drifted holdings. The future-data perturbation changes returns only, not dividend/share inputs, eligibility, or capitalization.

**Required revision:** Make these checks independent deterministic fixtures rather than assumptions about whichever real security sorts first. Add focused cases for a second rebalance after drift, reinvestment of terminal cash, split invariance of payout inputs, universe/history order, boundary rank ties, and the coverage defect above. A small changing-universe fixture with missing months and terminal events would test the real-data pathway more meaningfully than extending the current fixed-universe simulation.

## 10. Medium: reproducibility needs a submission contract tied to the actual folder and data

**Evidence:** `build_notebook.py`, lines 101–110 and 679–685; `Final/.gitignore`; notebook Section 13 and references.

The initialization claims to support execution from the parent workspace but searches for a directory called `final_project`, not `Final`. From this workspace root it would therefore use the wrong input location and write outputs outside `Final`. Running with the notebook directory as the working directory works; the broader claim is inaccurate.

The run manifest records settings and package versions but no input hashes, extract identifier, or code version. The presentation exporter does hash its source CSVs, which is useful, but that does not establish CRSP input provenance. The `.gitignore` excludes normalized data CSVs; that is compatible with a separate course-approved data package, but a repository checkout alone would not satisfy the code-plus-data requirement.

**Required revision:** Resolve the base path consistently to `Final`, document the supported launch command, and keep generated outputs within that folder. Extend the empirical manifest with input hashes, dataset release/extract date, code version, actual sample, and exclusion counts. Provide either a tested dependency lock or a clearly documented tested environment. Specify how the grader receives and locates the real data.

Fill the author/team placeholder and replace references to an unavailable course brief with traceable references to the actual supplied requirements. Keep the notebook and builder synchronized. The presentation already discloses its private generation runtime; retain the ready-to-open deliverables, but prioritize empirical correctness over further presentation tooling.

## Course-compliance snapshot

This table assesses completed work, not intentions listed in the notebook.

| Requirement | Current status |
|---|---|
| Jupyter submission and runnable code | Met for the synthetic demonstration; empirical path unverified. |
| Submitted historical data and CRSP study since 1929 | Missing. |
| Explicit signal definitions and rebalance timing | Substantially implemented, with payout conventions awaiting audit. |
| Point-in-time universe | Designed, not historically demonstrated; history/capitalization order differs from the paper. |
| Industry-neutral exposures and winsorization | Missing. |
| IC, moving IC, variance, standardized IC, and decay | Missing. |
| Decile forward returns, industry hit rates, and subperiod diagnostics | Missing. |
| Factor-mimicking/WLS and lagged portfolio combinations | Missing. |
| Portfolio weight drift and proportional trading costs | Implemented and demonstrated on synthetic/toy inputs. |
| Trade-by-trade audit trail | Missing from exported results. |
| Required benchmark-relative and distributional metrics | Partially implemented; substantial omissions. |
| Holding-period/cohort and cost joint sensitivity | Cost scenarios only. |
| Constrained optimization and capacity | Not implemented; selected course route needs explicit treatment. |
| Published-result reconciliation and factor attribution | Missing. |
| Tested improvement | Missing; evaluation experiments exist. |

## What deserves credit

- Synthetic results are prominently and consistently labeled. The narrative correctly avoids claiming that simulated performance validates the paper.
- The main selection mechanism is clear: volatility screening, within-pool momentum/payout ranks, equal initial weights, and quarterly formation.
- Momentum timing excludes the formation month; rolling calculations use a complete calendar, so missing months do not silently stretch windows.
- Portfolio weights drift between rebalances; cost charges use both bought and sold notional; terminal proceeds move to cash; unknown held-stock returns raise errors.
- Drawdown includes initial wealth, so a first-month loss is not hidden.
- Equal- and capitalization-weighted universe controls and common-sample ablations are useful design choices. The post-publication discussion appropriately acknowledges the limits of retrospective evidence.
- The demo reproduces, and the presentation's numerical snapshot agrees with it.

Those are meaningful implementation strengths. They do not resolve the empirical omissions or establish that the financial data contract is correct.

## Recommended order of revision

1. **Complete the data pipeline and baseline audit.** Obtain the historical inputs, implement normalization, reconcile payout and corporate actions, correct universe ordering, and enforce sample/formation coverage.
2. **Produce an honest replication report.** Run 1929–2016, reproduce the main US controls and published-statistic comparisons, explain discrepancies, then extend to the fixed later endpoint. Do not tune the rules merely to match 15.1%.
3. **Complete the course diagnostics and trading outputs.** Add historical industries, neutralized exposures, IC/deciles, the applicable factor-mimicking work, an auditable trade history, missing metrics, and holding-period/cost comparisons.
4. **Evaluate one improvement with attribution and uncertainty.** Use a declared rule and matched comparisons; report unfavorable findings as directly as favorable ones.
5. **Finalize the empirical notebook and presentation.** Replace synthetic figures and conclusions together, supply the data package and run manifest, and verify execution from the documented `Final` launch location.

**Reviewer recommendation:** Keep the existing prototype as the foundation, but direct the next effort toward audited CRSP data and the missing research diagnostics. The project will become convincing through traceable historical evidence and explained replication differences, not through additional synthetic charts.
