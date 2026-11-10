"""Application-level exceptions with clear, mappable HTTP semantics."""


class PDFRagError(Exception):
    """Base exception for all application errors."""


class DocumentProcessingError(PDFRagError):
    """Raised when a PDF cannot be loaded, parsed, or chunked."""


class UnsupportedFileTypeError(PDFRagError):
    """Raised when an uploaded file is not a supported type (PDF)."""


class FileTooLargeError(PDFRagError):
    """Raised when an uploaded file exceeds the configured size limit."""


class VectorStoreError(PDFRagError):
    """Raised when the vector store cannot be written to or queried."""


class RetrievalError(PDFRagError):
    """Raised when retrieval of relevant chunks fails."""


class GenerationError(PDFRagError):
    """Raised when the LLM fails to generate a response after retries."""


class AuthenticationError(PDFRagError):
    """Raised when a request is missing or has an invalid API key."""
