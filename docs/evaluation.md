# Tenet 평가 실행 및 검증

Claude Code의 네이티브 평가 사례(`case.yaml`, `fixture.sh`)는
`plugins/tenet/evals/`에 남겨 `claude plugin eval plugins/tenet` 명령과 호환되도록 합니다.
플러그인 설치에 불필요한 Python 후처리 도구와 회귀 검사는 저장소 루트
`evals/`에서 관리합니다. 개별 macOS 평가의 trace, 로그, 보고서 및
보충 probe 원본은 Git에 올리지 않고 저장소 외부에 보관합니다.

## 목표

개발 및 코드 검토에서 Tenet의 동작을 평가하고, 채점기의 오판을 탐지합니다.
현재 사례는 세 개이며, **점수만으로 기능 정확성이나 읽기 전용 준수를 확정하지 않습니다.**

| 사례 | 검증 목표 |
| --- | --- |
| `review-domain-invariant` | 문서화된 FILLED 주문 취소 금지 규칙을 근거로 결함 보고 |
| `review-no-dogma` | 단순 함수에 불필요한 DDD 패턴을 강제하지 않음 |
| `develop-withdrawal` | 출금의 정확성, 실패 테스트 선행, 통과 및 리팩터링 판단 |

## 실행 조건

Claude Code 2.1.310에서 확인한 `plugin eval` 명령 옵션을 사용합니다.
저장소 루트에서 실행하며 Python 3와 모델 호출 권한이 필요합니다.
플러그인 출처 및 fixture를 확인한 뒤, 신뢰할 수 있는 실행에서만 `--trust-plugin`을 사용합니다.
비대화형 환경에서는 해당 옵션이 없으면 신뢰 확인 과정에서 실패할 수 있습니다.
`--allow-tools`는 **선택한 모든 사례에 적용**되므로 검토와 개발을 반드시 분리합니다.

### 읽기 전용 검토 사례

```bash
CLAUDE_CODE_EFFORT_LEVEL=high claude plugin eval plugins/tenet \
  --case 'review-*' --scaffold --no-publish --trust-plugin \
  --model claude-opus-5-5 --judge-model haiku --runs 3 \
  --ablation with-without --keep-temp \
  --output-dir "$PWD/../tenet-eval-results/review"
```

이 실행에는 `--allow-tools Bash Write Edit`를 **추가하지 않습니다**.
검토 사례의 `allowed_tools`에 명시된 읽기 도구만 사용해야 하며, 실제 도구 목록을 trace로 확인합니다.

### 개발 사례

```bash
CLAUDE_CODE_EFFORT_LEVEL=high claude plugin eval plugins/tenet \
  --case develop-withdrawal --scaffold --allow-tools Bash Write Edit \
  --no-publish --trust-plugin --model claude-opus-5-5 \
  --judge-model haiku --runs 3 --ablation with-without \
  --keep-temp --output-dir "$PWD/../tenet-eval-results/develop"
```

`--model`과 `--judge-model`은 각기 에이전트와 채점 모델을 지정합니다.
`CLAUDE_CODE_EFFORT_LEVEL`은 현재 실행 프로세스에만 적용합니다.
`--ablation with-without`은 사례별 Tenet 적용/미적용 양쪽을 실행하므로
세 사례에 `--runs 3`을 적용하면 총 18회의 에이전트 실행이 발생합니다.
미적용 arm은 설치되지 않은 `/tenet` 명령을 일반 문자열로 받을 수 있습니다.
이는 독립적인 일반 작업 프롬프트와 다르므로 비교 해석 시 명시합니다.
실행 결과와 임시 작업 공간은 Git 추적 밖의 지정한 경로에 보관합니다.

## 결과의 독립 검증

실제 결과 디렉터리에서 각 회차의 작업 공간과 trace를 찾아 검사합니다.
Claude Code 2.1.310의 `--keep-temp` 결과에서는 회차별 `sealed/home/cwd`에
작업 공간이 보관될 수 있습니다. 실제 경로는 CLI 출력과 결과 메타데이터로 확인합니다.
보존 디렉터리는 접근을 제한할 수 있으므로 CLI가 안내한 **해당 평가 디렉터리만**
`chmod 700`으로 열고, 원본 권한과 경로를 먼저 기록합니다.
읽을 수 없는 경로를 찾지 못한 경로와 혼동하지 않습니다.

