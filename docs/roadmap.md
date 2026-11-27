
# Phase 1C roadmap

Proposed work for a later approval, Context Engineering and Overflow Regression Validation.

- Establish a controlled `32,768`-token runtime-context baseline on the target runtime. Use matched synthetic test cases and independently reviewed rubrics. Vary one factor at a time, such as history or tool output, and compare prompts below, at and beyond budget including output reserve and safety margin.
- Collect preflight budget decisions, runtime truncation flags, context-limit failures, compaction and output caps. Evaluate deliverable completeness independently against evidence IDs.
- Measure peak inference VRAM from idle baseline through inference. Record the sampling interval, process/device scope, hardware, runtime and concurrent GPU activity. Report `null` with `NOT_MEASURED` if sampling is unavailable.
- Predeclare thresholds and repeat counts. Expect in-budget cases to complete without runtime truncation and over-budget cases to follow the declared admission policy. Treat these as hypotheses to test. Existing exploratory observations do not establish the cause of prompt growth or whether increasing the context will fit GPU memory.

Phase 1B fixtures exercise the contracts for these signals. Live execution and VRAM collection require separate approval.
