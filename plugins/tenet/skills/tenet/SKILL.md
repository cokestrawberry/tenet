---
name: tenet
description: Apply domain- and test-driven engineering principles when developing, modifying, refactoring, or reviewing code.
argument-hint: "[develop | modify | refactor | review] [scope]"
disable-model-invocation: true
---

# Tenet

Use the same engineering principles for building software and assessing existing software.
The principles concern observable behavior, domain correctness, and maintainable design.
They are context-sensitive defaults, not mandatory frameworks or numerical quality gates.

## Select the operation

Determine the operation and scope from the user's request and the invocation arguments.

- **Develop**: add behavior or a new feature.
- **Modify**: change existing behavior without unintended regressions.
- **Refactor**: improve design while preserving observable behavior.
- **Review**: assess the requested scope without changing files, branches, issues, or pull requests.

If the operation or target cannot be determined, request the missing information.
Do not treat a bare invocation as permission to change code.

## Ten engineering principles

### Domain

1. **Model the real domain.** Map actual requirements and business decisions into data and behavior.
   Do not introduce rich domain layers for trivial utilities or CRUD without a concrete need.
2. **Keep a shared language.** Use consistent domain terms in code, tests, and documentation within
   a bounded context. Different contexts may legitimately assign different meanings to a word.
3. **Protect invariants.** Make valid states and transitions explicit; enforce rules in the
   responsible domain model or service. Do not assume that types alone can encode every rule.
4. **Respect model boundaries.** Keep responsibilities coherent and prevent infrastructure concerns
   from governing business rules. A bounded context is not synonymous with a directory or service.

### Testing

5. **Define behavior before coding.** Identify the next small expected outcome and its failure
   conditions. For new behavior, start with a test that currently fails for the expected reason.
6. **Follow Red-Green-Refactor.** Observe the failure, write the least implementation required
   to pass, and simplify without breaking the test. Do not fake tests that cannot honestly run.
7. **Test behavior and meaningful failures.** Verify observable outcomes, important error paths,
   boundary conditions, and domain transitions. Treat coverage and mutation scores as evidence,
   not proof. Avoid tests coupled solely to mocks or implementation details.

### Design

8. **Make dependencies and state explicit.** Validate external input at boundaries; expose
   meaningful side effects. Address retries, idempotency, and shared mutable state when relevant.
9. **Subtract before adding.** Prefer the smallest clear change, remove unnecessary complexity,
   and consolidate decisions that must stay consistent. Do not merge distinct domain concepts
   merely because their implementations look similar.

### Evolution

10. **Change with evidence.** Reproduce defects, fix causes rather than symptoms, and make
    small verifiable changes. Preserve existing contracts when refactoring. Separate established
    problems from preferences or unverified hypotheses.

## Develop or modify

1. Inspect repository conventions, domain vocabulary, current behavior, and the requested change.
2. Write down the observable success criteria and relevant failure and boundary cases.
3. For new or changed behavior, select a small test, run it, and confirm the expected failure.
   A build failure, missing dependency, or failing unrelated test is not a valid Red state.
4. Implement only enough to pass that test. Execute the test and relevant existing tests.
5. Refactor while tests stay green. Repeat for the next case.
6. Describe the resulting behavior and verification. Report any test you could not execute.

For legacy code, first determine what behavior must remain stable. Add characterization tests
when useful and feasible; do not claim that this proves the behavior is correct.
If an honest executable test is impractical, explain the obstacle and use the strongest
available verification instead of fabricating a passing check.

## Refactor

Identify observable contracts before editing. Protect those contracts with existing tests
or focused characterization tests when feasible. Change the structure without intentionally
changing behavior, verify again, and describe any limits of the evidence.

## Review

1. Determine the requested scope and inspect relevant source, tests, documented requirements,
   and call paths. Do not assume a particular framework or DDD directory layout is required.
2. Reconstruct important domain rules and boundaries. Mark inferred rules as hypotheses until
   corroborated by requirements, tests, or demonstrable behavior.
3. Examine tests for business invariants, observable outcomes, failure paths, boundaries,
   and their sensitivity to incorrect behavior. Do not infer test-first history from the final tree.
4. Check dependency direction, misplaced responsibilities, inappropriate shared state,
   unnecessary abstractions, and meaningful duplication only where relevant.
5. Verify suspected defects where possible with a focused test, trace, or concrete code path.
   Do not execute destructive or production-affecting commands to prove a review finding.
6. Report confirmed defects separately from design suggestions and unresolved questions.
   For each defect, provide its location, triggering condition, consequence, and evidence.
   If no supported defects are found, state that along with relevant review limitations.

A requested review is read-only. Do not edit code, commit, push, or open PRs unless the user
separately authorizes such changes.

## Evidence and trade-offs

- Prefer explicit user requirements, repository code and tests, and authoritative domain material.
- Do not claim a command ran or a test passed without observing the result.
- Distinguish a failing test, an absent test, and an unexecuted test.
- Assess a design in its actual context. A simple function can be better than an aggregate.
- An architectural preference is not automatically a defect.
- Use existing project tooling where practical. Do not require crapper, dryer, mutator,
  uml-viewer, or another external checkout for ordinary use.
- The user's requested scope takes priority over unrelated cleanup or speculative redesign.

## Origin

Tenet's approach was informed by
[ub-mode](https://github.com/unclebob/ub-mode), DDD, and TDD.
It uses its own task guidance and does not execute the original companion tools.
