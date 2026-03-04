# Architecture Diagrams (Mermaid)

This folder keeps high-signal architecture diagrams that should be updated when flow logic changes.

## Files

- `module-dependency.mmd`: module-level dependency map across frontend, API, services, tasks, engines, and infra.
- `sequence-testcase-execution-result.mmd`: end-to-end runtime flow from test case creation to execution result query.
- `sequence-health-omniparser.mmd`: aggregated health-check path and OmniParser probe behavior.
- `sequence-neural-design-to-execution.mmd`: Flow 1 design analysis/generation to Flow 3 execution handoff.
- `sequence-dispatcher-branching.mmd`: dispatcher routing with UI/API branch execution and persistence.
- `sequence-phoenix-compile-heal.mmd`: Phoenix trace compile + script healing workflow.
- `sequence-exception-timeout.mmd`: timeout branch from step execution to failed final status.
- `sequence-exception-assertion-failure.mmd`: assertion failure branch and result persistence.
- `sequence-exception-self-heal-fallback.mmd`: UI self-healing failure fallback/abort branch.

## Maintenance rule

When changing endpoint orchestration, Celery dispatching, engine routing, or health probe logic:

1. Update the impacted `.mmd` file in this folder in the same PR.
2. Keep node names aligned with actual module/file names.
3. Ensure sequence steps still match real API contracts.
4. Run `python scripts/check_mermaid_diagrams.py` before pushing.
5. CI `Backend CI` also runs Mermaid guard and will fail on invalid diagram syntax/structure.
