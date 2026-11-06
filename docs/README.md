# Documentation index

## Current production guides

- [Repository and architecture guide](repository-guide.md)
- [Official US plus clustering scoring contract](official-us-scoring.md)
- [GitHub refresh setup and secrets](advisory-refresh-actions.md)
- [Scheduling, freshness, failure alerts and recovery](operations.md)
- [V2 verification evidence and remaining limits](v2-verification.md)
- [Hosted schema and scoped account setup](hosted-advisory-rollout.md)
- [Local PostgreSQL and Docker](phase-3-local-postgres.md)
- [Security audit evidence](phase-0-security.md)

## Experiments and historical checkpoints

[Research](../research/README.md) contains model development and archived data preparation. Label-transfer, BERT retraining and US/UK pilot documents describe experiments, not a deployed NLP score.

The `phase-*`, `aws-*` and [original roadmap](production-roadmap.md) documents preserve how the system was built and benchmarked. In particular, the old BERT refresh and 48-hour freshness threshold are not the V2 production path. Follow the current operations guide for official-advisory refreshes. The [pre-V2 inventory](archive/repository-guide-pre-v2.md) is retained as historical provenance.
