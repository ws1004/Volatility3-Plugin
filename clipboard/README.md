**Korean** | [English](docs/README.en.md)

# Clipboard - Volatility 3 Plugin

## 설명
`clipboard`는 Windows 메모리 덤프에서 **현재 클립보드 내용**을 복구하는 Volatility 3 플러그인입니다.

클립보드는 커널에 있습니다. 윈도우 스테이션(대화형 데스크톱은 `WinSta0`)마다 클립보드가 하나씩 있고, win32k는 이를 세 개의 구조체로 관리합니다.

```
tagWINDOWSTATION  (풀 태그 "Wind")
  +0x80  pClipBase ───────► tagCLIP[ ]  (포맷마다 한 칸, 칸당 0x20바이트)
  +0x88  cNumClipFormats      +0x00  fmt     (CF_UNICODETEXT, CF_DIB, 등록 포맷 등)
  +0x90  iClipSequenceNumber  +0x08  hData ──► tagCLIPDATA  (풀 태그 "Uscb")
                                                 +0x00  h        (== hData)
                                                 +0x10  cbData
                                                 +0x14  abData[] (복사한 실제 바이트)
```

플러그인은 모든 윈도우 스테이션에서 이 연결을 따라갑니다. 각 `hData`를 small pool과 big pool에서 찾은 `Uscb` 객체와 맞춰 보고, 포맷마다 데이터를 출력합니다.

어떤 윈도우 스테이션도 가리키지 않는 `Uscb` 객체도 함께 출력합니다(세션 열이 `-`). 교체되거나 해제됐지만 아직 덮어쓰이지 않은 클립보드 데이터, 즉 **이전에 복사했던 내용의 잔해**입니다.

> 함께 쓰는 플러그인: [`cliphistory`](../cliphistory/README.md)는 유저모드 Clipboard User Service에서 클립보드 **히스토리**(Win+V)를 복구합니다.

## 호환성
`tagWINDOWSTATION`과 `tagCLIP`은 공개 win32k PDB에 없어서, 빌드별 레이아웃을 코드에 직접 넣었습니다.

| Windows | `pClipBase` | `cNumClipFormats` | `iClipSequenceNumber` | `tagCLIP` 크기 | 상태 |
| --- | --- | --- | --- | --- | --- |
| Windows 11 24H2 / 25H2 (win32kfull 10.0.26100.x) | `+0x80` | `+0x88` | `+0x90` | `0x20` | 테스트 완료 (26200.9457) |
| Windows 7 ~ Windows 10 | Volatility 3 내장 GUI 심볼 테이블 사용 | | | `0x18` | 대체 경로, 검증 안 됨 |

`tagCLIP` 배열의 모든 칸이 올바른 클립보드 포맷일 때만 레이아웃을 채택합니다. 그래서 레이아웃이 틀리면 엉뚱한 값 대신 아무 결과도 나오지 않습니다.

## 요구 사항
- Python 3.10 이상
- Volatility 3 Framework 2.26.0 이상 (2.28.3에서 테스트)
- 추가 모듈 없음

## 사용법
clipboard.py 파일을 volatility3/volatility3/framework/plugins/windows/clipboard.py 경로에 저장합니다.

### 기본 명령 :
```markdown
python vol.py -f [memory_dump.raw] windows.clipboard
```
### 옵션 :
- `--data-limit N` : 표시할 최대 글자 수(바이너리 포맷은 바이트 수). `0`이면 제한 없음. (기본값: 256)
- `--dump` : 각 클립보드 객체의 원본 데이터를 파일로 저장합니다.

### 명령 예시 :
1. 칸을 맞춘 표로 보기 :
    ```markdown
    python vol.py -r pretty -f [memory_dump.raw] windows.clipboard --data-limit 16
    ```
2. 모든 클립보드 객체를 파일로 저장 :
    ```markdown
    python vol.py -o [output_dir] -f [memory_dump.raw] windows.clipboard --dump
    ```

## 출력

| 열 | 의미 |
| --- | --- |
| `Session` / `WindowStation` | 클립보드 소유자 (`-` = 어떤 윈도우 스테이션도 가리키지 않는 객체) |
| `Sequence` | 클립보드 시퀀스 번호. 값이 같은 줄은 같은 복사에서 나온 것 |
| `Format` | 클립보드 포맷. `Registered (0xc...)`는 앱이 실행 중에 등록한 포맷 |
| `Handle` | `tagCLIP` 칸의 `hData` |
| `Object` | `tagCLIPDATA` 객체 주소 |
| `Size` | `cbData` |
| `Data` | 텍스트 포맷은 문자열, `CF_HDROP`은 파일 목록, 나머지는 hex |

### 출력 예시 :
Windows 11 25H2에서 이미지를 복사한 상태입니다. 한 번의 복사가 여러 포맷으로 동시에 올라가기 때문에, 같은 시퀀스 번호를 가진 줄이 여러 개 나옵니다. 실제 이미지는 포맷 `0xc197`의 PNG(`89 50 4e 47`)입니다.

```
Session  WindowStation  Sequence  Format               Handle      Object          Size  Data
1        WinSta0        75        Registered (0xc009)  0xcc0663    0xe789a03715d0  8     00 00 00 00 00 00 00 00
1        WinSta0        75        CF_BITMAP            0x40051333  N/A             N/A   -
1        WinSta0        75        Registered (0xc197)  0x908ab     0xe789a9297660  1407  89 50 4e 47 0d 0a 1a 0a 00 00 00 0d 49 48 44 52
1        WinSta0        75        Registered (0xc2ab)  0x1f029f    0xe789a0371ae0  4     01 00 00 00
1        WinSta0        75        Registered (0xc2ac)  0x20aa1     0xe789a0371c30  4     01 00 00 00
1        WinSta0        75        Registered (0xc013)  0xa025f     0xe789a92a2b10  312   00 00 00 00 38 01 00 00 01 00 00 00 04 00 00 00
1        WinSta0        75        CF_DIB               0x2         N/A             N/A   DUMMY_DIB_HANDLE
1        WinSta0        75        CF_DIBV5             0x2         N/A             N/A   DUMMY_DIB_HANDLE
-        -              -         Unknown              0xca0663    0xe789a058ae10  24    14 00 00 00 1b 00 00 00 ba 31 0d e5 75 90 47 27
```

## 한계
- 등록 포맷(`0xC000`-`0xFFFF`)의 이름은 세션 아톰 테이블에 있는데, 아직 읽어 오지 않습니다.
- `CF_BITMAP` 같은 GDI 포맷은 `tagCLIPDATA` 대신 GDI 핸들을 갖고 있어서 데이터가 표시되지 않습니다.
- `DUMMY_TEXT_HANDLE` / `DUMMY_DIB_HANDLE`은 요청이 오면 Windows가 변환해서 만들어 주는 포맷 표시입니다. 실제 데이터는 없습니다.
- USER 핸들은 세션 안에서만 고유합니다. 다른 세션의 객체가 같은 핸들 값을 가지면 모두 출력합니다.

## 라이선스
이 플러그인은 MIT 라이선스로 배포됩니다. 자세한 내용은 LICENSE 파일을 참고하세요.

## 작성자
- Name : ws1004(GyuBin Kim)
- Email : ws1004@kakao.com
- Version : 1.0.0
