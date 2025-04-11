from typing import Dict, Optional

from pydantic import BaseModel, Field

from .config import Server


class VersionInfo(BaseModel):
    """Version information for a specific server."""
    resource: str = ""
    client: str = ""


class VersionCache(BaseModel):
    """Cache of version information for all servers."""
    CN: VersionInfo = Field(default_factory=VersionInfo)
    EN: VersionInfo = Field(default_factory=VersionInfo)
    JP: VersionInfo = Field(default_factory=VersionInfo)
    KR: VersionInfo = Field(default_factory=VersionInfo)

    def get_version(self, server: Server) -> VersionInfo:
        """Get version information for a specific server."""
        return getattr(self, server)

    def set_version(self, server: Server, version: VersionInfo) -> None:
        """Set version information for a specific server."""
        setattr(self, server, version)


class AssetCache(BaseModel):
    """Cache of asset hashes."""
    assets: Dict[str, str] = Field(default_factory=dict)  # asset_path -> hash

    def get_hash(self, asset_path: str) -> Optional[str]:
        """Get hash for a specific asset path."""
        return self.assets.get(asset_path)

    def set_hash(self, asset_path: str, hash_value: str) -> None:
        """Set hash for a specific asset path."""
        self.assets[asset_path] = hash_value

    def clear(self) -> None:
        """Clear all cached hashes."""
        self.assets.clear() 