# Tenet

Tenet is a set of software engineering principles for both development and code review,
centered on Domain-Driven Design (DDD) and Test-Driven Development (TDD).

It helps coding agents make decisions based on domain rules and observable behavior when
building features, modifying existing code, refactoring, or reviewing a repository.
Tenet is distributed as a plugin for Claude Code and Codex.

A domain is the problem area that software serves, while tests verify expected behavior.
Tenet uses both perspectives to evaluate design and implementation choices.

## Core principles

| Area | Principles |
| --- | --- |
| Domain | Model the real domain, use a shared language, protect invariants, and respect model boundaries |
| Testing | Define behavior before coding, follow Red-Green-Refactor, and verify observable outcomes and meaningful failures |
| Design | Make dependencies and state explicit, and simplify before adding complexity |
| Evolution | Change safely with evidence |

See [Engineering Principles](docs/principles.md) for the meaning of each principle and
how it applies to development and review.
The agent instructions are in [SKILL.md](plugins/tenet/skills/tenet/SKILL.md).

## Installation

### Claude Code

```sh
claude plugin marketplace add cokestrawberry/tenet
claude plugin install tenet@tenet
```

### Codex

```sh
codex plugin marketplace add cokestrawberry/tenet
codex plugin add tenet@tenet
```

These installation commands follow the conventions of existing plugins.
The final installation process for Tenet has not yet been verified on both platforms.

## Usage

Specify an operation and a target or request when invoking the skill.
Tenet does not automatically apply to every task without an explicit invocation.

For example, in Claude Code:

```text
/tenet develop Implement account withdrawals using TDD
/tenet modify Change the conditions for canceling an order
/tenet refactor Restructure src/orders/ while preserving existing behavior
/tenet review src/orders/
```

In Codex, use:

```text
$tenet:tenet review src/orders/
```

During development, Tenet defines expected behavior first and implements changes in small,
verified steps. During review, it examines code and test evidence and distinguishes
confirmed problems from optional improvements. A review-only request does not authorize
changes to source files.

## Design approach

- Do not require particular object types, layer structures, or design patterns without a concrete need.
- Do not infer whether a developer followed TDD from the final code alone.
- Do not require external analysis tools or checkouts of other repositories.
- Do not treat complexity, duplication, coverage, or mutation-testing scores as conclusive on their own.
- Do not make unrelated changes or perform Git operations outside the requested scope.

## Development and evaluation

- [Original source audit](docs/ub-mode-audit.md)
- [DDD/TDD gap analysis](docs/gap-analysis.md)
- [Engineering principles](docs/principles.md)
- [Evaluation and verification](docs/evaluation.md)

The initial evaluation suite includes three cases covering development and review.
The presence of evaluation definitions alone does not establish that the skill behaves
correctly; see the evaluation documentation for execution and verification procedures.

## Attribution and license

Tenet adapts ideas from earlier software engineering guidance through a DDD/TDD lens.
It does not require separate analysis tools or external repository checkouts.
The projects consulted and their attribution are documented in the third-party notices.

Tenet is licensed under the [MIT License](LICENSE).
For original-source copyright and license notices, see
[THIRD_PARTY_NOTICES.md](plugins/tenet/THIRD_PARTY_NOTICES.md).
