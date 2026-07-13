"""Tests for project persistence, import and autosave recovery."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from app.core.page import Page, PageStatus
from app.core.project import Project, ProjectError


@pytest.fixture()
def sample_image(tmp_path: Path) -> Path:
    path = tmp_path / "scan.png"
    Image.new("RGB", (100, 140), "white").save(path)
    return path


class TestPage:
    def test_round_trip(self) -> None:
        page = Page(image_path=Path("pages/x.png"), source_name="x.png")
        page.status = PageStatus.EDITED
        restored = Page.from_dict(page.to_dict())
        assert restored.page_id == page.page_id
        assert restored.status is PageStatus.EDITED

    def test_from_dict_tolerates_garbage(self) -> None:
        page = Page.from_dict({"status": "bogus", "rotation": None})
        assert page.status is PageStatus.PENDING
        assert page.rotation == 0


class TestProject:
    def test_create_save_load(self, tmp_path: Path, sample_image: Path) -> None:
        project = Project.create(tmp_path / "p.adaproj", "P")
        project.import_files([sample_image])
        project.set_page_document(
            project.pages[0].page_id, "<p>hello</p>", edited_by_user=True
        )
        project.save()

        loaded = Project.load(tmp_path / "p.adaproj")
        assert len(loaded.pages) == 1
        assert loaded.pages[0].document_html == "<p>hello</p>"
        assert loaded.pages[0].status is PageStatus.EDITED

    def test_import_copies_files(self, tmp_path: Path, sample_image: Path) -> None:
        project = Project.create(tmp_path / "p.adaproj")
        project.import_files([sample_image])
        copied = project.pages[0].image_path
        assert copied.exists()
        assert copied != sample_image
        sample_image.unlink()  # original can vanish; project is unaffected
        assert project.pages[0].image_path.exists()

    def test_import_reports_unsupported(self, tmp_path: Path) -> None:
        bad = tmp_path / "notes.txt"
        bad.write_text("not an image")
        project = Project.create(tmp_path / "p.adaproj")
        with pytest.raises(ProjectError, match="unsupported"):
            project.import_files([bad])
        assert project.pages == []

    def test_remove_page(self, tmp_path: Path, sample_image: Path) -> None:
        project = Project.create(tmp_path / "p.adaproj")
        project.import_files([sample_image])
        page_id = project.pages[0].page_id
        image = project.pages[0].image_path
        assert project.remove_page(page_id)
        assert project.pages == []
        assert not image.exists()

    def test_load_missing(self, tmp_path: Path) -> None:
        with pytest.raises(ProjectError):
            Project.load(tmp_path / "nope")


class TestAutosaveRecovery:
    def test_snapshot_merge(self, tmp_path: Path, sample_image: Path) -> None:
        from app.core.autosave import apply_snapshot

        project = Project.create(tmp_path / "p.adaproj")
        project.import_files([sample_image])
        project.save()

        # Simulate unsaved work captured only in a snapshot.
        project.set_page_document(
            project.pages[0].page_id, "<p>unsaved</p>", edited_by_user=True
        )
        snapshot = tmp_path / "snap.json"
        project.save(target_file=snapshot)

        fresh = Project.load(tmp_path / "p.adaproj")
        assert fresh.pages[0].document_html == ""
        assert apply_snapshot(snapshot, fresh) == 1
        assert fresh.pages[0].document_html == "<p>unsaved</p>"
