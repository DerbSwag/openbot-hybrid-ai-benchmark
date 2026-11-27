
# Contracts v1

The four Draft 2020-12 schemas in `schemas/v1/` accept `schema_version: "1.0"`. Schemas are resolved from a fixed local registry. The schema URIs are identifiers, and unresolved references fail closed. Breaking changes require a new schema version and an explicit conversion policy.

| Contract | Identity and requirements |
| --- | --- |
| Case | `case_id` and `revision` bind a synthetic incident prompt, unique ID-bearing facts, external-access constraints and requested deliverable IDs. The CLI reads the file named for the case ID. |
| Rubric | `case_id`, `case_revision` and `rubric_revision` bind weighted expected claim IDs, values and evidence IDs to the case. Rubric deliverable IDs must equal the public list. |
| Run | Unique `run_id` binds the case/rubric revision, `mode`, `protocol_id` and decision model/tokenizer; includes status, typed invocation/event records and nullable output. A referenced Cloud baseline must share protocol, exact case/rubric revision, run kind and decision model/tokenizer, and both runs must contain an executed Cloud invocation using that model/tokenizer. Single-agent modes require one declared model/tokenizer and execution tier across their invocations. |
| Report | Contains deterministic per-run records and mode/run-kind summaries. `input_digest` is SHA-256 of canonical cases, rubrics and runs after sorting set-like lists by identity. Weight, membership and IDs are validated before the report is emitted. |

`classification: synthetic` applies to the underlying data, even for a future `benchmark_observation` collected on a synthetic case. `run_kind` separates those observations from `synthetic_fixture`. Known quantities include `value` plus `provenance` (`measured`, `estimated` or `expected`). Unknown quantities use `value: null` plus a reason. Peak VRAM uses MiB and requires `NOT_MEASURED` when missing. Zero is a known numeric value; aggregate zero totals with zero observations are empty sums.

Run status is `completed`, `partial`, `failed` or `unknown`. Completeness is evaluated independently from invocation telemetry. Missing output yields `unknown` completeness. Context and security each have a separate observation status. A positive overflow or violation is retained when coverage is incomplete. Approval and failure-related interventions use separate event types and have unique IDs per run.

## Per-invocation context

Budget is `prompt_tokens + reserved_output_tokens + safety_margin`, compared with `runtime_context`. Include system instructions, history, tool output and coordination text in the effective prompt tokens; keep their recorded provenance. The report distinguishes below, exactly at, over and unknown budget. Native context is a separate ceiling. A documented rejection requires an over-budget invocation that never executed.

| Context event | Counts towards overflow rate |
| --- | --- |
| `preflight_context_rejection` | Yes |
| `runtime_truncation` | Yes, runtime flag must be true |
| `context_limit_error` | Yes, executed invocation must be failed |
| `compaction` | No |
| `output_limit_truncation` | No |

Runtime status and budget do not establish completeness. Per-invocation output caps differ from exhausting the context window. An over-budget value alone describes preflight arithmetic; it does not fabricate an observed rejection or runtime event.
