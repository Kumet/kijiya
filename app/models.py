from pydantic import BaseModel, Field, HttpUrl


class GenerateRequest(BaseModel):
    url: HttpUrl
    prompt: str = Field(min_length=1, max_length=2000)


class SourceArticle(BaseModel):
    url: str
    title: str | None
    author: str | None
    published_at: str | None
    site_name: str | None
    text: str
    truncated: bool


class Section(BaseModel):
    heading: str
    paragraphs: list[str]


class GeneratedArticle(BaseModel):
    title: str
    lede: str
    sections: list[Section]
    tags: list[str] = []
    takeaways: list[str] = []


class StoredDoc(BaseModel):
    doc_id: str
    html: str
    filename: str
    created_at: float
