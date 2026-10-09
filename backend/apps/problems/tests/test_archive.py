import stat
import zipfile
from io import BytesIO

from django.test import SimpleTestCase

from backend.apps.problems.archive import ArchivePolicy, read_archive
from backend.apps.problems.errors import ProblemBundleError


def archive_with(entries: list[tuple[str | zipfile.ZipInfo, bytes]]) -> bytes:
    stream = BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, contents in entries:
            archive.writestr(name, contents)
    return stream.getvalue()


class BoundedArchiveReaderTests(SimpleTestCase):
    def test_reads_regular_files_without_writing_archive_paths(self) -> None:
        self.assertEqual(read_archive(archive_with([("nested/file.txt", b"safe")])) , {"nested/file.txt": b"safe"})

    def test_rejects_traversal_absolute_windows_and_duplicate_paths(self) -> None:
        for name in ("../escape", "/absolute", "C:/drive", "nested\\escape", "a//b"):
            with self.subTest(name=name), self.assertRaises(ProblemBundleError):
                read_archive(archive_with([(name, b"x")]))
        with self.assertRaises(ProblemBundleError):
            read_archive(archive_with([("a.txt", b"one"), ("A.TXT", b"two")]))

    def test_rejects_symlinks_and_special_unix_entries(self) -> None:
        for file_type in (stat.S_IFLNK, stat.S_IFIFO, stat.S_IFCHR):
            info = zipfile.ZipInfo("private/link")
            info.create_system = 3
            info.external_attr = (file_type | 0o777) << 16
            with self.subTest(file_type=file_type), self.assertRaises(ProblemBundleError):
                read_archive(archive_with([(info, b"target")]))

    def test_rejects_file_directory_collisions(self) -> None:
        with self.assertRaises(ProblemBundleError):
            read_archive(archive_with([("a", b"file"), ("a/b", b"child")]))

    def test_rejects_unsupported_compression_and_long_paths(self) -> None:
        stream = BytesIO()
        with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_BZIP2) as archive:
            archive.writestr("compressed", b"payload")
        with self.assertRaises(ProblemBundleError):
            read_archive(stream.getvalue())
        with self.assertRaises(ProblemBundleError):
            read_archive(archive_with([("a" * 1025, b"x")]))

    def test_rejects_archive_file_and_compression_bomb_limits(self) -> None:
        archive = archive_with([("large", b"x" * 1000)])
        with self.assertRaises(ProblemBundleError):
            read_archive(archive, policy=ArchivePolicy(max_archive_bytes=100))
        with self.assertRaises(ProblemBundleError):
            read_archive(archive, policy=ArchivePolicy(max_compression_ratio=2))
        with self.assertRaises(ProblemBundleError):
            read_archive(archive, policy=ArchivePolicy(max_file_bytes=100))
        with self.assertRaises(ProblemBundleError):
            read_archive(archive, policy=ArchivePolicy(max_total_uncompressed_bytes=100))

    def test_archive_policy_rejects_non_positive_limits(self) -> None:
        with self.assertRaises(ValueError):
            ArchivePolicy(max_entries=0)

    def test_rejects_encrypted_and_invalid_archives(self) -> None:
        encrypted = bytearray(archive_with([("file", b"data")]))
        local_header = encrypted.index(b"PK\x03\x04")
        local_flags = int.from_bytes(encrypted[local_header + 6:local_header + 8], "little") | 0x1
        encrypted[local_header + 6:local_header + 8] = local_flags.to_bytes(2, "little")
        central_header = encrypted.index(b"PK\x01\x02")
        central_flags = int.from_bytes(encrypted[central_header + 8:central_header + 10], "little") | 0x1
        encrypted[central_header + 8:central_header + 10] = central_flags.to_bytes(2, "little")
        with self.assertRaises(ProblemBundleError):
            read_archive(bytes(encrypted))
        with self.assertRaises(ProblemBundleError):
            read_archive(b"not a zip")
