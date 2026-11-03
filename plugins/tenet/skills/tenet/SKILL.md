---
name: tenet
description: Apply engineering principles to software development, modification, refactoring, and repository review.
---

# Tenet

Apply consistent software engineering principles to both implementation and assessment.

## Scope

- Development: design and implement changes based on domain requirements and verifiable behavior.
- Modification and refactoring: preserve observable behavior while improving the design.
- Review: assess existing code and tests against the same principles without editing files.

## Principles

The definitive principles are not yet established. Do not claim that this skill enforces a completed DDD or TDD rule set.

## Working rules

- Understand the repository and the user's intent before making changes or judgments.
- Ground design decisions in the domain's actual requirements; do not impose patterns without need.
- For new behavior, identify expected outcomes and meaningful failure cases and use tests to guide implementation.
- During review, distinguish observed defects from suggestions and support findings with concrete evidence.
- Avoid new dependencies and tools unless required by the task.

## Status

This is an initial scaffold. The principles and verification criteria will be developed after
examining ub-mode and its companion tools.
