"""Lightweight text extraction for Word and PowerPoint course materials."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import posixpath
import re
import shutil
import subprocess
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile


OFFICE_SUFFIXES = {".doc", ".docx", ".ppt", ".pptx"}
MAX_OFFICE_BYTES = 10 * 1024 * 1024
MAX_XML_BYTES = 24 * 1024 * 1024
MAX_SLIDES = 500
WORD_PARAGRAPH = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p"
WORD_TEXT = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t"
WORD_TAB = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}tab"
WORD_BREAK = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}br"
PRESENTATION_SLIDE = "{http://schemas.openxmlformats.org/presentationml/2006/main}sldId"
RELATIONSHIP_ID = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
DRAWING_TEXT = "{http://schemas.openxmlformats.org/drawingml/2006/main}t"


class OfficeDocumentError(ValueError):
    """The uploaded document is invalid or contains no readable text."""


class OfficeParserUnavailable(RuntimeError):
    """A required legacy Office text extractor is not installed."""


@dataclass(frozen=True)
class OfficeSection:
    text: str
    slide: int | None = None


def _xml_part(archive: ZipFile, name: str, remaining: list[int]) -> ElementTree.Element:
    info = archive.getinfo(name)
    if info.file_size > remaining[0]:
        raise OfficeDocumentError("This Office document is too large to process.")
    remaining[0] -= info.file_size
    with archive.open(info) as stream:
        return ElementTree.fromstring(stream.read(info.file_size + 1))


def _docx_sections(archive: ZipFile, remaining: list[int]) -> list[OfficeSection]:
    parts = ["word/document.xml"]
    parts.extend(sorted(name for name in archive.namelist() if re.fullmatch(
        r"word/(?:header|footer|footnotes|endnotes)\d*\.xml", name
    )))
    paragraphs = []
    for name in parts:
        root = _xml_part(archive, name, remaining)
        for paragraph in root.iter(WORD_PARAGRAPH):
            pieces = []
            for node in paragraph.iter():
                if node.tag == WORD_TEXT:
                    pieces.append(node.text or "")
                elif node.tag == WORD_TAB:
                    pieces.append("\t")
                elif node.tag == WORD_BREAK:
                    pieces.append("\n")
            line = "".join(pieces).strip()
            if line:
                paragraphs.append(line)
    return [OfficeSection("\n".join(paragraphs))] if paragraphs else []


def _pptx_slide_paths(archive: ZipFile, remaining: list[int]) -> list[str]:
    names = set(archive.namelist())
    presentation = _xml_part(archive, "ppt/presentation.xml", remaining)
    relationships = _xml_part(archive, "ppt/_rels/presentation.xml.rels", remaining)
    targets = {item.get("Id"): item.get("Target", "") for item in relationships}
    paths = []
    for slide in presentation.iter(PRESENTATION_SLIDE):
        target = targets.get(slide.get(RELATIONSHIP_ID), "")
        path = posixpath.normpath(
            target.lstrip("/") if target.startswith("/") else posixpath.join("ppt", target)
        )
        if path not in names or not re.fullmatch(r"ppt/slides/slide\d+\.xml", path):
            raise OfficeDocumentError("This PowerPoint file has a missing slide.")
        paths.append(path)
    if len(paths) > MAX_SLIDES:
        raise OfficeDocumentError("This PowerPoint has too many slides to process.")
    return paths


def _pptx_sections(archive: ZipFile, remaining: list[int]) -> list[OfficeSection]:
    sections = []
    names = set(archive.namelist())
    for number, path in enumerate(_pptx_slide_paths(archive, remaining), start=1):
        root = _xml_part(archive, path, remaining)
        text = "\n".join((node.text or "").strip() for node in root.iter(DRAWING_TEXT) if (node.text or "").strip())
        rels_path = posixpath.join(posixpath.dirname(path), "_rels", posixpath.basename(path) + ".rels")
        if rels_path in names:
            relationships = _xml_part(archive, rels_path, remaining)
            for relationship in relationships:
                if not relationship.get("Type", "").endswith("/notesSlide"):
                    continue
                target = relationship.get("Target", "")
                notes_path = posixpath.normpath(
                    target.lstrip("/") if target.startswith("/") else posixpath.join(posixpath.dirname(path), target)
                )
                if notes_path in names and re.fullmatch(r"ppt/notesSlides/notesSlide\d+\.xml", notes_path):
                    notes = _xml_part(archive, notes_path, remaining)
                    note_text = "\n".join((node.text or "").strip() for node in notes.iter(DRAWING_TEXT) if (node.text or "").strip())
                    if note_text:
                        text += f"\nSpeaker notes: {note_text}"
        if text:
            sections.append(OfficeSection(text, slide=number))
    return sections


def _legacy_sections(path: Path) -> list[OfficeSection]:
    command = "antiword" if path.suffix.lower() == ".doc" else "catppt"
    executable = shutil.which(command)
    if not executable:
        raise OfficeParserUnavailable(f"{command} is required to process legacy Office files. Export as DOCX or PPTX and upload again.")
    try:
        result = subprocess.run(
            [executable, "-t", str(path)] if command == "antiword" else [executable, "-d", "utf-8", str(path)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise OfficeDocumentError("The legacy Office file could not be read. Export as DOCX or PPTX and upload again.") from exc
    if result.returncode or len(result.stdout) > MAX_XML_BYTES:
        raise OfficeDocumentError("The legacy Office file could not be read. Export as DOCX or PPTX and upload again.")
    text = result.stdout.decode("utf-8", errors="replace").strip()
    if command == "catppt":
        return [OfficeSection(slide.strip(), slide=number) for number, slide in enumerate(text.split("\f"), 1) if slide.strip()]
    return [OfficeSection(text)] if text else []


def parse_office_document(path: Path) -> list[OfficeSection]:
    """Extract indexable text without running document macros or conversion scripts."""
    suffix = path.suffix.lower()
    if suffix not in OFFICE_SUFFIXES:
        raise OfficeDocumentError("Upload a Word or PowerPoint document.")
    if path.stat().st_size > MAX_OFFICE_BYTES:
        raise OfficeDocumentError("Documents must be 10 MB or smaller.")
    if suffix in {".doc", ".ppt"}:
        sections = _legacy_sections(path)
    else:
        try:
            with ZipFile(path) as archive:
                remaining = [MAX_XML_BYTES]
                sections = _docx_sections(archive, remaining) if suffix == ".docx" else _pptx_sections(archive, remaining)
        except (BadZipFile, KeyError, ElementTree.ParseError, RuntimeError) as exc:
            raise OfficeDocumentError("The Office file could not be read. Upload a valid, unencrypted DOCX or PPTX file.") from exc
    if not sections:
        raise OfficeDocumentError("No readable text was found in this Office file. Images and scanned slides need OCR first.")
    return sections
