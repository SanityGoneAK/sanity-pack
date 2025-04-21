import asyncio
from pathlib import Path
from typing import Dict, List, Optional
from zipfile import ZipFile
from io import BytesIO

import aiohttp
from tenacity import retry, stop_after_attempt, wait_exponential

from ..models.cache import AssetCache, VersionCache, VersionInfo
from ..models.config import Config, Server
from ..utils.logger import logger


class DataFetcher:
    """Handles downloading game data from Arknights servers."""

    # Server URLs
    VERSION_URLS = {
        Server.CN: "https://ak-conf.hypergryph.com/config/prod/official/Android/version",
        Server.EN: "https://ark-us-static-online.yo-star.com/assetbundle/official/Android/version",
        Server.JP: "https://ark-jp-static-online.yo-star.com/assetbundle/official/Android/version",
        Server.KR: "https://ark-kr-static-online-1300509597.yo-star.com/assetbundle/official/Android/version",
    }

    ASSET_BASE_URLS = {
        Server.CN: "https://ak.hycdn.cn/assetbundle/official/Android",
        Server.EN: "https://ark-us-static-online.yo-star.com/assetbundle/official/Android",
        Server.JP: "https://ark-jp-static-online.yo-star.com/assetbundle/official/Android",
        Server.KR: "https://ark-kr-static-online-1300509597.yo-star.com/assetbundle/official/Android",
    }

    def __init__(self, config: Config):
        self.config = config
        self.version_cache = VersionCache()
        self.asset_cache = AssetCache()
        self._session: Optional[aiohttp.ClientSession] = None
        self._semaphore = asyncio.Semaphore(35)  # Limit concurrent downloads

    async def __aenter__(self):
        """Set up async context."""
        timeout = aiohttp.ClientTimeout(total=30)  # 30 seconds timeout
        self._session = aiohttp.ClientSession(
            timeout=timeout,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Clean up async context."""
        if self._session:
            await self._session.close()
            self._session = None

    def _is_path_whitelisted(self, server: Server, path: str) -> bool:
        """Check if a path matches the server's whitelist."""
        whitelist = self.config.servers[server].path_whitelist
        if not whitelist:
            return True
        return any(
            path.startswith(prefix) or prefix.startswith(path)
            for prefix in whitelist
        )

    @retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=4, max=20))
    async def _fetch_json(self, url: str) -> Dict:
        """Fetch and parse JSON from a URL with retry logic."""
        if not self._session:
            raise RuntimeError("DataFetcher must be used as an async context manager")
        
        try:
            async with self._session.get(url) as response:
                response.raise_for_status()
                # Read the response text first
                text = await response.text()
                
                try:
                    return await response.json(content_type=None)
                except Exception as e:
                    logger.error(f"Failed to parse JSON directly: {str(e)}", exc_info=True)
                    # Fallback: try to parse the text we already have
                    import json
                    return json.loads(text)
                
        except aiohttp.ClientError as e:
            logger.error(f"HTTP error for {url}: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error for {url}: {str(e)}", exc_info=True)
            raise

    async def get_version(self, server: Server) -> VersionInfo:
        """Get the current version information for the specified server."""
        try:
            data = await self._fetch_json(self.VERSION_URLS[server])
            logger.debug(f"Version data: {data}")
            version = VersionInfo(
                resource=data["resVersion"],
                client=data["clientVersion"]
            )
            self.version_cache.set_version(server, version)
            return version
        except Exception as e:
            logger.error(f"Error getting version for {server}: {str(e)}", exc_info=True)
            raise

    async def get_asset_list(self, server: Server) -> List[Dict]:
        """Get the list of available assets for a server."""
        try:
            version = await self.get_version(server)
            url = f"{self.ASSET_BASE_URLS[server]}/assets/{version.resource}/hot_update_list.json"
            logger.debug(f"Full asset list url: {url}")
            data = await self._fetch_json(url)
            return data.get("abInfos", [])
        except Exception as e:
            logger.error(f"Error getting asset list for {server}: {str(e)}", exc_info=True)
            raise

    def _transform_asset_path(self, path: str) -> str:
        """Transform asset path to match the server URL format."""
        return (path
                .replace(".ab", "")
                .replace(".bin", "")
                .replace(".mp4", "")
                .replace("/", "_")
                .replace("#", "__")
                + ".dat")

    async def download_asset(self, server: Server, asset_path: str, asset_hash: str) -> Optional[bytes]:
        """Download a specific asset if it matches the whitelist."""
        async with self._semaphore:  # Limit concurrent downloads
            # Check whitelist if it exists
            if not self._is_path_whitelisted(server, asset_path):
                return None

            # Check if we already have this version cached
            cached_hash = self.asset_cache.get_hash(asset_path)
            if cached_hash == asset_hash:
                return None

            # Construct the download URL
            version = self.version_cache.get_version(server)
            transformed_path = self._transform_asset_path(asset_path)
            url = f"{self.ASSET_BASE_URLS[server]}/assets/{version.resource}/{transformed_path}"

            logger.info(f"Fetching asset {asset_path}")

            # Download the asset
            if not self._session:
                raise RuntimeError("DataFetcher must be used as an async context manager")
            
            try:
                async with self._session.get(url) as response:
                    response.raise_for_status()
                    data = await response.read()

                # Process the zip file
                try:
                    with ZipFile(BytesIO(data)) as zip_file:
                        # Extract all files to the output directory
                        server_output_dir = self.config.output_dir / server.lower()
                        for zip_info in zip_file.filelist:
                            zip_info.filename = asset_path  # Use the original asset path
                            zip_file.extract(zip_info, server_output_dir)
                except Exception as e:
                    logger.error(f"Failed to extract {asset_path}: {str(e)}", exc_info=True)
                    return None

                # Update the cache
                self.asset_cache.set_hash(asset_path, asset_hash)
                return data
                
            except aiohttp.ClientError as e:
                logger.error(f"Failed to download {asset_path}: {str(e)}", exc_info=True)
                return None
            except Exception as e:
                logger.error(f"Unexpected error downloading {asset_path}: {str(e)}", exc_info=True)
                return None

    async def fetch_server_assets(self, server: Server) -> None:
        """Fetch assets for a specific server."""
        if not self.config.servers[server].enabled:
            return

        logger.info(f"\nProcessing {server} server...")
        try:
            # Get asset list
            assets = await self.get_asset_list(server)
            logger.info(f"Found {len(assets)} assets")

            # Create download tasks
            tasks = []
            for asset in assets:
                if isinstance(asset, dict):
                    path = asset.get("name")
                    hash_value = asset.get("hash") or asset.get("md5")
                    if path and hash_value:
                        tasks.append(self.download_asset(server, path, hash_value))

            # Run all download tasks concurrently
            await asyncio.gather(*tasks)

        except Exception as e:
            logger.error(f"Error processing {server} server: {str(e)}", exc_info=True)

    async def fetch_all(self):
        """Fetch assets from all enabled servers concurrently."""
        # Create tasks for each server
        tasks = [
            self.fetch_server_assets(server)
            for server in self.config.servers.keys()
        ]
        
        # Run all server tasks concurrently
        await asyncio.gather(*tasks) 