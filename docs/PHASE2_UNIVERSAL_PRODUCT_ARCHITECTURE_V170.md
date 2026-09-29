# Phase 2 Universal Product Architecture — design only

**Implementation lock:** no Phase-2 implementation may begin until a v1.7 attested Phase-1 certificate verifies under the out-of-band trust anchor.

When unlocked, Phase 2 is a universal mission workspace rather than a collection of unrelated feature screens. Every capability must enter through the Phase-1 mission/job/event/evidence/artifact/approval boundary.

## Product domains

- Mission OS: long-horizon planning, DAG execution, checkpoints, replanning, approvals and recovery.
- Intelligence OS: model routing, memory, retrieval, research, reasoning councils and bounded agent swarms.
- Build OS: repositories, patches, tests, web/backend/mobile/Android/game and infrastructure build workflows.
- Computer & Browser OS: browser/computer workers with policy, credentials isolation, screenshots, receipts and approval boundaries.
- Data & Document OS: datasets, analysis, charts, PDF/DOCX/XLSX/PPTX pipelines and reproducible artifact generation.
- Media OS: image/video/audio generation and transformation workers with provenance and compute budgets.
- AI/ML OS: local/cloud model registry, GPU jobs, evaluation, fine-tuning/training workflows and experiment evidence.
- Android Lab: SDK/Gradle/ADB/device/QNN verification as explicit worker/tool contracts.
- Automation OS: reusable workflows, schedules, triggers and user-defined tools under the same policy plane.

## Non-negotiable architecture

`UI -> TITAN control plane -> policy/approval -> durable mission DAG -> worker fabric -> tool adapters -> artifact/evidence graph -> audit/observability`

No worker may bypass workspace identity, fencing/lease semantics, approvals, evidence receipts, artifact versioning, quotas, or audit. Capabilities are registered by contract and ownership domain; new top-level roots require architecture-policy changes and tests.

## Phase-2 opening order

1. Universal Mission Workspace and capability registry.
2. Worker/tool protocol and artifact graph.
3. Code/build/test workers.
4. Browser/computer worker.
5. Research/knowledge and document/data workers.
6. Model router/GPU/AI-ML workers.
7. Media and Android labs.
8. Automation and extensibility SDK.
9. Cross-domain end-to-end qualification and product hardening.

This document is architecture only and deliberately contains no Phase-2 implementation.
