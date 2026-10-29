[Korean](../README.md) | **English**

# Clipboard History - Volatility 3 Plugin

## Description
`cliphistory` is a custom plugin for Volatility 3 that recovers **clipboard history (Win+V) items** from a Windows memory dump.

Unlike the current clipboard, the history is not kept in the kernel. It is kept by the Clipboard User Service (`cbdhsvc_<LUID>`), which runs inside an `svchost.exe` per logged on user, in that process's heap:

```
CBDHSvc!ClipboardHistoryItemInternal
  +0x00  3 vftable pointers (inside cbdhsvc.dll)
  +0x40  ItemId     (GUID)
  +0x50  Timestamp  (FILETIME)
  +0x60  CDataPackage * ──► windows.applicationmodel.datatransfer!CDataPackage
                              +0xE0  format object array ──► format object
                              +0xE8  format count              +0x08  name (HSTRING, e.g. "Text")
                                                               +0x18  text (UTF-16, "Text" only)
```

The plugin scans the private memory of every process that has `cbdhsvc.dll` loaded and identifies history items by their shape: three vftables inside `cbdhsvc.dll`, a plausible timestamp, and a data package whose vftable is inside the data transfer DLL. Because it does not walk the heap, **freed items that have not been overwritten yet are recovered as well**.

The history only exists when it has been turned on (Settings > System > Clipboard > Clipboard history).

> Companion plugin: [`clipboard`](../../clipboard/docs/README.en.md) recovers the **current** clipboard contents from the kernel.

## Compatibility
None of these types are in public PDBs, so the offsets are hard coded:

| Component | Version | Status |
| --- | --- | --- |
| Windows 11 25H2 | 26200.9457 | Tested |
| `cbdhsvc.dll` | 10.0.26100.8117 | Tested |
| `windows.applicationmodel.datatransfer.dll` | 10.0.26100.1 | Tested |

Other builds may move the fields and need the offsets re-checked.

## Requirements
- Python 3.10 or higher
- Volatility 3 Framework (version. 2.26.0 or higher, tested on 2.28.3)
- No additional modules

## Usage
Save the cliphistory.py file in the path volatility3/volatility3/framework/plugins/windows/cliphistory.py.

### Basic Command :
```markdown
python vol.py -f [memory_dump.raw] windows.cliphistory
```
### Options :
- `--pid PID [PID ...]` : Only scan these processes. Scanning only the `svchost.exe` hosting `cbdhsvc` is much faster.
- `--text-limit N` : Maximum number of characters of text to display per item. `0` for no limit. (default: 256)
- `--dump` : Write the complete text of each item to a file.

### Example Commands :
1. Find the process hosting the Clipboard User Service :
    ```markdown
    python vol.py -f [memory_dump.raw] windows.svcscan | findstr cbdhsvc
    ```
2. Recover the history from that process only :
    ```markdown
    python vol.py -f [memory_dump.raw] windows.cliphistory --pid [PID]
    ```
3. Dump the full text of every item :
    ```markdown
    python vol.py -o [output_dir] -f [memory_dump.raw] windows.cliphistory --pid [PID] --dump
    ```

## Output

| Column | Meaning |
| --- | --- |
| `PID` / `Process` | The process hosting the Clipboard User Service |
| `Offset` | Address of the `ClipboardHistoryItemInternal` object |
| `Timestamp` | When the item was copied (UTC) |
| `ItemId` | GUID of the history item |
| `Formats` | Names of the formats in the item's data package (e.g. `Text`, `HTML Format`, `Bitmap`) |
| `Length` | Number of characters of text |
| `Text` | The text of the item, when it has a `Text` format |

Items are sorted by timestamp.

## Limitations
- Only the `Text` format is decoded. Other formats (HTML, images, files) are listed by name only.
- Freed items are recovered on a best effort basis; an item whose memory was partly reused may show no formats or no text.
- Items larger than 4 MB are not kept by the clipboard history and therefore cannot be recovered.

## License
This plugin is distributed under the MIT License. See the LICENSE file for more details.

## Author
- Name : ws1004(GyuBin Kim)
- Email : ws1004@kakao.com
- Version : 1.0.0
