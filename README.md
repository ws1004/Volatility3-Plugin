**English** | [한국어](docs/README.ko.md)

# Volatility3-Plugin

A collection of Volatility 3 plugins for Windows memory forensics, written during personal research. Each plugin is a single Python file with its own documentation.

## Plugins

| Plugin | What it does | Where the data comes from | Target | Docs |
| --- | --- | --- | --- | --- |
| [`windows.clipboard`](clipboard/clipboard.py) | Recovers the **current clipboard contents** in every format, plus remnants of earlier copies | Kernel window station structures (`tagWINDOWSTATION` → `tagCLIP` → `tagCLIPDATA`, pool tag `Uscb`) | Windows 11 24H2 / 25H2 | [English](clipboard/README.md) · [한국어](clipboard/docs/README.ko.md) |
| [`windows.cliphistory`](cliphistory/cliphistory.py) | Recovers **clipboard history (Win+V)** items, including freed (deleted or evicted) ones, and optionally carves clipboard images (PNG, DIB) | Heap of the Clipboard User Service (`cbdhsvc`) inside `svchost.exe` | Windows 11 25H2 | [English](cliphistory/README.md) · [한국어](cliphistory/docs/README.ko.md) |
| [`windows.detect_injection`](detect_injection/detect_injection.py) | Detects **DLL injection, thread injection, and PE injection** in running processes | Process memory, loaded modules, and threads | Windows | [English](detect_injection/README.md) · [한국어](detect_injection/docs/README.ko.md) |

All current plugins require **Volatility 3 Framework 2.26.0 or higher**. (`detect_injection` v1.x supported 2.5.2 to 2.11.0; see its documentation.)

## Quick start

1. Copy the plugin file into the Volatility 3 Windows plugin directory:
    ```
    volatility3/volatility3/framework/plugins/windows/
    ```
2. Run it like any built-in plugin:
    ```
    python vol.py -f [memory_dump.raw] windows.clipboard
    python vol.py -f [memory_dump.raw] windows.cliphistory
    python vol.py -f [memory_dump.raw] windows.detect_injection --dll --thread --pe
    ```

`detect_injection` needs two extra modules (`pefile`, `colorama`). Install them with `pip install -r detect_injection/requirements.txt`. The clipboard plugins have no extra dependencies.

Options, output columns, example output, and limitations are described in each plugin's documentation.

## Planned

- Plugins that do not exist anywhere yet
- Plugins that existed in Volatility 2 but have not been ported to Volatility 3

## License

MIT. See [LICENSE](LICENSE).