평가 에이전트가 생성한 코드는 신뢰할 수 없습니다. 개발 사례의 독립 검증은
에이전트가 작성한 `account.py`를 실제로 실행하므로 **호스트에서 바로 실행하지 않고**,
네트워크와 외부 자원 접근을 차단한 별도 격리 환경에서 수행합니다.
해당 격리를 마련할 수 없다면 실행 검증을 생략하고 `판단 불가`로 기록합니다.

검토 사례는 fixture 밖의 새 파일이나 기존 파일 변경이 없는지 확인합니다.
Python의 `__pycache__` 같은 생성 파일도 읽기 전용 위반으로 취급합니다.
읽기 전용 검증은 신뢰된 `fixture.sh`에서 현재 세 사례가 사용하는
`cat > 파일명 <<'EOF'` 형태의 고정 파일 생성만 해석하며 Bash를 실행하지 않습니다.
지원 범위 밖의 셸 명령은 추측해서 실행하지 않고 검증을 중단합니다.
Claude Code의 실제 평가 사례 생성은 기존 `fixture.sh`를 그대로 사용합니다.
개발 사례는 보존된 작업 공간에서 다음 명령으로 독립 기능 테스트를 실행합니다.

```bash
python3 evals/verify_case.py develop-withdrawal /path/to/eval/workspace
```

검토 사례에도 같은 도구를 적용할 수 있습니다.

```bash
python3 evals/verify_case.py review-domain-invariant /path/to/eval/workspace
python3 evals/verify_case.py review-no-dogma /path/to/eval/workspace
```

검증 도구는 **이미 보존된 작업 공간에만** 적용합니다. 단일 평가의 자동 grader에
추가 연결된 것은 아니므로, 모든 회차에 실행하고 결과를 별도로 기록해야 합니다.
Trace 기반 LLM grader는 Red→Green의 실제 순서와 리팩터링 판단을 평가하려고
시도하지만, Claude Code 2.1.310에서 trace가 24개 메시지를 넘으면 **처음 12개와
마지막 12개만** 채점 입력에 포함되고 중간은 생략될 수 있습니다.
따라서 각 회차의 결과 JSON에서 `tracePath`를 찾아 전체 `trace.jsonl`을 별도로
검토하고, 테스트 추가·기대한 실패 실행·구현 변경·최종 통과 실행의 순서와 출력을 확인합니다.
24개 메시지를 초과해 필요한 근거가 채점 입력에서 누락될 수 있는 회차는 두 trace 기반
grader의 판정을 **단독 증거로 인정하지 않고 `판단 불가`로** 표시합니다.
전체 trace에 근거한 별도의 검증 결과와 grader 결과를 구분해 기록합니다.
실제 파일 변경 여부는 trace만으로 보증하지 않고 독립 검증 결과를 우선합니다.

### 필수 후처리 검증

모델 평가가 끝나면 아래 명령을 실행합니다. 후처리는 모델을 호출하지 않으며,
모든 사례의 적용·미적용 조건과 반복 회차를 처리합니다. LLM 점수만으로 최종 통과를 판단하지 않습니다.

```bash
python3 -B evals/post_eval.py \
  --aggregate ../tenet-eval-results/review/aggregate-result.json \
  --aggregate ../tenet-eval-results/develop/aggregate-result.json \
  --output ../tenet-eval-results/post-verification-1
```

`--output`에는 아직 없는 별도 디렉터리를 지정합니다. 원래 결과나 증거 디렉터리 안에는 쓸 수 없습니다.
원본 파일이나 접근 권한을 변경하지 않으며, 읽을 수 없는 증거는 `INCONCLUSIVE`로 기록합니다.
JSON·JSONL·매핑·출처 자료와 결과 문서는 UTF-8로 읽고 씁니다.
네이티브 평가 fixture는 `.gitattributes`로 LF 줄바꿈을 유지하여
Windows에서도 SHA-256 및 바이트 단위 출처 비교를 변경하지 않습니다.
실행 결과의 `tracePath`로 전체 기록과 같은 임시 디렉터리의 `sealed/home/cwd`를 찾습니다.
임시 파일이 이미 정리됐다면 보존한 사본을 `--run-root`로 지정합니다.

```bash
python3 -B evals/post_eval.py \
  --aggregate /path/to/results/aggregate-result.json \
  --run-root /path/to/preserved-runs \
  --output /path/to/new-verification
```

보존 사본은 `<run-root>/<사례>/<with 또는 without>-<회차>/` 구조입니다.
그 안의 `out/trace.jsonl`과 `workspace/` 또는 `sealed/home/cwd/`를 사용합니다.
`source.json`의 `source` 필드나 `kept-source.txt`에 원래 임시 디렉터리 경로가 있어야 합니다.
결과 JSON의 `tracePath`와 이 경로를 비교하므로, 서로 다른 평가 자료가 섞여도 임의의 회차를 선택하지 않습니다.
`--aggregate`와 `--run-root`는 여러 번 지정할 수 있습니다.

