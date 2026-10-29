# Copyright (c) 2026 GyuBin Kim (ws1004)
# Licensed under the MIT License. See the LICENSE file in the repository root for details.
#
import logging
import struct
from typing import Dict, Iterator, List, NamedTuple, Optional, Tuple

from volatility3.framework import exceptions, interfaces, renderers
from volatility3.framework.configuration import requirements
from volatility3.framework.layers import scanners
from volatility3.framework.renderers import format_hints
from volatility3.plugins.windows import bigpools, windowstations

vollog = logging.getLogger(__name__)


class StationLayout(NamedTuple):
    """Where a tagWINDOWSTATION keeps its clipboard, and the size of each tagCLIP."""

    name: str
    clip_base: int
    clip_count: int
    sequence_number: int
    entry_size: int


class ClipFormat(NamedTuple):
    fmt: int
    handle: int


class ClipData(NamedTuple):
    offset: int
    handle: int
    size: int


class Clipboard(interfaces.plugins.PluginInterface):
    """Extracts the contents of the Windows clipboard from win32k's window stations."""

    _required_framework_version = (2, 0, 0)
    _version = (1, 0, 0)

    # win32k types are not in public PDBs, so the layouts are tried in turn and the first one
    # that describes a plausible clipboard is used. Each tagCLIP starts with
    # { ULONG fmt; HANDLE hData; BOOL fGlobalHandle; }.
    LAYOUTS = [
        # Observed on Windows 11 25H2 (26200.9457, win32kfull 10.0.26100.9444)
        StationLayout("win11-26100", 0x80, 0x88, 0x90, 0x20),
    ]
    # Size of tagCLIP in the bundled GUI symbol tables (Windows 7 - Windows 10)
    SYMBOL_ENTRY_SIZE = 0x18
    MAX_FORMATS = 104

    # tagCLIPDATA: { HEAD head { HANDLE h; ULONG cLockObj; }; ULONG cbData; BYTE abData[]; }
    CLIPDATA_TAG = b"Uscb"
    CLIPDATA_SIZE = 0x10
    CLIPDATA_DATA = 0x14
    POOL_HEADER_SIZE = 0x10
    POOL_HEADER_TAG = 0x04
    MAX_SMALL_DATA = 0x20000
    MAX_DATA = 0x10000000

    # Placeholder handles stored for formats that are synthesised on demand
    DUMMY_HANDLES = {1: "DUMMY_TEXT_HANDLE", 2: "DUMMY_DIB_HANDLE"}

    FORMATS = {
        1: "CF_TEXT",
        2: "CF_BITMAP",
        3: "CF_METAFILEPICT",
        4: "CF_SYLK",
        5: "CF_DIF",
        6: "CF_TIFF",
        7: "CF_OEMTEXT",
        8: "CF_DIB",
        9: "CF_PALETTE",
        10: "CF_PENDATA",
        11: "CF_RIFF",
        12: "CF_WAVE",
        13: "CF_UNICODETEXT",
        14: "CF_ENHMETAFILE",
        15: "CF_HDROP",
        16: "CF_LOCALE",
        17: "CF_DIBV5",
        0x80: "CF_OWNERDISPLAY",
        0x81: "CF_DSPTEXT",
        0x82: "CF_DSPBITMAP",
        0x83: "CF_DSPMETAFILEPICT",
        0x8E: "CF_DSPENHMETAFILE",
    }

    @classmethod
    def get_requirements(cls) -> List[interfaces.configuration.RequirementInterface]:
        return [
            requirements.ModuleRequirement(
                name="kernel",
                description="Windows kernel",
                architectures=["Intel64"],
            ),
            requirements.VersionRequirement(
                name="windowstations",
                component=windowstations.WindowStations,
                version=(1, 0, 0),
            ),
            requirements.VersionRequirement(
                name="bigpools", component=bigpools.BigPools, version=(2, 0, 0)
            ),
            requirements.IntRequirement(
                name="data-limit",
                description="Maximum number of characters (or bytes for binary formats) to display (0 for no limit)",
                default=256,
                optional=True,
            ),
            requirements.BooleanRequirement(
                name="dump",
                description="Write the raw data of each clipboard object to a file",
                default=False,
                optional=True,
            ),
        ]

    @classmethod
    def format_name(cls, fmt: int) -> str:
        if fmt in cls.FORMATS:
            return cls.FORMATS[fmt]
        if 0xC000 <= fmt <= 0xFFFF:
            # Registered format; the name lives in the session's atom table
            return f"Registered ({fmt:#x})"
        if 0x200 <= fmt <= 0x2FF:
            return f"CF_PRIVATE ({fmt:#x})"
        if 0x300 <= fmt <= 0x3FF:
            return f"CF_GDIOBJ ({fmt:#x})"
        return f"Unknown ({fmt:#x})"

    @classmethod
    def _is_valid_format(cls, fmt: int) -> bool:
        return (
            fmt in cls.FORMATS or 0x200 <= fmt <= 0x3FF or 0xC000 <= fmt <= 0xFFFF
        )

    @classmethod
    def symbol_layout(
        cls, winsta: interfaces.objects.ObjectInterface
    ) -> Optional[StationLayout]:
        """Builds a layout from the GUI symbol table the window station was created with."""
        template = winsta.vol.type_name
        try:
            station_type = winsta._context.symbol_space.get_type(template)
            sequence = -1
            if station_type.has_member("iClipSequenceNumber"):
                sequence = station_type.relative_child_offset("iClipSequenceNumber")
            clip_count = station_type.relative_child_offset("cNumClipFormats")
            if sequence == clip_count:
                # Some bundled tables list both fields at the same offset; do not trust either reading
                sequence = -1
            return StationLayout(
                "symbols",
                station_type.relative_child_offset("pClipBase"),
                clip_count,
                sequence,
                cls.SYMBOL_ENTRY_SIZE,
            )
        except (exceptions.SymbolError, AttributeError):
            return None

    @classmethod
    def get_station_clipboard(
        cls,
        layer: interfaces.layers.DataLayerInterface,
        winsta_offset: int,
        layouts: List[StationLayout],
    ) -> Optional[Tuple[StationLayout, int, Optional[int], List[ClipFormat]]]:
        """Reads the tagCLIP array of a window station.

        Args:
            layer: The (session) layer the window station lives in
            winsta_offset: The address of the tagWINDOWSTATION
            layouts: The candidate layouts, most specific first

        Returns:
            The layout that matched, the address of the tagCLIP array, the clipboard sequence
            number and the formats on the clipboard, or None if no layout fits
        """
        for layout in layouts:
            try:
                clip_base = struct.unpack(
                    "<Q", layer.read(winsta_offset + layout.clip_base, 8)
                )[0]
                count = struct.unpack(
                    "<I", layer.read(winsta_offset + layout.clip_count, 4)
                )[0]
                sequence = None
                if layout.sequence_number >= 0:
                    sequence = struct.unpack(
                        "<I", layer.read(winsta_offset + layout.sequence_number, 4)
                    )[0]
                if not clip_base or not 0 < count <= cls.MAX_FORMATS:
                    continue
                raw = layer.read(clip_base, count * layout.entry_size)
            except exceptions.InvalidAddressException:
                continue

            formats = []
            for index in range(count):
                fmt, handle = struct.unpack_from(
                    "<I 4x Q", raw, index * layout.entry_size
                )
                formats.append(ClipFormat(fmt, handle))
            if all(cls._is_valid_format(entry.fmt) for entry in formats):
                return layout, clip_base, sequence, formats
        return None

    @classmethod
    def _parse_clipdata(
        cls,
        layer: interfaces.layers.DataLayerInterface,
        offset: int,
        max_size: int,
    ) -> Optional[ClipData]:
        try:
            handle, _lock_count, size = struct.unpack(
                "<Q I 4x I", layer.read(offset, cls.CLIPDATA_DATA)
            )
        except exceptions.InvalidAddressException:
            return None
        # USER handles are a 16 bit table index plus a 16 bit uniqueness counter
        if not 0 < handle <= 0xFFFFFFFF or not handle & 0xFFFF:
            return None
        if not 0 < size <= max_size:
            return None
        return ClipData(offset, handle, size)

    @classmethod
    def scan_clipdata(
        cls,
        context: interfaces.context.ContextInterface,
        kernel_module_name: str,
        progress_callback=None,
    ) -> Iterator[ClipData]:
        """Finds tagCLIPDATA objects by their pool tag, in both the small and big pools.

        Args:
            context: The context to retrieve required elements (layers, symbol tables) from
            kernel_module_name: The name of the module for the kernel

        Returns:
            The clipboard data objects found
        """
        kernel = context.modules[kernel_module_name]
        layer = context.layers[kernel.layer_name]

        for tag_offset in layer.scan(
            context,
            scanners.BytesScanner(cls.CLIPDATA_TAG),
            progress_callback=progress_callback,
        ):
            header = tag_offset - cls.POOL_HEADER_TAG
            if header & 0xF:
                continue
            clipdata = cls._parse_clipdata(
                layer, header + cls.POOL_HEADER_SIZE, cls.MAX_SMALL_DATA
            )
            if clipdata is not None:
                yield clipdata

        # Allocations of a page or more have no pool header and are only tracked in the big pool table
        tag = cls.CLIPDATA_TAG.decode()
        for big_pool in bigpools.BigPools.list_big_pools(
            context, kernel_module_name, tags=[tag]
        ):
            allocation = big_pool.get_number_of_bytes()
            if isinstance(allocation, interfaces.renderers.BaseAbsentValue):
                continue
            clipdata = cls._parse_clipdata(layer, int(big_pool.Va), cls.MAX_DATA)
            if clipdata is not None and clipdata.size <= allocation:
                yield clipdata

    @staticmethod
    def _read_available(
        layer: interfaces.layers.DataLayerInterface, offset: int, size: int
    ) -> bytes:
        """Reads up to size bytes, stopping at the first unreadable page instead of padding."""
        data = b""
        while len(data) < size:
            chunk = min(size - len(data), 0x1000 - ((offset + len(data)) & 0xFFF))
            try:
                data += layer.read(offset + len(data), chunk)
            except exceptions.InvalidAddressException:
                break
        return data

    @classmethod
    def _decode_hdrop(cls, data: bytes) -> Optional[str]:
        """Decodes a DROPFILES structure followed by a double NUL terminated file list."""
        if len(data) < 20:
            return None
        files_offset, wide = struct.unpack_from("<I 12x I", data)
        if not 20 <= files_offset <= len(data):
            return None
        if wide:
            names = data[files_offset:].decode("utf-16-le", errors="replace")
        else:
            names = data[files_offset:].decode("latin-1")
        return "; ".join(name for name in names.split("\x00\x00")[0].split("\x00") if name)

    @classmethod
    def render_data(cls, fmt: Optional[int], data: bytes, limit: int) -> str:
        """Produces a printable representation of clipboard data.

        Args:
            fmt: The clipboard format, or None when it is not known (unreferenced objects)
            data: The bytes of the object that could be read
            limit: The maximum number of characters, or bytes of binary data, to render
        """
        text = None
        if fmt == 13:
            text = data[: len(data) & ~1].decode("utf-16-le", errors="replace")
        elif fmt in (1, 7, 0x81):
            text = data.decode("latin-1")
        elif fmt == 15:
            text = cls._decode_hdrop(data)
        elif fmt is None and len(data) >= 4 and not len(data) & 1:
            # Without a format, only claim text when it decodes cleanly as a terminated string
            try:
                candidate = data.decode("utf-16-le")
            except UnicodeDecodeError:
                candidate = ""
            body = candidate.rstrip("\x00")
            if len(body) > 1 and len(body) < len(candidate) and all(
                char.isprintable() or char in "\r\n\t" for char in body
            ):
                text = candidate

        if text is not None:
            text = text.split("\x00")[0] if fmt != 15 else text
            return text[:limit] if limit else text
        shown = data[:limit] if limit else data
        return shown.hex(" ")

    def _generator(self):
        kernel_module_name = self.config["kernel"]
        kernel = self.context.modules[kernel_module_name]
        kernel_layer = self.context.layers[kernel.layer_name]
        limit = self.config["data-limit"]

        clipdata_by_handle: Dict[int, List[ClipData]] = {}
        for clipdata in self.scan_clipdata(
            self.context, kernel_module_name, self._progress_callback
        ):
            clipdata_by_handle.setdefault(clipdata.handle, []).append(clipdata)

        used = set()
        arrays = set()

        def row(session, station, sequence, fmt, handle, clipdata):
            file_output = "Disabled"
            if clipdata is None:
                offset = size = renderers.NotApplicableValue()
                shown = self.DUMMY_HANDLES.get(handle, renderers.NotAvailableValue())
            else:
                offset = format_hints.Hex(clipdata.offset)
                size = clipdata.size
                data = self._read_available(
                    kernel_layer, clipdata.offset + self.CLIPDATA_DATA, clipdata.size
                )
                if len(data) < clipdata.size:
                    vollog.debug(
                        f"Clipboard data at {clipdata.offset:#x} truncated to {len(data)} of {clipdata.size} bytes"
                    )
                shown = self.render_data(fmt, data, limit)
                if self.config["dump"]:
                    file_name = f"clipboard.{clipdata.handle:#x}.{clipdata.offset:#x}.dat"
                    with self.open(file_name) as file_handle:
                        file_handle.write(data)
                        file_output = file_handle.preferred_filename
            return (
                0,
                (
                    session,
                    station,
                    sequence,
                    self.format_name(fmt) if fmt is not None else "Unknown",
                    format_hints.Hex(handle),
                    offset,
                    size,
                    shown,
                    file_output,
                ),
            )

        for (
            winsta,
            name,
            session_id,
        ) in windowstations.WindowStations.scan_window_stations(
            self.context, self.config_path, kernel_module_name
        ):
            layer = self.context.layers[winsta.vol.layer_name]
            layouts = list(self.LAYOUTS)
            symbol_layout = self.symbol_layout(winsta)
            if symbol_layout is not None:
                layouts.append(symbol_layout)
            result = self.get_station_clipboard(layer, winsta.vol.offset, layouts)
            if result is None:
                continue
            layout, clip_base, sequence, formats = result
            if sequence is None:
                sequence = renderers.NotAvailableValue()
            vollog.debug(
                f"Window station {name} (session {session_id}) at {winsta.vol.offset:#x} uses layout {layout.name}"
            )
            # The array shares the clipboard pool tag; scan results are not sign extended
            arrays.add(clip_base & kernel_layer.maximum_address)

            for entry in formats:
                # Handles are only unique within a session and the pool scan cannot tell sessions
                # apart, so when several objects share a handle value all of them are shown
                matches = clipdata_by_handle.get(entry.handle, [])
                if entry.handle in self.DUMMY_HANDLES or not matches:
                    yield row(session_id, name, sequence, entry.fmt, entry.handle, None)
                for clipdata in matches:
                    used.add(clipdata.offset)
                    yield row(
                        session_id, name, sequence, entry.fmt, entry.handle, clipdata
                    )

        # Objects no window station refers to: replaced or freed data that has not been reused yet
        for handle, matches in clipdata_by_handle.items():
            for clipdata in matches:
                if clipdata.offset in used or clipdata.offset in arrays:
                    continue
                yield row(
                    renderers.NotAvailableValue(),
                    renderers.NotAvailableValue(),
                    renderers.NotAvailableValue(),
                    None,
                    handle,
                    clipdata,
                )

    def run(self):
        return renderers.TreeGrid(
            [
                ("Session", int),
                ("WindowStation", str),
                ("Sequence", int),
                ("Format", str),
                ("Handle", format_hints.Hex),
                ("Object", format_hints.Hex),
                ("Size", int),
                ("Data", str),
                ("File output", str),
            ],
            self._generator(),
        )
