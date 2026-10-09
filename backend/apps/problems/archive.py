"""Bounded ZIP reader that never extracts archive paths to the host filesystem."""

from __future__ import annotations

import io
import stat
import zipfile
import zlib
from dataclasses import dataclass
from pathlib import PurePosixPath

from .errors import ProblemBundleError


@dataclass(frozen=True, slots=True)
class ArchivePolicy:
    max_archive_bytes: int = 16 * 1024 * 1024
    max_entries: int = 4096
    max_file_bytes: int = 8 * 1024 * 1024
    max_total_uncompressed_bytes: int = 64 * 1024 * 1024
    max_compression_ratio: int = 100

    def __post_init__(self) -> None:
        values = (
            self.max_archive_bytes,
            self.max_entries,
            self.max_file_bytes,
            self.max_total_uncompressed_bytes,
            self.max_compression_ratio,
        )
        if any(not isinstance(value, int) or isinstance(value, bool) or value <= 0 for value in values):
            raise ValueError("archive policy limits must be positive integers")


DEFAULT_ARCHIVE_POLICY = ArchivePolicy()
READ_CHUNK_BYTES = 64 * 1024
MAX_MEMBER_NAME_BYTES = 1024
MAX_PATH_DEPTH = 32


def _safe_member_name(info: zipfile.ZipInfo) -> tuple[str, bool]:
    original_name = getattr(info, "orig_filename", info.filename)
    is_directory = info.is_dir()
    if (
        not original_name
        or "\x00" in original_name
        or "\\" in original_name
        or original_name.startswith("/")
    ):
        raise ProblemBundleError("archive contains an unsafe path")
    try:
        if len(original_name.encode("utf-8", errors="strict")) > MAX_MEMBER_NAME_BYTES:
            raise ProblemBundleError("archive path exceeds its size limit")
    except UnicodeEncodeError as error:
        raise ProblemBundleError("archive path is not valid Unicode") from error

    raw_path = original_name[:-1] if is_directory and original_name.endswith("/") else original_name
    parts = raw_path.split("/")
    path = PurePosixPath(raw_path)
    if (
        path.is_absolute()
        or not parts
        or any(part in {"", ".", ".."} for part in parts)
        or len(parts) > MAX_PATH_DEPTH
        or (parts and ":" in parts[0])
        or path.as_posix() != raw_path
    ):
        raise ProblemBundleError("archive contains an unsafe path")

    if info.create_system == 3:
        mode = info.external_attr >> 16
        file_type = stat.S_IFMT(mode)
        allowed_types = {0, stat.S_IFREG, stat.S_IFDIR}
        if file_type not in allowed_types:
            raise ProblemBundleError("archive contains a link or special filesystem entry")
        if file_type == stat.S_IFDIR and not is_directory:
            raise ProblemBundleError("archive entry type does not match its path")
        if file_type == stat.S_IFREG and is_directory:
            raise ProblemBundleError("archive entry type does not match its path")

    if info.flag_bits & 0x1:
        raise ProblemBundleError("encrypted archive entries are not supported")
    return path.as_posix(), is_directory


def read_archive(
    archive_bytes: bytes,
    *,
    policy: ArchivePolicy = DEFAULT_ARCHIVE_POLICY,
) -> dict[str, bytes]:
    """Read regular ZIP files into a bounded mapping; no archive-controlled write occurs."""
    if not isinstance(archive_bytes, bytes) or not archive_bytes:
        raise ProblemBundleError("archive is empty or not bytes")
    if len(archive_bytes) > policy.max_archive_bytes:
        raise ProblemBundleError("archive exceeds its compressed-size limit")

    try:
        archive = zipfile.ZipFile(io.BytesIO(archive_bytes), mode="r")
    except (zipfile.BadZipFile, OSError) as error:
        raise ProblemBundleError("archive is not a valid ZIP file") from error

    files: dict[str, bytes] = {}
    entry_types_casefolded: dict[str, bool] = {}
    descendant_paths: set[str] = set()
    total_uncompressed = 0
    with archive:
        infos = archive.infolist()
        if not infos or len(infos) > policy.max_entries:
            raise ProblemBundleError("archive has an invalid number of entries")

        for info in infos:
            name, is_directory = _safe_member_name(info)
            if info.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}:
                raise ProblemBundleError("archive compression method is not supported")
            name_key = name.casefold()
            if name_key in entry_types_casefolded:
                raise ProblemBundleError("archive contains duplicate paths")
            for parent in PurePosixPath(name).parents:
                if parent == PurePosixPath("."):
                    continue
                parent_key = parent.as_posix().casefold()
                if entry_types_casefolded.get(parent_key) is False:
                    raise ProblemBundleError("archive file is also used as a directory")
                descendant_paths.add(parent_key)
            if not is_directory and name_key in descendant_paths:
                raise ProblemBundleError("archive file is also used as a directory")
            entry_types_casefolded[name_key] = is_directory

            if is_directory:
                if info.file_size != 0 or info.compress_size != 0:
                    raise ProblemBundleError("archive directory entry contains data")
                continue
            if info.file_size < 0 or info.file_size > policy.max_file_bytes:
                raise ProblemBundleError("archive file exceeds its size limit")
            if info.compress_size < 0:
                raise ProblemBundleError("archive has an invalid compressed size")
            if info.file_size and (
                info.compress_size == 0
                or info.file_size > info.compress_size * policy.max_compression_ratio
            ):
                raise ProblemBundleError("archive file exceeds its compression-ratio limit")
            if total_uncompressed + info.file_size > policy.max_total_uncompressed_bytes:
                raise ProblemBundleError("archive exceeds its total uncompressed-size limit")

            data = bytearray()
            try:
                with archive.open(info, mode="r") as member:
                    while True:
                        chunk = member.read(min(READ_CHUNK_BYTES, policy.max_file_bytes - len(data) + 1))
                        if not chunk:
                            break
                        data.extend(chunk)
                        if len(data) > policy.max_file_bytes:
                            raise ProblemBundleError("archive file exceeds its size limit")
            except (EOFError, NotImplementedError, OSError, RuntimeError, zipfile.BadZipFile, zlib.error) as error:
                raise ProblemBundleError("archive entry cannot be read safely") from error
            if len(data) != info.file_size:
                raise ProblemBundleError("archive entry size does not match its directory record")
            total_uncompressed += len(data)
            files[name] = bytes(data)

    return files
