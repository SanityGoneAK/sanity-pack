import asyncio
import json
from pathlib import Path

from .core.fetcher import DataFetcher
from .core.extractor import UnityAssetExtractor
from .models.cache import AssetCache, VersionCache
from .models.config import Config, Server, ServerConfig
from .utils.cache import load_cache, save_cache


def create_default_config() -> Config:
    """Create a default configuration with common whitelist patterns."""
    return Config(
        servers={
            Server.CN: ServerConfig(
                enabled=True,
                path_whitelist=[
                    "chararts/",
                    "portraits/",
                    "spritepack/ui_equip_",
                ]
            ),
            Server.EN: ServerConfig(
                enabled=True,
                path_whitelist=[
                    "chararts/",
                    "portraits/",
                ]
            ),
            Server.JP: ServerConfig(enabled=False),
            Server.KR: ServerConfig(enabled=False),
        }
    )


async def main():
    """Main entry point for the package."""
    # Load configuration
    try:
        with open("config.json") as f:
            config = Config.model_validate(json.load(f))
    except FileNotFoundError:
        print("Creating default config.json...")
        config = create_default_config()
        with open("config.json", "w") as f:
            json.dump(config.model_dump(), f, indent=2)

    # Create cache directory if it doesn't exist
    config.cache_dir.mkdir(parents=True, exist_ok=True)

    # Load caches
    version_cache = load_cache(config.cache_dir, "version.json", VersionCache)
    asset_cache = load_cache(config.cache_dir, "assets.json", AssetCache)

    # Initialize fetcher and extractor
    async with DataFetcher(config) as fetcher:
        # Set the caches in the fetcher
        fetcher.version_cache = version_cache
        fetcher.asset_cache = asset_cache

        # Fetch assets from all enabled servers
        await fetcher.fetch_all()

        # Save updated caches
        save_cache(fetcher.version_cache, config.cache_dir, "version.json")
        save_cache(fetcher.asset_cache, config.cache_dir, "assets.json")

    # Initialize extractor and process assets
    extractor = UnityAssetExtractor(config)
    for server, server_config in config.servers.items():
        if not server_config.enabled:
            continue

        print(f"\nProcessing {server} server assets...")
        server_dir = config.output_dir / server.lower()
        
        # Process each asset file
        for asset_path in server_dir.glob("**/*.ab"):
            relative_path = asset_path.relative_to(server_dir)
            print(f"Extracting {relative_path}...")
            
            try:
                extractor.save_assets(
                    server,
                    str(relative_path),
                    save_textures=True,
                    save_sprites=True
                )
                print(f"Successfully extracted assets from {relative_path}")
            except Exception as e:
                print(f"Error processing {relative_path}: {e}")


if __name__ == "__main__":
    asyncio.run(main()) 