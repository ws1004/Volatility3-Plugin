[English](../README.md) | **한국어**

# Volatility3-Plugin

개인 연구를 하며 만든 Windows 메모리 포렌식용 Volatility 3 플러그인 모음입니다. 플러그인은 각각 Python 파일 하나이고, 폴더마다 문서가 있습니다.

## 플러그인

| 플러그인 | 하는 일 | 데이터 출처 | 대상 | 문서 |
| --- | --- | --- | --- | --- |
| [`windows.clipboard`](../clipboard/clipboard.py) | **현재 클립보드 내용**을 모든 포맷으로 복구하고, 이전 복사의 잔해도 함께 복구 | 커널 윈도우 스테이션 구조체(`tagWINDOWSTATION` → `tagCLIP` → `tagCLIPDATA`, 풀 태그 `Uscb`) | Windows 11 24H2 / 25H2 | [한국어](../clipboard/docs/README.ko.md) · [English](../clipboard/README.md) |
| [`windows.cliphistory`](../cliphistory/cliphistory.py) | 해제된(삭제되거나 밀려난) 항목을 포함한 **클립보드 히스토리(Win+V)** 항목을 복구하고, 옵션으로 클립보드 이미지(PNG, DIB)를 카빙 | `svchost.exe` 안 Clipboard User Service(`cbdhsvc`)의 힙 | Windows 11 25H2 | [한국어](../cliphistory/docs/README.ko.md) · [English](../cliphistory/README.md) |
| [`windows.detect_injection`](../detect_injection/detect_injection.py) | 실행 중인 프로세스의 **DLL 인젝션, 스레드 인젝션, PE 인젝션** 탐지 | 프로세스 메모리, 로드된 모듈, 스레드 | Windows | [한국어](../detect_injection/docs/README.ko.md) · [English](../detect_injection/README.md) |

현재 플러그인은 모두 **Volatility 3 Framework 2.26.0 이상**이 필요합니다. (`detect_injection` v1.x는 2.5.2 ~ 2.11.0을 지원했습니다. 해당 문서를 참고하세요.)

## 빠른 시작

1. 플러그인 파일을 Volatility 3의 Windows 플러그인 디렉터리에 복사합니다.
    ```
    volatility3/volatility3/framework/plugins/windows/
    ```
2. 내장 플러그인처럼 실행합니다.
    ```
    python vol.py -f [memory_dump.raw] windows.clipboard
    python vol.py -f [memory_dump.raw] windows.cliphistory
    python vol.py -f [memory_dump.raw] windows.detect_injection --dll --thread --pe
    ```

`detect_injection`은 추가 모듈 두 개(`pefile`, `colorama`)가 필요합니다. `pip install -r detect_injection/requirements.txt`로 설치하세요. 클립보드 플러그인 두 개는 추가 의존성이 없습니다.

옵션, 출력 열, 출력 예시, 한계는 각 플러그인 문서에 있습니다.

## 앞으로 만들 플러그인

- 아직 만들어진 적 없는 플러그인
- Volatility 2에는 있었지만 Volatility 3에는 아직 없는 플러그인

## 라이선스

MIT. [LICENSE](../LICENSE)를 참고하세요.
