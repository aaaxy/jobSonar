"""Extract text from PDF or DOCX resume files."""

import os
import sys
from pathlib import Path


def extract_from_pdf(path: str) -> str:
    """Extract text from a PDF file using PyMuPDF."""
    import fitz  # pymupdf

    doc = fitz.open(path)
    text_parts = []
    for page in doc:
        text_parts.append(page.get_text())
    doc.close()
    return "\n".join(text_parts).strip()


def extract_from_docx(path: str) -> str:
    """Extract text from a DOCX file."""
    from docx import Document

    doc = Document(path)
    return "\n".join(p.text for p in doc.paragraphs).strip()


def extract_from_txt(path: str) -> str:
    """Read plain text file."""
    return Path(path).read_text(encoding="utf-8").strip()


def extract_resume_text(path: str) -> str:
    """Extract text from a resume file (PDF, DOCX, or TXT)."""
    ext = Path(path).suffix.lower()
    extractors = {
        ".pdf": extract_from_pdf,
        ".docx": extract_from_docx,
        ".txt": extract_from_txt,
    }
    extractor = extractors.get(ext)
    if extractor is None:
        raise ValueError(f"Unsupported resume format: {ext}. Use .pdf, .docx, or .txt")
    text = extractor(path)
    if not text:
        raise ValueError(f"No text extracted from {path}. Check the file is not empty.")
    return text


def find_resume(project_root: str) -> str:
    """Find the resume file in the project root."""
    for ext in (".pdf", ".docx", ".txt"):
        path = os.path.join(project_root, f"resume{ext}")
        if os.path.exists(path):
            return path
    raise FileNotFoundError(
        "No resume found. Place resume.pdf, resume.docx, or resume.txt in the project root."
    )


if __name__ == "__main__":
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    resume_path = find_resume(root)
    text = extract_resume_text(resume_path)
    print(f"Extracted {len(text)} characters from {resume_path}")
    print("---")
    print(text)