후처리는 다음 근거를 기록합니다.

- 검토: `verify_case.py`로 fixture와 모든 파일을 비교합니다. 생성 파일도 차이로 처리합니다.
- 개발: 복사본에서 `verify_case.py`의 행동 검사를 실행합니다. macOS `sandbox-exec`가 필요합니다.
  네트워크·사용자 디렉터리(`/Users`) 읽기·복사본 밖 쓰기의 차단을 먼저 검사합니다.
  시스템 파일 읽기는 허용합니다. 격리 확인 실패나 지원하지 않는 운영체제에서는 생성 코드를 실행하지 않습니다.
  행동 검사용 복사본에는 제출된 `account.py`만 넣습니다. `verify_case.py`도 작업 공간을
  Python 모듈 검색 경로에 추가하지 않고, 표준 `unittest`를 가져온 뒤 해당 소스만 읽어 실행합니다.
  제출된 `unittest.py`나 같은 이름의 디렉터리가 검증 도구 대신 로딩되지 않도록 합니다.
- 과정: 전체 trace의 도구 호출과 결과를 대응시키고 `Edit`·`Write` 변경을 재현합니다.
  새 테스트의 출금 호출과 잔액·예외 검사를 Python AST로 확인하고, 관찰된 실패·구현 변경·성공의 순서를 검사합니다.
  재현한 파일이 보존된 최종 파일과 같은지도 확인합니다. 이벤트 위치는 1부터 시작하는 JSONL 줄과 0부터 시작하는 블록 번호입니다.
- 보고: 최종 응답에서 리팩터링 결정의 명시적인 설명을 찾아 원문과 위치를 기록합니다.
  이 설명은 에이전트의 주장으로 표시하며, 실제 테스트 실행의 증거로 사용하지 않습니다.

현재 과정 검사는 출금 fixture의 Python `unittest` 실행을 지원합니다.
특정 테스트 함수 이름은 요구하지 않으며, `python3 -m unittest` 같은 모듈 실행과 직접 파일 실행을 인식합니다.
테스트 증거로 인정하는 명령은 단일 실행이어야 합니다. `2>&1`은 허용하지만 stderr 숨기기,
파이프, `;`·`&&` 등으로 연결한 복합 명령은 실행 종료 상태와 출력의 출처를 분리할 수 없어 `INCONCLUSIVE`로 기록합니다.
직접 실행한 도구의 오류 여부와 테스트 요약을 함께 확인해야 실패 또는 통과의 증거로 인정합니다.
따라서 출력 필터를 사용한 과거 기록은 전체 trace가 있어도 과정 검증에 통과하지 못할 수 있습니다.
최초 실패는 새 출금 테스트에서 `Account.withdraw`가 없어서 발생한 경우를 확인합니다.
다른 실패 원인, 인식하지 못하는 명령·도구·편집, 불완전한 출력은 성공으로 추정하지 않습니다.
지원 범위 밖의 올바른 구현도 `INCONCLUSIVE`가 될 수 있습니다.
이 검사는 보존된 도구 출력에 근거하며, 테스트 코드가 의도적으로 위조한 출력을 판별하는 일반적인 증명 도구는 아닙니다.

출력은 `verification.json`과 회차별 요약 `verification.md`입니다.
JSON은 자동 채점, 독립 검사, 실행 완료 여부, 전체 trace 검사, 리팩터링 보고를 구분합니다.
최종 판정은 아래 순서로 결합합니다.

1. 필수 검사 중 하나라도 `FAIL`이면 최종 `FAIL`입니다. LLM 통과 점수로 덮어쓸 수 없습니다.
2. 실패는 없지만 증거 누락·접근 제한·API 오류·채점 오류·검증 미지원이 있으면 `INCONCLUSIVE`입니다.
3. 모든 필수 검사가 통과해야 `PASS`입니다.

프로세스 종료 코드는 전체 `PASS`일 때 0, `FAIL`이 있을 때 1, 실패 없이 판단 불가일 때 2입니다.
종료 코드 1은 후처리 명령 자체의 고장뿐 아니라 검증된 실패 회차가 있다는 뜻일 수 있습니다.
JSON의 `runs`와 `errors`를 함께 확인합니다. 생성된 요약은 원래 LLM 점수를 수정하지 않습니다.

