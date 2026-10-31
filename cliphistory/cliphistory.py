# Copyright (c) 2026 GyuBin Kim (ws1004)
# Licensed under the MIT License. See the LICENSE file in the repository root for details.
#
import contextlib
import datetime
import hashlib
import logging
import struct
import uuid
from typing import Dict, Iterator, List, NamedTuple, Optional, Tuple

from volatility3.framework import exceptions, interfaces, renderers
from volatility3.framework.configuration import requirements
from volatility3.framework.renderers import conversion, format_hints
from volatility3.plugins.windows import pslist

vollog = logging.getLogger(__name__)


class HistoryItem(NamedTuple):
    offset: int
    item_id: str
    timestamp: int
    formats: List[str]
    text: Optional[str]


class CarvedImage(NamedTuple):
    offset: int
    kind: str
    width: int
    height: int
    depth: int
    data: bytes


class ClipboardHistory(interfaces.plugins.PluginInterface):
    """Recovers clipboard history (Win+V) items from the Clipboard User Service (cbdhsvc)."""

    _required_framework_version = (2, 0, 0)
    _version = (1, 0, 0)

    SERVICE_DLL = "cbdhsvc.dll"
    DATATRANSFER_DLL = "windows.applicationmodel.datatransfer.dll"

    # Object layouts recovered on Windows 11 25H2 (26200.9457), cbdhsvc.dll 10.0.26100.8117 and
    # windows.applicationmodel.datatransfer.dll 10.0.26100.1. None of these types are in public
    # PDBs, so the offsets must be re-checked on other builds.
    #
    # CBDHSvc!ClipboardHistoryItemInternal
    ITEM_VFTABLES = 3  # consecutive vftable pointers at the start of the object
    ITEM_ID = 0x40  # GUID
    ITEM_TIMESTAMP = 0x50  # FILETIME
    ITEM_PACKAGE = 0x60  # CDataPackage *
    ITEM_SIZE = 0x68
    # windows_applicationmodel_datatransfer!CDataPackage
    PACKAGE_FORMATS = 0xE0  # array of format object pointers
    PACKAGE_FORMAT_COUNT = 0xE8
    # CUnicodeTextFormat / CHtmlTextFormat / CStreamFormat / CGlobalMemoryFormat
    FORMAT_NAME = 0x08  # HSTRING
    FORMAT_TEXT = 0x18  # CUnicodeTextFormat only: NUL terminated UTF-16
    # HSTRING header
    HSTRING_LENGTH = 0x04
    HSTRING_BUFFER = 0x10

    MAX_FORMATS = 64
    MAX_FORMAT_NAME = 256
    MAX_TEXT_BYTES = 4 * 1024 * 1024  # clipboard history ignores items above 4 MB
    MIN_TIMESTAMP = 0x01D0000000000000  # 2014
    MAX_TIMESTAMP = 0x01F0000000000000  # 2053
    SCAN_CHUNK = 0x400000
    MAX_VAD_SIZE = 0x40000000

    # Image items keep their pixels behind nested, undocumented property maps that could not be
    # tied back to an item reliably, so the images are carved from the same memory by signature.
    PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
    PNG_END = b"IEND\xaeB`\x82"
    DIB_HEADER = b"\x28\x00\x00\x00"  # BITMAPINFOHEADER.biSize
    DIB_HEADER_SIZE = 0x28
    DIB_DEPTHS = (1, 4, 8, 16, 24, 32)
    MAX_IMAGE_BYTES = 64 * 1024 * 1024
    MAX_IMAGE_DIMENSION = 20000

    @classmethod
    def get_requirements(cls) -> List[interfaces.configuration.RequirementInterface]:
        return [
            requirements.ModuleRequirement(
                name="kernel",
                description="Windows kernel",
                architectures=["Intel64"],
            ),
            requirements.VersionRequirement(
                name="pslist", component=pslist.PsList, version=(3, 0, 0)
            ),
            requirements.ListRequirement(
                name="pid",
                element_type=int,
                description="Process IDs to include (all other processes are excluded)",
                optional=True,
            ),
            requirements.IntRequirement(
                name="text-limit",
                description="Maximum number of characters of text to display per item (0 for no limit)",
                default=256,
                optional=True,
            ),
            requirements.BooleanRequirement(
                name="dump",
                description="Write the complete text of each item to a file, and carve the clipboard images (PNG and DIB) to files",
                default=False,
                optional=True,
            ),
        ]

    @classmethod
    def _module_ranges(
        cls, proc: interfaces.objects.ObjectInterface
    ) -> Dict[str, Tuple[int, int]]:
        """Returns the address range of each loaded module, keyed by lower case name."""
        ranges = {}
        for entry in proc.load_order_modules():
            with contextlib.suppress(exceptions.InvalidAddressException):
                name = entry.BaseDllName.get_string().lower()
                base = int(entry.DllBase)
                ranges[name] = (base, base + int(entry.SizeOfImage))
        return ranges

    @staticmethod
    def _read_pointer(
        layer: interfaces.layers.DataLayerInterface, offset: int
    ) -> Optional[int]:
        try:
            return struct.unpack("<Q", layer.read(offset, 8))[0]
        except exceptions.InvalidAddressException:
            return None

    @classmethod
    def _read_hstring(
        cls, layer: interfaces.layers.DataLayerInterface, offset: Optional[int]
    ) -> Optional[str]:
        if not offset:
            return None
        try:
            length = struct.unpack("<I", layer.read(offset + cls.HSTRING_LENGTH, 4))[0]
            if length > cls.MAX_FORMAT_NAME:
                return None
            buffer = struct.unpack("<Q", layer.read(offset + cls.HSTRING_BUFFER, 8))[0]
            return layer.read(buffer, length * 2).decode("utf-16-le")
        except (exceptions.InvalidAddressException, UnicodeDecodeError):
            return None

    @classmethod
    def _read_wide_string(
        cls, layer: interfaces.layers.DataLayerInterface, offset: Optional[int]
    ) -> Optional[str]:
        """Reads a NUL terminated UTF-16 string, stopping early at the first unreadable page."""
        if not offset:
            return None
        data = b""
        while len(data) < cls.MAX_TEXT_BYTES:
            # Read up to the next page boundary so an unreadable page only truncates the text
            size = 0x1000 - ((offset + len(data)) & 0xFFF)
            try:
                page = layer.read(offset + len(data), size)
            except exceptions.InvalidAddressException:
                break
            data += page
            for index in range(len(data) - len(page) & ~1, len(data) - 1, 2):
                if data[index] == 0 and data[index + 1] == 0:
                    return data[:index].decode("utf-16-le", errors="replace")
        return data[: len(data) & ~1].decode("utf-16-le", errors="replace") or None

    @classmethod
    def _parse_item(
        cls,
        layer: interfaces.layers.DataLayerInterface,
        offset: int,
        raw: bytes,
        datatransfer: Tuple[int, int],
    ) -> Optional[HistoryItem]:
        timestamp, package = struct.unpack_from("<Q8xQ", raw, cls.ITEM_TIMESTAMP)
        if not cls.MIN_TIMESTAMP < timestamp < cls.MAX_TIMESTAMP:
            return None
        vftable = cls._read_pointer(layer, package)
        if vftable is None or not datatransfer[0] <= vftable < datatransfer[1]:
            return None

        item_id = uuid.UUID(bytes_le=raw[cls.ITEM_ID : cls.ITEM_ID + 16])
        formats: List[str] = []
        text = None
        array = cls._read_pointer(layer, package + cls.PACKAGE_FORMATS)
        count = cls._read_pointer(layer, package + cls.PACKAGE_FORMAT_COUNT)
        if array and count and count <= cls.MAX_FORMATS:
            for index in range(count):
                fmt = cls._read_pointer(layer, array + index * 8)
                if not fmt:
                    continue
                name = cls._read_hstring(
                    layer, cls._read_pointer(layer, fmt + cls.FORMAT_NAME)
                )
                if name is None:
                    continue
                formats.append(name)
                if name == "Text" and text is None:
                    text = cls._read_wide_string(
                        layer, cls._read_pointer(layer, fmt + cls.FORMAT_TEXT)
                    )
        return HistoryItem(
            offset, "{%s}" % str(item_id).upper(), timestamp, formats, text
        )

    @classmethod
    def scan_history_items(
        cls,
        context: interfaces.context.ContextInterface,
        proc: interfaces.objects.ObjectInterface,
    ) -> Iterator[HistoryItem]:
        """Scans the private memory of a cbdhsvc host process for clipboard history items.

        Items are found by their shape (vftables inside cbdhsvc.dll, a plausible timestamp and a
        data package implemented by the data transfer DLL) rather than through the heap, so
        freed items that have not been overwritten yet are returned as well.

        Args:
            context: The context to retrieve required elements (layers, symbol tables) from
            proc: The process hosting the Clipboard User Service

        Returns:
            The clipboard history items found in the process
        """
        modules = cls._module_ranges(proc)
        service = modules.get(cls.SERVICE_DLL)
        datatransfer = modules.get(cls.DATATRANSFER_DLL)
        if service is None or datatransfer is None:
            return None

        layer = context.layers[proc.add_process_layer()]
        seen = set()

        for chunk_start, _end, data in cls._private_chunks(proc, layer, cls.ITEM_SIZE):
            for position in range(0, len(data) - cls.ITEM_SIZE + 1, 16):
                vftables = struct.unpack_from(f"<{cls.ITEM_VFTABLES}Q", data, position)
                if not all(service[0] <= vftable < service[1] for vftable in vftables):
                    continue
                offset = chunk_start + position
                if offset in seen:
                    continue
                seen.add(offset)
                item = cls._parse_item(
                    layer,
                    offset,
                    data[position : position + cls.ITEM_SIZE],
                    datatransfer,
                )
                if item is not None:
                    yield item

    @classmethod
    def _private_chunks(
        cls,
        proc: interfaces.objects.ObjectInterface,
        layer: interfaces.layers.DataLayerInterface,
        overlap: int,
    ) -> Iterator[Tuple[int, int, bytes]]:
        """Yields the non empty chunks of a process's private memory as (start, VAD end, data).

        Consecutive chunks overlap by the given number of bytes so a structure crossing a
        chunk boundary is still seen whole.
        """
        for vad in proc.get_vad_root().traverse():
            if not vad.get_private_memory():
                continue
            start, end = vad.get_start(), vad.get_end() + 1
            if end - start > cls.MAX_VAD_SIZE:
                vollog.debug(
                    f"Skipping oversized VAD {start:#x}-{end:#x} in PID {proc.UniqueProcessId}"
                )
                continue

            for chunk_start in range(start, end, cls.SCAN_CHUNK):
                size = min(cls.SCAN_CHUNK + overlap, end - chunk_start)
                data = layer.read(chunk_start, size, pad=True)
                if data.strip(b"\x00"):
                    yield chunk_start, end, data

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
    def _parse_dib(
        cls, data: bytes, position: int
    ) -> Optional[Tuple[int, int, int, int, int]]:
        """Validates a BITMAPINFOHEADER.

        Returns:
            (width, height, depth, offset of the pixels, size of header + palette + pixels)
        """
        if position + cls.DIB_HEADER_SIZE > len(data):
            return None
        _size, width, height, planes, depth, compression = struct.unpack_from(
            "<IiiHHI", data, position
        )
        if planes != 1 or depth not in cls.DIB_DEPTHS:
            return None
        if not 0 < width <= cls.MAX_IMAGE_DIMENSION:
            return None
        if not 0 < abs(height) <= cls.MAX_IMAGE_DIMENSION:
            return None
        if compression not in (0, 3):  # BI_RGB or BI_BITFIELDS
            return None
        pixels = ((width * depth + 31) // 32) * 4 * abs(height)
        palette = (1 << depth) * 4 if depth <= 8 else 0
        size = cls.DIB_HEADER_SIZE + palette + pixels
        if size > cls.MAX_IMAGE_BYTES:
            return None
        return width, abs(height), depth, cls.DIB_HEADER_SIZE + palette, size

    @classmethod
    def carve_images(
        cls,
        context: interfaces.context.ContextInterface,
        proc: interfaces.objects.ObjectInterface,
    ) -> Iterator[CarvedImage]:
        """Carves PNG and DIB images from the private memory of a cbdhsvc host process.

        DIBs are returned as complete .bmp files. Identical images are only returned once.

        Args:
            context: The context to retrieve required elements (layers, symbol tables) from
            proc: The process hosting the Clipboard User Service

        Returns:
            The images found in the process
        """
        if cls.SERVICE_DLL not in cls._module_ranges(proc):
            return None

        layer = context.layers[proc.add_process_layer()]
        seen = set()

        for chunk_start, end, data in cls._private_chunks(proc, layer, 0x1000):
            found = []
            position = data.find(cls.PNG_SIGNATURE)
            while position != -1:
                offset = chunk_start + position
                tail = data.find(cls.PNG_END, position)
                if tail != -1:
                    blob = data[position : tail + len(cls.PNG_END)]
                else:
                    # The end of the image is past this chunk
                    blob = cls._read_available(
                        layer, offset, min(cls.MAX_IMAGE_BYTES, end - offset)
                    )
                    tail = blob.find(cls.PNG_END)
                    blob = blob[: tail + len(cls.PNG_END)] if tail != -1 else b""
                if len(blob) >= 24:
                    width, height = struct.unpack_from(">II", blob, 16)
                    found.append(CarvedImage(offset, "PNG", width, height, 32, blob))
                position = data.find(cls.PNG_SIGNATURE, position + 8)

            position = data.find(cls.DIB_HEADER)
            while position != -1:
                parsed = cls._parse_dib(data, position)
                if parsed is not None:
                    width, height, depth, pixel_offset, size = parsed
                    offset = chunk_start + position
                    dib = cls._read_available(layer, offset, min(size, end - offset))
                    if len(dib) == size:
                        # Prepend a BITMAPFILEHEADER so the image opens as a .bmp file
                        header = b"BM" + struct.pack(
                            "<IHHI", 14 + size, 0, 0, 14 + pixel_offset
                        )
                        found.append(
                            CarvedImage(offset, "DIB", width, height, depth, header + dib)
                        )
                position = data.find(cls.DIB_HEADER, position + 4)

            for image in found:
                digest = hashlib.sha1(image.data).digest()
                if digest not in seen:
                    seen.add(digest)
                    yield image

    def _generator(self, procs):
        limit = self.config["text-limit"]
        for proc in procs:
            pid = proc.UniqueProcessId
            try:
                name = proc.ImageFileName.cast(
                    "string", max_length=proc.ImageFileName.vol.count, errors="replace"
                )
                items = sorted(
                    self.scan_history_items(self.context, proc),
                    key=lambda item: item.timestamp,
                )
            except exceptions.InvalidAddressException as excp:
                vollog.debug(f"Unable to scan PID {pid}: {excp}")
                continue

            for item in items:
                text = item.text
                file_output = "Disabled"
                if text is None:
                    shown = renderers.NotAvailableValue()
                    length = renderers.NotAvailableValue()
                else:
                    length = len(text)
                    shown = text[:limit] if limit else text
                    if self.config["dump"]:
                        file_name = f"cliphistory.{pid}.{item.offset:#x}.txt"
                        with self.open(file_name) as file_handle:
                            file_handle.write(text.encode("utf-8"))
                            file_output = file_handle.preferred_filename

                yield (
                    0,
                    (
                        pid,
                        name,
                        format_hints.Hex(item.offset),
                        conversion.wintime_to_datetime(item.timestamp),
                        item.item_id,
                        ", ".join(item.formats) or renderers.NotAvailableValue(),
                        length,
                        shown,
                        file_output,
                    ),
                )

            if not self.config["dump"] or not items:
                continue

            # Carved images cannot be tied to an item, so they are listed after the items under
            # their own offset; match them to the Bitmap items by size and content
            try:
                images = list(self.carve_images(self.context, proc))
            except exceptions.InvalidAddressException as excp:
                vollog.debug(f"Unable to carve images from PID {pid}: {excp}")
                continue

            for image in images:
                extension = "png" if image.kind == "PNG" else "bmp"
                file_name = f"cliphistory.{pid}.{image.offset:#x}.{extension}"
                with self.open(file_name) as file_handle:
                    file_handle.write(image.data)
                    file_output = file_handle.preferred_filename

                yield (
                    0,
                    (
                        pid,
                        name,
                        format_hints.Hex(image.offset),
                        renderers.NotAvailableValue(),
                        renderers.NotAvailableValue(),
                        f"{image.kind} image",
                        renderers.NotApplicableValue(),
                        f"{image.width}x{image.height}, {image.depth} bpp, {len(image.data)} bytes",
                        file_output,
                    ),
                )

    def run(self):
        filter_func = pslist.PsList.create_pid_filter(self.config.get("pid", None))

        return renderers.TreeGrid(
            [
                ("PID", int),
                ("Process", str),
                ("Offset", format_hints.Hex),
                ("Timestamp", datetime.datetime),
                ("ItemId", str),
                ("Formats", str),
                ("Length", int),
                ("Text", str),
                ("File output", str),
            ],
            self._generator(
                pslist.PsList.list_processes(
                    context=self.context,
                    kernel_module_name=self.config["kernel"],
                    filter_func=filter_func,
                )
            ),
        )
