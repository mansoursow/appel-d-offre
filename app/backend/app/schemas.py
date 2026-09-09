from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class TenderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_id: str
    source_name: str
    title: str
    entity: Optional[str] = None
    category: Optional[str] = None
    country: Optional[str] = None
    zone: str
    published_date: Optional[str] = None
    deadline_date: Optional[str] = None
    deadline_iso: Optional[str] = None
    url: Optional[str] = None
    description: Optional[str] = None
    is_relevant: bool = True
    scraped_at: Optional[datetime] = None


class TenderListOut(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[TenderOut]


class SourceOut(BaseModel):
    id: str
    name: str
    url: str
    zone: str
    status: str
    tender_count: int = 0


class RefreshResultOut(BaseModel):
    source_id: str
    source_name: str
    status: str          # ok | error | skipped
    new_items: int = 0
    total_found: int = 0
    error: Optional[str] = None


class RefreshSummaryOut(BaseModel):
    started_at: datetime
    finished_at: datetime
    results: list[RefreshResultOut]
