from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class Server(str, Enum):
    """Supported Arknights servers."""
    CN = "CN"
    EN = "EN"
    KR = "KR"
    JP = "JP"


class ServerConfig(BaseModel):
    """Configuration for a specific server."""
    enabled: bool = Field(default=True, description="Whether to fetch data from this server")
    path_whitelist: Optional[List[str]] = Field(
        default=None,
        description="List of paths to extract. If None, all paths will be extracted"
    )


class Config(BaseModel):
    """Main configuration model."""
    output_dir: Path = Field(default=Path("./output"), description="Directory for extracted data")
    cache_dir: Path = Field(default=Path("./cache"), description="Directory for cache files")
    servers: Dict[Server, ServerConfig] = Field(
        default_factory=lambda: {
            server: ServerConfig() for server in Server
        },
        description="Per-server configuration"
    )

    class Config:
        use_enum_values = True 