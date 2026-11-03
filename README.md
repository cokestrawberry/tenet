# Tenet

DDD(Domain-Driven Design), TDD(Test-Driven Development), 소프트웨어 설계 원칙을 바탕으로 개발과 코드 검토에 공통으로 적용할 엔지니어링 지침을 만드는 프로젝트입니다.

## 목표

- 신규 기능 개발, 수정, 리팩터링, 기존 저장소 검토에 동일한 원칙을 적용합니다.
- 도메인 모델과 비즈니스 규칙을 중심으로 설계하고, 관찰 가능한 동작을 테스트로 보호합니다.
- 코드와 테스트에 근거하여 판단하며, 특정 아키텍처나 도구를 무조건 강제하지 않습니다.
- 별도 분석 도구 또는 외부 저장소 없이도 기본 원칙을 적용할 수 있도록 합니다.

## 현재 상태

초기 구조만 구성된 단계입니다. DDD·TDD 원칙의 최종 목록과 검증 기준은 아직 확정되지 않았습니다. 현재 스킬은 배포 형식과 사용 범위를 확인하기 위한 초안입니다.

## 구조

- `plugins/tenet/skills/tenet/SKILL.md`: 개발 및 코드 검토에 공통으로 적용하는 스킬 진입점
- `plugins/tenet/.claude-plugin/plugin.json`: 플러그인 메타데이터
- `.claude-plugin/marketplace.json`: 플러그인 배포용 Marketplace 메타데이터
- `.gitignore`: 현재는 비어 있으며, 필요한 제외 규칙이 생기면 추가합니다.

## 참고 프로젝트

- [ub-mode](https://github.com/unclebob/ub-mode): 엔지니어링 원칙 및 개발 작업 규율의 참고 자료
- [crapper](https://github.com/unclebob/crapper): 복잡도와 테스트 커버리지 기반 품질 평가 참고
- [dryer](https://github.com/unclebob/dryer): 구조적 중복 분석 참고
- [mutator](https://github.com/unclebob/mutator): 변이 테스트 참고
- [uml-viewer](https://github.com/unclebob/uml-viewer): 구조 및 의존성 시각화 참고

현재는 참고 링크만 포함하며, 해당 저장소의 코드나 문서를 복사하지 않았습니다. 외부 도구는 필수 의존성이 아닙니다.

## 라이선스

MIT. [LICENSE](LICENSE)를 참조하십시오.
