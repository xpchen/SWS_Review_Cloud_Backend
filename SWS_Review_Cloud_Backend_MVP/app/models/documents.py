from pydantic import BaseModel


class DocumentCreate(BaseModel):
    title: str
    doc_type: str = "SOIL_WATER_PLAN"


class DocumentOut(BaseModel):
    id: int
    project_id: int
    doc_type: str
    title: str
    current_version_id: int | None


class VersionOut(BaseModel):
    id: int
    document_id: int
    version_no: int
    status: str
    source_file_id: int
    pdf_file_id: int | None
    error_message: str | None


class VersionStatusOut(BaseModel):
    id: int
    status: str
    progress: int | None = None
    error_message: str | None = None
