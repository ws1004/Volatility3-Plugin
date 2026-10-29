[Korean](../README.md) | **English**

# Volatility3-Plugin

Volatility3 Plugin produced while doing personal research will be uploaded here.

### Currently produced plugins : 
- [`detect_injection.py`](../detect_injection/docs/README.en.md) : This plugin focuses on identifying DLL injection, Thread injection, and PE injection in running processes on a Windows system. *(v2.x requires Volatility 3 Framework 2.26.0 or higher)*
- [`clipboard.py`](../clipboard/docs/README.en.md) : This plugin recovers the current clipboard contents (every format, plus remnants of earlier copies) from the kernel window station structures (tagWINDOWSTATION → tagCLIP → tagCLIPDATA) on Windows 11 24H2/25H2. *(requires Volatility 3 Framework 2.26.0 or higher)*
- [`cliphistory.py`](../cliphistory/docs/README.en.md) : This plugin recovers clipboard history (Win+V) items, including freed ones, from the heap of the Clipboard User Service (cbdhsvc). *(requires Volatility 3 Framework 2.26.0 or higher)*

### Types of plugins to be produced
- Plugins that have never been produced
- Plugins that were in Volatility2 but are not yet in Volatility3
