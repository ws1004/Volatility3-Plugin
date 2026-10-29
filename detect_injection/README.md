**Korean** | [English](docs/README.en.md)

# Detect Injection - Volatility 3 Plugin

## 설명
`detect_injection`은 메모리 덤프에서 여러 가지 프로세스 인젝션 기법을 탐지하는 Volatility 3 커스텀 플러그인입니다. Windows 시스템에서 실행 중인 프로세스의 DLL 인젝션, 스레드 인젝션, PE 인젝션을 찾는 데 집중합니다.

앞으로 추가 연구를 통해 더 많은 인젝션 기법을 탐지할 예정입니다.

## 호환성
Volatility 3는 framework 2.26.0에서 플러그인 API가 바뀌었습니다(`list_processes` / `list_modules`가 이제
`kernel_module_name` 하나만 받고, `Disassembly`가 `renderers`로 옮겨졌습니다). 설치된 Volatility 3 버전에
맞는 플러그인 버전을 고르세요.

| 플러그인 버전 | Volatility 3 Framework |
| --- | --- |
| `v2.x` (현재) | 2.26.0 이상 |
| `v1.x` | 2.5.2 ~ 2.11.0 |

(2.11.0과 2.26.0 사이에는 릴리스가 없으므로, `v1.x`가 동작하는 마지막 버전은 2.11.0입니다.)

`v1.x`는 현재 트리에 없습니다. 가져오려면 다음과 같이 합니다.
```bash
git log --oneline -- detect_injection/
git show <commit>:detect_injection/detect_injection.py
```

## 요구 사항
- Python 3.10 이상
- Volatility 3 Framework (2.26.0 이상)
- 필요한 모듈:
    - `pefile`
    - `colorama`

## 설치
이 플러그인을 사용하려면 다음 의존성을 설치해야 합니다.
```markdown
pip install -r requirements.txt
```

## 사용법
detect_injection 플러그인을 실행하려면 메모리 덤프와 함께 `--dll`, `--thread`, `--pe` 옵션 중 하나 이상이 필요합니다.

또한 detect_injection.py 파일을 volatility3/volatility3/framework/plugins/windows/detect_injection.py 경로에 저장합니다.

### 기본 명령 : 
```markdown
python vol.py -c config.json -f [memory_dump.raw] windows.detect_injection -h
```
### 옵션 : 
- `--dll` : 프로세스의 DLL 인젝션을 탐지합니다.
- `--thread` : 프로세스의 스레드 인젝션을 탐지합니다.
- `--pe` : 프로세스의 PE 인젝션을 탐지합니다.

### 명령 예시 : 
1. DLL 인젝션 탐지 : 
    ```markdown
    python vol.py -c config.json -f [memory_dump.raw] windows.detect_injection --dll
    ```
2. 스레드 인젝션 탐지 : 
    ```markdown
    python vol.py -c config.json -f [memory_dump.raw] windows.detect_injection --thread
    ```
3. PE 인젝션 탐지 : 
    ```markdown
    python vol.py -c config.json -f [memory_dump.raw] windows.detect_injection --pe
    ```

## 출력

### 출력 예시 : 

#### DLL 인젝션 탐지 (--dll)
![DLL_INJECTION.png](img/DLL_INJECTION.png)

#### 스레드 인젝션 탐지 (--thread)
![THREAD_INJECTION.png](img/THREAD_INJECTION.png)

#### PE 인젝션 탐지 (--pe)
![PE_INJECTION.png](img/PE_INJECTION.png)

## 오류 처리
올바른 옵션(--dll, --thread, --pe)을 하나도 지정하지 않으면, 플러그인이 오류를 내고 종료합니다.

```markdown
At least one option (dll, thread, or pe) must be set.
Use -h for more information.
```

## 라이선스
이 플러그인은 MIT 라이선스로 배포됩니다. 자세한 내용은 LICENSE 파일을 참고하세요.

## 작성자
- Name : ws1004(GyuBin Kim)
- Email : ws1004@kakao.com
- Version : 2.0.0