로컬 회귀 검사는 다음과 같이 실행합니다. 모델 호출은 없습니다.
Windows에서는 설치된 Python 실행기(`python` 또는 `py -3`)를 사용해
같은 `-B -m unittest discover -s evals/tests -v` 인자를 전달할 수 있습니다.
심볼릭 링크 생성 권한이 없는 Windows에서는 실제 링크 생성 회귀 검사만
건너뛰며, 모의 루트·내부 링크 거부와 접근 권한 오류 처리는 항상 검사합니다.
신뢰되지 않은 생성 코드의 독립 실행은 여전히 macOS `sandbox-exec` 격리가 필요합니다.

```bash
python3 -B -m unittest discover -s evals/tests -v
```

이전 평가 자료가 있으면 다음 변수로 두 라운드의 실제 기록을 사용하는 회귀 검사도 실행할 수 있습니다.
자료가 없는 환경에서는 해당 검사만 skip으로 기록합니다.

```bash
TENET_PREVIOUS_EVAL=/path/to/previous-evaluation \
TENET_POSTFIX_EVAL=/path/to/postfix-evaluation \
python3 -B -m unittest discover -s evals/tests -v
```

### 보충 Probe의 검증 및 판정

원래 사례가 아닌 별도 Probe 이름을 검증하려면 해당 Probe의 `fixture.sh`가
원래 사례의 Fixture와 **바이트 단위로 일치**한다는 근거를 명시합니다.
JSON 매핑의 키는 평가 결과의 사례 이름이며, 각 항목의 `case`는 원래 세 사례 중 하나입니다.
`fixtureSha256`은 `fixturePath`에 있는 파일의 SHA-256 값입니다.

```json
{
  "probe-dev-long-honest-red": {
    "case": "develop-withdrawal",
    "fixturePath": "/path/to/probe/fixture.sh",
    "fixtureSha256": "<64-character SHA-256 digest>"
  }
}
```

`fixturePath`의 파일과 SHA-256을 모두 확인하고 원래 Fixture와 내용이 같을 때만
해당 사례로 검증합니다. 검증되지 않은 매핑은 `INCONCLUSIVE`입니다.
평가 증거의 복사본이 기존 원본과 일치한다는 사실까지 이 매핑이 증명하지는 않습니다.
전체 Trace의 경로와 보존본의 출처도 종전 방식으로 별도 확인합니다.

```bash
python3 -B evals/post_eval.py \
  --aggregate /path/to/supplement/aggregate-result.json \
  --run-root /path/to/preserved-runs \
  --case-map /path/to/probe-case-map.json \
  --output /path/to/new-verification
```

`automatic`은 원래 LLM 채점 결과로 보존되고 `adjudication`에 별도 판단 근거가 남습니다.
기능 및 과정 Grader의 이름이 명시적으로 확인되고 두 채점 모두 명확히 `PASS` 또는
`FAIL`로 완료되었으며, 전체 Trace·독립 행동 검사·실행 완료·파일 재현·리팩터링
보고가 모두 통과해야 LLM 실패 교정을 검토합니다. 채점 오류나 결과 누락으로
어느 한쪽이라도 `INCONCLUSIVE`이면 독립 증거가 충분해도 자동 `PASS`로 교정하지 않습니다.
기능 Grader가 PASS이면 과정 Grader의 잘못된 FAIL을 전체 Trace 근거로 교정할 수 있습니다.

독립 증거가 모두 완전하고 기능 Grader가 FAIL인 경우에만, 제출한 `test_account.py`의 **테스트 효과 검사**
(`testEffectiveness`)가 PASS여야 교정합니다. 이미 기능 Grader가 PASS인 회차에
이 변이 검사 결과를 추가 필수 조건으로 요구하지 않습니다. 신뢰한 출금 구현에서 제출 테스트를
통과시킨 다음, 출금액 미차감, 0·음수·잔액 초과 허용, 잘못된 입력에서 잔액 변경을
일으키는 7개 변형 구현으로 같은 제출 테스트를 각각 실행합니다.
기준 구현이 통과하고 7개 변형 모두를 테스트 실패로 검출해야 PASS입니다.
변형 일부를 검출하지 못하면 `INCONCLUSIVE`입니다. 이는 해당 변이 집합만으로
원래 기능이 틀렸다고 확정할 수 없기 때문입니다. 지원하지 않는 테스트 형식이나
실행 오류도 `INCONCLUSIVE`로 기록합니다. 테스트는 독립 행동 계약 검사를 통과한 회차에서만
별도 macOS `sandbox-exec` 격리로 실행하고, 제출된 다른 Python 모듈은
작업 공간에 복사하지 않습니다. Python `-I`를 사용하고 표준 `unittest`는
제출 테스트를 읽기 전에 가져옵니다.

