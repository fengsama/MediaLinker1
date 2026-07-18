from pydantic import BaseModel, Field


class ScanRequest(BaseModel):
    path: str = Field(min_length=1, description="需要扫描的本地目录或已挂载的 SMB 路径")
    recursive: bool = Field(default=True, description="是否扫描子目录")


class SubtitleFile(BaseModel):
    name: str
    path: str
    extension: str
    size: int


class VideoFile(BaseModel):
    name: str
    path: str
    extension: str
    size: int
    modified_at: str
    detected_season: int | None = None
    detected_episode: int | None = None
    subtitles: list[SubtitleFile] = Field(default_factory=list)


class ScanResponse(BaseModel):
    root: str
    count: int
    files: list[VideoFile]
