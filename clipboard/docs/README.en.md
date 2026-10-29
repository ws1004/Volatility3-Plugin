[Korean](../README.md) | **English**

# Clipboard - Volatility 3 Plugin

## Description
`clipboard` is a custom plugin for Volatility 3 that recovers the **current clipboard contents** from a Windows memory dump.

The clipboard lives in the kernel. Every window station (`WinSta0` for the interactive desktop) owns one, and win32k keeps it in three structures:

```
tagWINDOWSTATION  (pool tag "Wind")
  +0x80  pClipBase ───────► tagCLIP[ ]  (one entry per format, 0x20 bytes each)
  +0x88  cNumClipFormats      +0x00  fmt     (CF_UNICODETEXT, CF_DIB, registered format, ...)
  +0x90  iClipSequenceNumber  +0x08  hData ──► tagCLIPDATA  (pool tag "Uscb")
                                                 +0x00  h        (== hData)
                                                 +0x10  cbData
                                                 +0x14  abData[] (the copied bytes)
```

The plugin walks this chain for every window station, matches each `hData` against the `Uscb` objects found in the small and big pools, and prints the data of every format.

`Uscb` objects that no window station points to are printed as well (with `-` in the session columns). These are replaced or freed clipboard data that has not been overwritten yet, i.e. remnants of **earlier copies**.

> Companion plugin: [`cliphistory`](../../cliphistory/docs/README.en.md) recovers the clipboard **history** (Win+V) from the user mode Clipboard User Service.

## Compatibility
`tagWINDOWSTATION` and `tagCLIP` are not in the public win32k PDBs, so the layout is hard coded per build:

| Windows | `pClipBase` | `cNumClipFormats` | `iClipSequenceNumber` | `tagCLIP` size | Status |
| --- | --- | --- | --- | --- | --- |
| Windows 11 24H2 / 25H2 (win32kfull 10.0.26100.x) | `+0x80` | `+0x88` | `+0x90` | `0x20` | Tested (26200.9457) |
| Windows 7 ~ Windows 10 | from the GUI symbol tables bundled with Volatility 3 | | | `0x18` | Fallback, not verified |

A layout is only accepted when every entry of the `tagCLIP` array holds a valid clipboard format, so a wrong layout yields no rows rather than garbage.

## Requirements
- Python 3.10 or higher
- Volatility 3 Framework (version. 2.26.0 or higher, tested on 2.28.3)
- No additional modules

## Usage
Save the clipboard.py file in the path volatility3/volatility3/framework/plugins/windows/clipboard.py.

### Basic Command :
```markdown
python vol.py -f [memory_dump.raw] windows.clipboard
```
### Options :
- `--data-limit N` : Maximum number of characters (or bytes for binary formats) to display. `0` for no limit. (default: 256)
- `--dump` : Write the raw data of each clipboard object to a file.

### Example Commands :
1. Show the clipboard as an aligned table :
    ```markdown
    python vol.py -r pretty -f [memory_dump.raw] windows.clipboard --data-limit 16
    ```
2. Dump every clipboard object to a file :
    ```markdown
    python vol.py -o [output_dir] -f [memory_dump.raw] windows.clipboard --dump
    ```

## Output

| Column | Meaning |
| --- | --- |
| `Session` / `WindowStation` | Owner of the clipboard (`-` = object not referenced by any window station) |
| `Sequence` | Clipboard sequence number. Rows with the same value come from the same copy |
| `Format` | Clipboard format. `Registered (0xc...)` formats are registered by applications at run time |
| `Handle` | `hData` of the `tagCLIP` entry |
| `Object` | Address of the `tagCLIPDATA` object |
| `Size` | `cbData` |
| `Data` | Text for text formats, file list for `CF_HDROP`, hex otherwise |

### Example Output :
An image copied on Windows 11 25H2. One copy is offered in several formats at once, so a single copy produces several rows sharing one sequence number. The actual image is the PNG (`89 50 4e 47`) in format `0xc197`.

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

## Limitations
- Names of registered formats (`0xC000`-`0xFFFF`) live in the session atom table and are not resolved yet.
- `CF_BITMAP` and other GDI formats hold a GDI handle instead of a `tagCLIPDATA`, so their data is not shown.
- `DUMMY_TEXT_HANDLE` / `DUMMY_DIB_HANDLE` mark formats Windows synthesises on demand; they carry no data.
- USER handles are only unique within a session. When objects from different sessions share a handle value, all of them are shown.

## License
This plugin is distributed under the MIT License. See the LICENSE file for more details.

## Author
- Name : ws1004(GyuBin Kim)
- Email : ws1004@kakao.com
- Version : 1.0.0
