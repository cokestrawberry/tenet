# ub-mode 및 참조 도구 조사

## 목적과 조사 범위

Tenet의 개발·수정·리팩터링·검토 공통 원칙을 설계하기 위한 원본 조사입니다.
이 문서는 분석 기록이며, 아직 Tenet의 최종 규범은 아닙니다.

조사 대상은 `unclebob/ub-mode`의 README, SKILL.md, LICENSE와
`crapper`, `dryer`, `mutator`, `uml-viewer`의 공개 README 및 라이선스 파일입니다.

## ub-mode의 실제 구조

[원본 SKILL.md](https://github.com/unclebob/ub-mode/blob/master/SKILL.md)는
코드 작성 또는 변경을 위한 지침으로 세 부분을 사용합니다.

| 구역 | 포함된 주제 | Tenet에서의 처리 방향 |
| --- | --- | --- |
| First Make it Work | 최소 변경, 기초 설계, TDD, 도메인·타입·경계, 동시성, 멱등성 | 핵심 철학 후보 |
| Then Make it Right | 근본 원인, 단계적 검증, 행동 테스트, 지표·변이 분석, 리팩터링 | 핵심 철학과 선택적 도구 분리 |
| Practice | 작업 기록, 컨텍스트 관리, Worktree, 커밋·푸시 | 작업 절차로 분리 |

첫 번째 구역은 다음 규칙을 포함합니다.

- Laziness Protocol: 필요한 최소 변경과 결정의 단일 책임
- Foundational Thinking: 데이터 형태 및 구조적 전제 먼저 점검
- TDD: 실패하는 테스트 확인 → 최소 구현 → 검증
- Redesign From First Principles: 새 요구사항을 기존 구조에 무조건 덧붙이지 않기
- Attack the Premise: 같은 전제가 반복 실패하면 전제 자체 재검토
- Subtract Before You Add: 복잡도 추가 전에 제거 가능한 부분 검토
- Outcome-Oriented Execution: 검증 가능한 결과 중심으로 작업
- Build the Lever: 복잡한 반복 작업에 필요한 도구 마련
- Architecture: 도메인 모델, 입출력 경계, 타입, 멱등성, 공유 상태 분리

두 번째 구역은 다음 규칙을 포함합니다.

- Fix Root Causes: 증상 숨기기보다 근본 원인 해결
- Sequence Work into Verifiable Units: 작은 단위 변경 및 검증
- Test Behavior, Not Implementation: 사용자가 관찰하는 결과 검증
- Crapper, Dryer, Mutator: 특정 분석 도구로 품질 확인
- Refactoring: 현재 동작 고정 → 구조 변경 → 동작 불변 증명

세 번째 구역의 Keep a Log, Guard the Context Window, Worktree Cleanup,
Commit and Push는 설계 품질 자체보다 에이전트의 작업 운영 방식에 가깝습니다.

## 분석에 사용된 용어

- **순환 복잡도(Cyclomatic Complexity)**: 분기 수를 바탕으로 코드에서 가능한 실행 경로의 복잡성을 측정하는 지표입니다.
- **커버리지(Coverage)**: 테스트가 코드의 어느 부분을 실행했는지 나타내는 측정값입니다.
- **CRAP 점수**: 복잡도와 테스트 커버리지를 조합한 변경 위험도 참고 지표입니다.
- **구조적 중복**: 변수 이름이 달라도 코드의 처리 구조가 비슷한 경우를 뜻합니다.
- **변이 테스트(Mutation Testing)**: 연산이나 조건을 일부 바꿨을 때 테스트가 오류를 탐지하는지 확인합니다.

이 용어들은 일반적인 코드 품질 평가 개념이며, 아래 도구는 해당 개념의 구현 사례입니다.
특정 프로젝트나 도구 사용 경험 없이도 Tenet의 원칙을 이해할 수 있어야 합니다.

## 참조 저장소의 역할과 의존성

| 도구 | 실제 목적 | 실행 관련 사항 | Tenet 사용 방침 |
| --- | --- | --- | --- |
| [crapper](https://github.com/unclebob/crapper) | 복잡도와 커버리지로 CRAP 점수 산출 | 언어별 테스트·커버리지 도구 활용 | 선택적 참고 |
| [dryer](https://github.com/unclebob/dryer) | 정규화된 구문 구조의 유사도 검사 | 기본 후보 임계값 0.82 | 선택적 참고 |
| [mutator](https://github.com/unclebob/mutator) | 코드를 변형해 테스트의 결함 탐지 능력 점검 | 실행 시 옆 경로(`../crapper`)에 crapper 체크아웃 필요(이름 식별·기본 커버리지 생성) | 선택적 참고 |
| [uml-viewer](https://github.com/unclebob/uml-viewer) | 구조·의존성·품질 지표 시각화 | Clojure/Java 및 부가 실행 환경 사용 | 선택적 참고 |

`ub-mode`는 CRAP 점수 10 미만, 유사도 0.8 이상 제거, 변이 테스트 적용을
직접 요구합니다. 그러나 `dryer` README의 기본 검출 임계값은 0.82입니다.
두 값은 동일한 계약이 아니며, 검출 후보와 실제 중복 제거 필요 여부도 다릅니다.

Tenet에서는 수치나 도구 사용 자체를 보편적 성공 조건으로 삼지 않습니다.
이미 설치된 분석 도구를 이용할 수는 있지만, 측정값은 코드 근거와 함께 해석해야 합니다.

## DDD와 TDD 관점에서의 관찰

- `Model the Domain`과 `Boundary Discipline`이 존재하지만,
  Bounded Context 사이의 관계와 언어의 의미 경계를 체계적으로 분석하는 절차는 명시되어 있지 않습니다.
- `TDD`는 실패하는 테스트를 먼저 작성하도록 지시합니다.
  다만 기존 저장소의 테스트를 평가할 때 개발 순서를 추정하지 않는 기준은 별도로 필요합니다.
- `Test Behavior, Not Implementation`은 재사용할 가치가 높습니다.
  도메인 불변식과 테스트 사례 간의 대응 관계를 명시하면 검토에도 활용할 수 있습니다.
- `Refactoring`, `Fix Root Causes`, `Subtract Before You Add`는
  개발과 검토 모두에서 재해석할 수 있습니다.
- 복잡도·중복·변이 수치를 보편적인 의무로 두면 언어·프로젝트별 편차를 고려하기 어렵습니다.

DDD 참고: [Martin Fowler, Bounded Context](https://martinfowler.com/bliki/BoundedContext.html).

TDD 참고: [Martin Fowler, Test-Driven Development](https://martinfowler.com/bliki/TestDrivenDevelopment.html).

## 라이선스 및 출처 정책

- `ub-mode`의 LICENSE는 MIT이며 저작권 고지는 `Copyright (c) 2026 Robert C. Martin`입니다.
- `crapper`, `dryer`, `mutator`의 LICENSE는 BSD Zero Clause입니다.
- `uml-viewer`에서는 루트 LICENSE 파일을 확인하지 못했습니다.
  명확한 사용 허락을 확인하기 전에는 해당 코드나 문서를 복사하지 않습니다.
- 이번 조사 문서는 구현 코드나 원문 지시문을 복제하지 않은 요약·분석 자료입니다.
- 향후 `ub-mode`의 보호되는 표현을 복사·수정하는 경우 원본 MIT 전문과
  저작권 고지를 함께 보존해야 합니다.

## 다음 단계의 판단 기준

1. 원본 규칙을 유지·수정·제외·추가로 분류하고 구체적인 이유를 기록합니다.
2. DDD는 도메인 모델과 경계뿐 아니라 실제 비즈니스 규칙의 위치까지 검증합니다.
3. TDD는 개발 시 테스트 우선을 유지하되, 기존 코드 검토 시 관찰 가능한 테스트 품질을 평가합니다.
4. 외부 저장소 체크아웃·특정 도구 실행은 기본 요건으로 요구하지 않습니다.
5. 사용자의 명시적 요청 없이 검토 모드에서 코드·커밋을 변경하지 않습니다.

## 조사 출처

- [ub-mode README](https://github.com/unclebob/ub-mode/blob/master/README.md)
- [ub-mode SKILL.md](https://github.com/unclebob/ub-mode/blob/master/SKILL.md)
- [ub-mode LICENSE](https://github.com/unclebob/ub-mode/blob/master/LICENSE)
- [crapper README](https://github.com/unclebob/crapper/blob/master/README.md)
- [dryer README](https://github.com/unclebob/dryer/blob/master/README.md)
- [mutator README](https://github.com/unclebob/mutator/blob/master/README.md)
- [uml-viewer README](https://github.com/unclebob/uml-viewer/blob/master/README.md)