현재 지원하는 제출 테스트는 `unittest`와 `account.Account`에 관한 제한된
import 형식입니다. 동적 코드 실행·일부 리플렉션·기타 import를 사용하는
정상 테스트도 INCONCLUSIVE가 될 수 있습니다. 변이 검사는 출금 fixture의
표적 오류 검출 능력을 확인할 뿐 임의의 Python 테스트가 안전하거나
모든 가능한 오류를 탐지한다는 증명은 아닙니다. 원래 LLM 결과는
`automatic`에 유지하며, 각 변형의 실행 결과와 교정 근거를 별도 기록합니다.

기존 LLM의 실패와 독립 증거가 충돌하지만 전체 Trace가 `INCONCLUSIVE`인 경우에는
확정 실패로 단정하지 않고 `INCONCLUSIVE`로 기록합니다.
반면 독립 행동 또는 과정 검증에서 확정된 실패는 항상 `FAIL`입니다.
검토의 내용 품질은 파일 불변 검사만으로 증명할 수 없으므로 LLM 실패를 덮어쓰지 않습니다.

임의 Python `-c` 실행은 import 부작용으로 파일을 변경할 수 있으므로
일반적인 읽기 전용 명령으로 인정하지 않습니다. 다만 출금 fixture의
`python3 -B -c "import account; print(account.Account(5).balance)"`는
도구 출력이 `5`이고, 해당 시점의 `account.py`에 최상위 `Account` 클래스만 있으며
데코레이터·상속·실행 시 기본값·추가 실행 코드가 없고,
일반 매개변수뿐 아니라 `*args`와 `**kwargs`에도 실행 가능한 annotation이 없으며,
생성자가 `self.balance = balance` 한 문장으로만 구성된 경우에 한하여
관찰 명령으로 인정합니다. 이는 특정 평가 fixture의 제한된 정적 검증이지,
일반적인 Python 실행이 안전함을 보장하는 기능이 아닙니다.
이외의 Python 실행이나 변경 가능성을 증명하지 못하는 명령은 판단 불가로 남습니다.

이미 구현 변경이 관찰되었고 그보다 앞선 관련 Red 실행이 없으며,
구현 변경 이전에 미확인 **도구 호출**이 없을 때는 이후 미지원 명령이 있어도
테스트 우선 원칙 위반을 `FAIL`로 보존합니다. 미확인 명령의 호출과 결과가
구현 변경과 겹치는 경우에는 명령 결과가 늦게 도착했더라도 `INCONCLUSIVE`를 유지합니다. 이전에 미지원 도구 호출이
있어 Red 실행을 숨겼을 가능성이 있다면 `INCONCLUSIVE`를 유지합니다.
전체 과정 검증이 통과하더라도 원래 기능 Grader가 실패했고 독립 검사로
모든 기능 채점 기준을 입증할 수 없는 경우, 최종 판정은 `INCONCLUSIVE`입니다.
이는 원래 LLM 채점 오류가 완전히 해결되었다는 뜻이 아닙니다.

## 현재 한계 및 추가 평가 대상

- `develop-withdrawal`은 저장소 내부에 테스트 파일을 생성하는 상황이므로,
  저장소 밖 테스트의 지속성 안내(PR #9)는 아직 검증하지 못합니다.
- 실제 구현의 변이 테스트 탐지 능력을 자동으로 평가하지 않습니다.
- 간단한 불변식 fixture는 미적용 모델도 통과할 수 있습니다. 더 복잡한
  요구사항/호출 경로 사례를 추가하기 전까지 점수 차이를 일반화하지 않습니다.
- `--trust-plugin`은 검토한 플러그인에 대한 실행 시 신뢰 확인을 생략합니다.
  도구 권한 자체를 완화하는 용도로 사용하지 않습니다.
- 보고서에 에이전트 비용과 judge 비용이 분리되어 있으면 합산한 총비용을 기록합니다.
  judge 모델의 실제 버전이 결과에 없으면 명령으로 선택한 이름만 기록합니다.
- 설치된 CLI의 옵션 지원 범위와 샌드박스 설정을 실제 실행 환경에서 재확인해야 합니다.

## 품질 판정

평가 결과는 `유효 통과`, `유효 실패`, `오탐 통과`, `정상 동작 오판`,
`판단 불가`로 구분합니다. 특히 읽기 전용 위반, 허위 근거, 기능 실패,
Red 없는 구현이 단순 문자열 검사만으로 통과하는지 별도로 확인합니다.
