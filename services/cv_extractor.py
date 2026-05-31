"""
cv_extractor.py — Extract plain text from uploaded CV files.
Supports: PDF (PyMuPDF), DOCX (python-docx), TXT.
"""
import io


def extract_text(file_bytes: bytes, filename: str) -> str:
    fname = filename.lower()
    if fname.endswith(".pdf"):
        return _extract_pdf(file_bytes)
    elif fname.endswith(".docx"):
        return _extract_docx(file_bytes)
    elif fname.endswith(".txt"):
        return _extract_txt(file_bytes)
    elif fname.endswith(".doc"):
        raise ValueError("Old .doc format is not supported. Please save your CV as .docx or PDF.")
    else:
        raise ValueError("Unsupported file type. Please upload a PDF, DOCX, or TXT file.")


def _extract_pdf(file_bytes: bytes) -> str:
    try:
        import fitz
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        text = "\n".join(page.get_text() for page in doc).strip()
        doc.close()
        if not text:
            raise ValueError("PDF appears to be image-based with no extractable text.")
        return text
    except ImportError:
        raise ValueError("PDF extraction unavailable.")
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"Could not read PDF: {str(e)}")


def _extract_docx(file_bytes: bytes) -> str:
    try:
        from docx import Document
        doc = Document(io.BytesIO(file_bytes))
        text = "\n".join(p.text for p in doc.paragraphs if p.text.strip()).strip()
        if not text:
            raise ValueError("DOCX file appears to be empty.")
        return text
    except ImportError:
        raise ValueError("DOCX extraction unavailable.")
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"Could not read DOCX: {str(e)}")


def _extract_txt(file_bytes: bytes) -> str:
    text = file_bytes.decode("utf-8", errors="replace").strip()
    if not text:
        raise ValueError("TXT file is empty.")
    return text
