# Detect Injection - Volatility 3 Plugin

## Description
`detect_injection` is a custom plugin for Volatility 3 that allows the detection of various process injection techniques in memory dumps. This plugin focuses on identifying DLL injection, Thread injection, and PE injection in running processes on a Windows system.

We will detect more Injections through additional research in the future.

## Compatibility
Volatility 3 changed its plugin API at framework 2.26.0 (`list_processes` / `list_modules` now take a
single `kernel_module_name`, and `Disassembly` moved to `renderers`). Pick the version that matches
your Volatility 3 install:

| Plugin version | Volatility 3 Framework |
| --- | --- |
| `v2.x` (current) | 2.26.0 or higher |
| `v1.x` | 2.5.2 ~ 2.11.0 |

(There is no release between 2.11.0 and 2.26.0, so 2.11.0 is the last version `v1.x` runs on.)

`v1.x` is no longer in the tree. To retrieve it:
```bash
git log --oneline -- detect_injection/
git show <commit>:detect_injection/detect_injection.py
```

## Requirements
- Python 3.10 or higher
- Volatility 3 Framework (version. 2.26.0 or higher)
- Required modules:
    - `pefile`
    - `colorama`

## Installation
To use this plugin, you need to install the following dependencies.
```markdown
pip install -r requirements.txt
```

## Usage
To run the detect_injection plugin, you need a memory dump and at least one of the following options: `--dll`, `--thread`, or `--pe`.

Also save the detect_injection.py file in the path volatility3/volatility3/framework/plugins/windows/detect_injection.py.

### Basic Command : 
```markdown
python vol.py -c config.json -f [memory_dump.raw] windows.detect_injection -h
```
### Options : 
- `--dll` : Detect DLL Injection in processes.
- `--thread` : Detect Thread Injection in processes.
- `--pe` : Detect PE Injection in processes.

### Example Commands : 
1. Detect DLL Injection : 
    ```markdown
    python vol.py -c config.json -f [memory_dump.raw] windows.detect_injection --dll
    ```
2. Detect Thread Injection : 
    ```markdown
    python vol.py -c config.json -f [memory_dump.raw] windows.detect_injection --thread
    ```
3. Detect PE Injection : 
    ```markdown
    python vol.py -c config.json -f [memory_dump.raw] windows.detect_injection --pe
    ```

## Output

### Example Output : 

#### Detect DLL Injection (--dll)
![DLL_INJECTION.png](img/DLL_INJECTION.png)

#### Detect Thread Injection (--thread)
![THREAD_INJECTION.png](img/THREAD_INJECTION.png)

#### Detect PE Injection (--pe)
![PE_INJECTION.png](img/PE_INJECTION.png)

## Error Handling
If no valid option (--dll, --thread, --pe) is specified, the plugin will raise an error and terminate.

```markdown
At least one option (dll, thread, or pe) must be set.
Use -h for more information.
```

## License
This plugin is distributed under the MIT License. See the LICENSE file for more details.

## Author
- Name : ws1004(GyuBin Kim)
- Email : ws1004@kakao.com
- Version : 2.0.0