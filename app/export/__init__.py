"""Export subsystem: DOCX (python-docx) and PDF (Qt paged rendering).

Both exporters consume the editor's native rich text (as HTML per page) so
whatever the user sees is what gets exported.
"""

from app.export.docx_exporter import export_docx
from app.export.pdf_exporter import export_pdf

__all__ = ["export_docx", "export_pdf"]
