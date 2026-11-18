import io
import tarfile
import zipfile

import pytest

from pia.services.archive import ArchiveError, SafeArchiveInspector, safe_member_path


def _tar(path, entries):
    with tarfile.open(path, "w:gz") as tf:
        for e in entries:
            info = tarfile.TarInfo(e["name"])
            if e.get("type") == "sym":
                info.type, info.linkname = tarfile.SYMTYPE, e["target"]
                tf.addfile(info)
            elif e.get("type") == "hard":
                info.type, info.linkname = tarfile.LNKTYPE, e["target"]
                tf.addfile(info)
            elif e.get("type") == "fifo":
                info.type = tarfile.FIFOTYPE
                tf.addfile(info)
            else:
                data = e.get("data", b"x")
                info.size = len(data)
                tf.addfile(info, io.BytesIO(data))
    return path


@pytest.mark.parametrize("name", ["../evil", "/etc/passwd", "a/../../b", "C:/win.ini", "..\\..\\x", "ok\x00bad"])
def test_unsafe_member_names_rejected(name):
    assert safe_member_path(name) is None


def test_safe_member_names_normalised():
    assert safe_member_path("./pkg/./a.py") == "pkg/a.py"


def test_tar_path_traversal_is_rejected_and_not_written(tmp_path, settings):
    arc = _tar(tmp_path / "a.tar.gz", [{"name": "pkg/ok.py"}, {"name": "../../escape.sh", "data": b"boom"}])
    out = tmp_path / "out"
    rep = SafeArchiveInspector(settings.limits).extract(arc, out)
    assert rep.files == ["pkg/ok.py"]
    assert [r.kind for r in rep.rejected] == ["path_traversal"]
    assert not (tmp_path / "escape.sh").exists()


def test_symlinks_hardlinks_and_special_files_rejected(tmp_path, settings):
    arc = _tar(tmp_path / "a.tar.gz", [
        {"name": "pkg/a.py"}, {"name": "pkg/link", "type": "sym", "target": "/etc/passwd"},
        {"name": "pkg/inner", "type": "sym", "target": "a.py"}, {"name": "pkg/hard", "type": "hard", "target": "pkg/a.py"},
        {"name": "pkg/pipe", "type": "fifo"}])
    rep = SafeArchiveInspector(settings.limits).extract(arc, tmp_path / "out")
    kinds = sorted(r.kind for r in rep.rejected)
    assert kinds == ["hardlink", "special_file", "symlink", "symlink_escape"]
    assert not (tmp_path / "out" / "pkg" / "link").exists()


def test_duplicate_members_rejected(tmp_path, settings):
    arc = _tar(tmp_path / "a.tar.gz", [{"name": "pkg/a.py", "data": b"one"}, {"name": "pkg/a.py", "data": b"two"}])
    rep = SafeArchiveInspector(settings.limits).extract(arc, tmp_path / "out")
    assert (tmp_path / "out/pkg/a.py").read_bytes() == b"one"
    assert rep.rejected[0].kind == "duplicate"


def test_per_file_and_total_size_limits(tmp_path, settings):
    arc = _tar(tmp_path / "a.tar.gz", [{"name": "big.bin", "data": b"0" * 5000}, {"name": "small.txt", "data": b"s"}])
    rep = SafeArchiveInspector(settings.with_limits(max_file_bytes=1000).limits).extract(arc, tmp_path / "o1")
    assert rep.files == ["small.txt"] and rep.rejected[0].kind == "oversize"
    with pytest.raises(ArchiveError):
        SafeArchiveInspector(settings.with_limits(max_extract_bytes=100).limits).extract(arc, tmp_path / "o2")


def test_file_count_limit(tmp_path, settings):
    arc = _tar(tmp_path / "a.tar.gz", [{"name": f"f{i}.txt"} for i in range(20)])
    with pytest.raises(ArchiveError):
        SafeArchiveInspector(settings.with_limits(max_files=5).limits).extract(arc, tmp_path / "o")


def test_file_type_validation(tmp_path, settings):
    fake = tmp_path / "pkg.whl"
    fake.write_bytes(b"\x1f\x8b" + b"0" * 100)
    with pytest.raises(ArchiveError, match="mismatch"):
        SafeArchiveInspector(settings.limits).extract(fake, tmp_path / "o")
    junk = tmp_path / "pkg.tar.gz"
    junk.write_bytes(b"#!/bin/sh\necho hi\n")
    with pytest.raises(ArchiveError, match="unrecognised"):
        SafeArchiveInspector(settings.limits).extract(junk, tmp_path / "o2")


def test_zip_symlink_traversal_and_bomb(tmp_path, settings):
    arc = tmp_path / "a.whl"
    with zipfile.ZipFile(arc, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("pkg/ok.py", "x = 1\n")
        zf.writestr("../evil.py", "boom")
        link = zipfile.ZipInfo("pkg/link")
        link.external_attr = (0o120777 << 16)
        zf.writestr(link, "/etc/shadow")
        zf.writestr("pkg/bomb.txt", "0" * 3_000_000)
    rep = SafeArchiveInspector(settings.limits).extract(arc, tmp_path / "o")
    assert rep.files == ["pkg/ok.py"]
    assert sorted(r.kind for r in rep.rejected) == ["path_traversal", "symlink_escape", "zip_bomb"]


def test_extracted_files_are_not_executable(tmp_path, settings):
    arc = tmp_path / "a.tar.gz"
    with tarfile.open(arc, "w:gz") as tf:
        info = tarfile.TarInfo("run.sh")
        info.mode, info.size = 0o4755, 4
        tf.addfile(info, io.BytesIO(b"echo"))
    SafeArchiveInspector(settings.limits).extract(arc, tmp_path / "o")
    assert (tmp_path / "o/run.sh").stat().st_mode & 0o7111 == 0
