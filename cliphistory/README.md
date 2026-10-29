**Korean** | [English](docs/README.en.md)

# Clipboard History - Volatility 3 Plugin

## 설명
`cliphistory`는 Windows 메모리 덤프에서 **클립보드 히스토리(Win+V) 항목**을 복구하는 Volatility 3 플러그인입니다.

현재 클립보드와 달리 히스토리는 커널에 있지 않습니다. 로그인한 사용자마다 `svchost.exe` 안에서 도는 Clipboard User Service(`cbdhsvc_<LUID>`)가 자기 프로세스 힙에 보관합니다.

```
CBDHSvc!ClipboardHistoryItemInternal
  +0x00  vftable 포인터 3개 (cbdhsvc.dll 안)
  +0x40  ItemId     (GUID)
  +0x50  Timestamp  (FILETIME)
  +0x60  CDataPackage * ──► windows.applicationmodel.datatransfer!CDataPackage
                              +0xE0  포맷 객체 배열 ──► 포맷 객체
                              +0xE8  포맷 개수          +0x08  이름 (HSTRING, 예: "Text")
                                                        +0x18  텍스트 (UTF-16, "Text"만)
```

플러그인은 `cbdhsvc.dll`이 로드된 모든 프로세스의 private 메모리를 스캔합니다. 그리고 다음 세 가지 모양으로 히스토리 항목을 찾아냅니다.
- vftable 3개가 모두 `cbdhsvc.dll` 안을 가리킴
- 타임스탬프 값이 그럴듯함
- 데이터 패키지의 vftable이 data transfer DLL 안을 가리킴

힙을 따라가는 방식이 아니라서, **해제됐지만 아직 덮어쓰이지 않은 항목도 함께 복구됩니다.**

히스토리는 기능을 켠 경우에만 존재합니다(설정 > 시스템 > 클립보드 > 클립보드 검색 기록).

> 함께 쓰는 플러그인: [`clipboard`](../clipboard/README.md)는 커널에서 **현재** 클립보드 내용을 복구합니다.

## 호환성
이 타입들은 모두 공개 PDB에 없어서, 오프셋을 코드에 직접 넣었습니다.

| 구성 요소 | 버전 | 상태 |
| --- | --- | --- |
| Windows 11 25H2 | 26200.9457 | 테스트 완료 |
| `cbdhsvc.dll` | 10.0.26100.8117 | 테스트 완료 |
| `windows.applicationmodel.datatransfer.dll` | 10.0.26100.1 | 테스트 완료 |

다른 빌드에서는 필드 위치가 바뀔 수 있으니 오프셋을 다시 확인해야 합니다.

## 요구 사항
- Python 3.10 이상
- Volatility 3 Framework 2.26.0 이상 (2.28.3에서 테스트)
- 추가 모듈 없음

## 사용법
cliphistory.py 파일을 volatility3/volatility3/framework/plugins/windows/cliphistory.py 경로에 저장합니다.

### 기본 명령 :
```markdown
python vol.py -f [memory_dump.raw] windows.cliphistory
```
### 옵션 :
- `--pid PID [PID ...]` : 지정한 프로세스만 스캔합니다. `cbdhsvc`가 도는 `svchost.exe`만 지정하면 훨씬 빠릅니다.
- `--text-limit N` : 항목마다 표시할 최대 글자 수. `0`이면 제한 없음. (기본값: 256)
- `--dump` : 각 항목의 전체 텍스트를 파일로 저장합니다.

### 명령 예시 :
1. Clipboard User Service가 도는 프로세스 찾기 :
    ```markdown
    python vol.py -f [memory_dump.raw] windows.svcscan | findstr cbdhsvc
    ```
2. 그 프로세스에서만 히스토리 복구 :
    ```markdown
    python vol.py -f [memory_dump.raw] windows.cliphistory --pid [PID]
    ```
3. 모든 항목의 전체 텍스트 저장 :
    ```markdown
    python vol.py -o [output_dir] -f [memory_dump.raw] windows.cliphistory --pid [PID] --dump
    ```

## 출력

| 열 | 의미 |
| --- | --- |
| `PID` / `Process` | Clipboard User Service가 도는 프로세스 |
| `Offset` | `ClipboardHistoryItemInternal` 객체 주소 |
| `Timestamp` | 복사한 시각 (UTC) |
| `ItemId` | 히스토리 항목의 GUID |
| `Formats` | 항목의 데이터 패키지에 든 포맷 이름 (예: `Text`, `HTML Format`, `Bitmap`) |
| `Length` | 텍스트 글자 수 |
| `Text` | `Text` 포맷이 있을 때 그 내용 |

항목은 타임스탬프 순으로 정렬됩니다.

## 한계
- 내용을 디코딩하는 건 `Text` 포맷뿐입니다. 다른 포맷(HTML, 이미지, 파일)은 이름만 표시합니다.
- 해제된 항목은 최대한 복구하지만, 메모리가 일부 재사용됐다면 포맷이나 텍스트가 비어 있을 수 있습니다.
- 4MB를 넘는 항목은 클립보드 히스토리가 애초에 보관하지 않으므로 복구할 수 없습니다.

## 라이선스
이 플러그인은 MIT 라이선스로 배포됩니다. 자세한 내용은 LICENSE 파일을 참고하세요.

## 작성자
- Name : ws1004(GyuBin Kim)
- Email : ws1004@kakao.com
- Version : 1.0.0
