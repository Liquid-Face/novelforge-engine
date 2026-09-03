"""
Export-phase tools: LaTeX typesetting and ePub packaging. No art/illustration
step -- text only, per project requirements.
"""
from __future__ import annotations
import shutil
import subprocess
import zipfile
from pathlib import Path
from novelforge.project import ProjectLayout

_LATEX_TEMPLATE = r"""\documentclass[11pt]{book}
\usepackage[T1,T2A]{fontenc}
\usepackage[russian,english]{babel}
\usepackage{geometry}
\geometry{paperwidth=%(width)s, paperheight=%(height)s, margin=2cm}
\title{%(title)s}
\author{}
\date{}
\begin{document}
\maketitle
%(body)s
\end{document}
"""


def _escape_tex(text: str) -> str:
    replacements = {"&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_"}
    for k, v in replacements.items():
        text = text.replace(k, v)
    return text


def build_tex(layout: ProjectLayout) -> Path:
    cfg = layout.config.project
    body_parts = []
    for i in range(1, cfg.chapters_total + 1):
        p = layout.chapter_path(i)
        if not p.exists():
            continue
        chapter_text = _escape_tex(layout.read(p))
        paragraphs = "\n\n".join(chapter_text.split("\n\n"))
        body_parts.append(f"\\chapter*{{Глава {i}}}\n{paragraphs}")
    body = "\n\n".join(body_parts)
    width, height = cfg.__dict__.get("chapter_length_words", None), None
    tex = _LATEX_TEMPLATE % {
        "width": layout.config.export.trim_size.split("x")[0],
        "height": layout.config.export.trim_size.split("x")[1],
        "title": _escape_tex(cfg.title),
        "body": body,
    }
    out_path = layout.export_dir / "novel.tex"
    layout.export_dir.mkdir(parents=True, exist_ok=True)
    out_path.write_text(tex, encoding="utf-8")
    return out_path


def typeset_pdf(layout: ProjectLayout) -> Path | None:
    tex_path = layout.export_dir / "novel.tex"
    engine = layout.config.export.typeset_engine
    binary = shutil.which(engine) or shutil.which("pdflatex")
    if not binary:
        return None
    subprocess.run([binary, "-interaction=nonstopmode", tex_path.name], cwd=str(layout.export_dir), check=False)
    pdf_path = layout.export_dir / "novel.pdf"
    return pdf_path if pdf_path.exists() else None


def build_epub(layout: ProjectLayout) -> Path:
    """Minimal, dependency-free EPUB3 packager (no external tool required)."""
    cfg = layout.config.project
    epub_path = layout.export_dir / "novel.epub"
    layout.export_dir.mkdir(parents=True, exist_ok=True)

    chapters_xhtml = []
    for i in range(1, cfg.chapters_total + 1):
        p = layout.chapter_path(i)
        if not p.exists():
            continue
        text = layout.read(p)
        paragraphs = "".join(f"<p>{line}</p>" for line in text.split("\n\n") if line.strip())
        chapters_xhtml.append((f"chapter{i}.xhtml",
            f"<?xml version='1.0' encoding='utf-8'?><html xmlns='http://www.w3.org/1999/xhtml'>"
            f"<head><title>Глава {i}</title></head><body><h1>Глава {i}</h1>{paragraphs}</body></html>"))

    with zipfile.ZipFile(epub_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("mimetype", "application/epub+zip", zipfile.ZIP_STORED)
        z.writestr("META-INF/container.xml",
            "<?xml version='1.0'?><container version='1.0' xmlns='urn:oasis:names:tc:opendocument:xmlns:container'>"
            "<rootfiles><rootfile full-path='OEBPS/content.opf' media-type='application/oebps-package+xml'/></rootfiles>"
            "</container>")
        manifest_items = "".join(
            f"<item id='c{i}' href='{fn}' media-type='application/xhtml+xml'/>"
            for i, (fn, _) in enumerate(chapters_xhtml)
        )
        spine_items = "".join(f"<itemref idref='c{i}'/>" for i in range(len(chapters_xhtml)))
        opf = (
            "<?xml version='1.0' encoding='utf-8'?>"
            "<package xmlns='http://www.idpf.org/2007/opf' version='3.0' unique-identifier='bookid'>"
            f"<metadata xmlns:dc='http://purl.org/dc/elements/1.1/'>"
            f"<dc:identifier id='bookid'>novelforge-{cfg.title}</dc:identifier>"
            f"<dc:title>{cfg.title}</dc:title><dc:language>{cfg.language}</dc:language></metadata>"
            f"<manifest>{manifest_items}<item id='ncx' href='toc.ncx' media-type='application/x-dtbncx+xml'/></manifest>"
            f"<spine toc='ncx'>{spine_items}</spine></package>"
        )
        z.writestr("OEBPS/content.opf", opf)
        navpoints = "".join(
            f"<navPoint id='np{i}' playOrder='{i+1}'><navLabel><text>Глава {i+1}</text></navLabel>"
            f"<content src='{fn}'/></navPoint>"
            for i, (fn, _) in enumerate(chapters_xhtml)
        )
        ncx = (
            "<?xml version='1.0' encoding='utf-8'?>"
            "<ncx xmlns='http://www.daisy.org/z3986/2005/ncx/' version='2005-1'>"
            f"<head/><docTitle><text>{cfg.title}</text></docTitle>"
            f"<navMap>{navpoints}</navMap></ncx>"
        )
        z.writestr("OEBPS/toc.ncx", ncx)
        for fn, content in chapters_xhtml:
            z.writestr(f"OEBPS/{fn}", content)
    return epub_path
