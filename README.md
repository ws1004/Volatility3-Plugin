**Korean** | [English](docs/README.en.md)

# Volatility3-Plugin

개인 연구를 하며 만든 Volatility3 플러그인을 이곳에 올립니다.

### 현재 제작된 플러그인 : 
- [`detect_injection.py`](detect_injection/README.md) : Windows 시스템에서 실행 중인 프로세스의 DLL 인젝션, 스레드 인젝션, PE 인젝션을 탐지하는 플러그인입니다. *(v2.x는 Volatility 3 Framework 2.26.0 이상 필요)*
- [`clipboard.py`](clipboard/README.md) : Windows 11 24H2/25H2에서 커널 윈도우 스테이션 구조체(tagWINDOWSTATION → tagCLIP → tagCLIPDATA)를 따라가 현재 클립보드 내용(모든 포맷과 이전 복사의 잔해)을 복구하는 플러그인입니다. *(Volatility 3 Framework 2.26.0 이상 필요)*
- [`cliphistory.py`](cliphistory/README.md) : Clipboard User Service(cbdhsvc)의 힙에서 해제된 항목을 포함한 클립보드 히스토리(Win+V) 항목을 복구하고, 옵션으로 클립보드 이미지(PNG, DIB)도 카빙하는 플러그인입니다. *(Volatility 3 Framework 2.26.0 이상 필요)*

### 앞으로 만들 플러그인
- 아직 만들어진 적 없는 플러그인
- Volatility2에는 있었지만 Volatility3에는 아직 없는 플러그인
