# Tenet

도메인 주도 설계(DDD)와 테스트 주도 개발(TDD)를 중심으로
개발과 코드 검토에 공통으로 적용할 수 있는 소프트웨어 엔지니어링 원칙입니다.

Tenet은 코딩 에이전트가 새로운 기능을 만들거나 기존 코드를 수정·리팩터링·검토할 때
도메인과 사용자 동작을 중심으로 판단하도록 돕는 Skill입니다.
Claude Code와 Codex에서 사용할 수 있도록 Plugin 구조로 배포합니다.

도메인은 소프트웨어가 해결할 업무 영역이며, 테스트는 예상하는 동작을 검증하는 수단입니다.
Tenet은 두 관점을 함께 사용해 설계와 구현의 타당성을 판단합니다.

## 핵심 원칙

| 영역 | 원칙 |
| --- | --- |
| Domain | 실제 도메인 모델링, 공통 언어, 불변식 보호, 모델 경계 존중 |
| Testing | 구현 전 동작 정의, Red-Green-Refactor, 관찰 가능한 결과와 실패 검증 |
| Design | 명시적인 의존성·상태, 추가 전에 단순화 |
| Evolution | 근거를 통한 안전한 변경 |

각 원칙의 의미와 개발·검토 기준은 [엔지니어링 원칙](docs/principles.md)에서 설명합니다.
실제 에이전트 지침은 [SKILL.md](plugins/tenet/skills/tenet/SKILL.md)에 있습니다.

## 설치

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

설치 명령은 기존 플러그인의 배포 규칙을 기준으로 작성했습니다.
Tenet 자체의 최종 설치 검증은 아직 진행하지 않았습니다.

## 사용법

명령을 실행할 때 작업 유형과 대상 또는 요청을 함께 제공합니다.
별도 호출 없이 모든 작업에 자동 적용되도록 구성하지 않았습니다.

Claude Code에서 사용하는 예시는 다음과 같습니다.

```text
/tenet develop 계좌 출금 기능을 TDD로 구현
/tenet modify 주문 취소 조건을 변경
/tenet refactor src/orders/ 의 구조를 정리하되 기존 동작 보존
/tenet review src/orders/
```

Codex에서는 다음 형식으로 호출합니다.

```text
$tenet:tenet review src/orders/
```

개발에서는 기대 동작을 먼저 정의하고 검증하면서 작은 단위로 구현합니다.
검토에서는 코드와 테스트의 근거를 확인하고, 문제점과 선택적 개선 제안을 구분합니다.
검토 요청만 받은 경우에는 소스 파일을 수정하지 않습니다.

## 설계 방향

- 특정 객체 유형, 계층 구조나 설계 패턴을 무조건 요구하지 않습니다.
- 완성된 코드만으로 과거 개발자가 TDD를 사용했는지 단정하지 않습니다.
- 외부 분석 도구나 다른 저장소의 체크아웃을 필수로 요구하지 않습니다.
- 복잡도, 중복도, 커버리지, 변이 테스트의 수치를 단독 판정 기준으로 사용하지 않습니다.
- 작업 범위를 벗어나는 수정이나 Git 작업을 임의로 수행하지 않습니다.

## 개발 과정 및 검증

- [원본 조사](docs/ub-mode-audit.md)
- [DDD·TDD Gap Analysis](docs/gap-analysis.md)
- [엔지니어링 원칙](docs/principles.md)
- [Evals 및 검증 계획](docs/evaluation.md)

초기 Evals는 개발과 검토에 관한 세 가지 사례를 포함합니다.
검사 설정을 추가한 단계이며, 모델을 대상으로 실제 실행한 결과를 뜻하지 않습니다.

## 출처 및 라이선스

프로젝트는 기존 소프트웨어 엔지니어링 지침의 원칙을 DDD·TDD 관점에서 재구성했습니다.
별도 분석 도구나 외부 저장소 설치 없이 사용할 수 있습니다.
참고한 프로젝트 목록과 출처는 원본 저작권 고지 문서에 정리했습니다.

Tenet 자체는 [MIT](LICENSE) 라이선스로 제공됩니다.
참고한 원본의 저작권·라이선스는 [THIRD_PARTY_NOTICES.md](plugins/tenet/THIRD_PARTY_NOTICES.md)를 확인하십시오.
