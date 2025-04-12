import json
from pathlib import Path
from typing import Tuple

from .fetcher import DataFetcher
from .extractor import UnityAssetExtractor
from .alpha_processor import AlphaProcessor
from ..models.cache import AssetCache, VersionCache
from ..models.config import Config, Server, ServerConfig
from ..utils.cache import load_cache, save_cache


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
                    "gamedata/",  # Add gamedata for text assets
                    "prefabs/",   # Add prefabs for MonoBehaviours
                ]
            ),
            Server.EN: ServerConfig(
                enabled=True,
                path_whitelist=[
                    "chararts/",
                    "portraits/",
                    "gamedata/",  # Add gamedata for text assets
                    "prefabs/",   # Add prefabs for MonoBehaviours
                ]
            ),
            Server.JP: ServerConfig(enabled=False),
            Server.KR: ServerConfig(enabled=False),
        }
    )


def load_or_create_config() -> Config:
    """Load configuration from file or create default if it doesn't exist."""
    try:
        with open("config.json") as f:
            return Config.model_validate(json.load(f))
    except FileNotFoundError:
        print("Creating default config.json...")
        config = create_default_config()
        with open("config.json", "w") as f:
            json.dump(config.model_dump(), f, indent=2)
        return config


def setup_directories(config: Config) -> None:
    """Create necessary directories if they don't exist."""
    config.cache_dir.mkdir(parents=True, exist_ok=True)


def load_caches(config: Config) -> Tuple[VersionCache, AssetCache]:
    """Load or create cache files."""
    version_cache = load_cache(config.cache_dir, "version.json", VersionCache)
    asset_cache = load_cache(config.cache_dir, "assets.json", AssetCache)
    return version_cache, asset_cache


async def fetch_assets(config: Config, version_cache: VersionCache, asset_cache: AssetCache) -> None:
    """Fetch assets from all enabled servers."""
    async with DataFetcher(config) as fetcher:
        fetcher.version_cache = version_cache
        fetcher.asset_cache = asset_cache
        await fetcher.fetch_all()
        save_cache(fetcher.version_cache, config.cache_dir, "version.json")
        save_cache(fetcher.asset_cache, config.cache_dir, "assets.json")


def extract_assets(config: Config) -> None:
    """Extract assets from downloaded files."""
    extractor = UnityAssetExtractor(config)
    for server, server_config in config.servers.items():
        if not server_config.enabled:
            continue

        print(f"\nProcessing {server} server assets...")
        server_dir = config.output_dir / server.lower()
        
        for asset_path in server_dir.glob("**/*.ab"):
            relative_path = asset_path.relative_to(server_dir)
            print(f"Extracting {relative_path}...")
            
            try:
                extractor.save_assets(
                    server,
                    str(relative_path),
                    save_textures=True,
                    save_sprites=True,
                    save_text_assets=True,
                    save_mono_behaviours=True
                )
                print(f"Successfully extracted assets from {relative_path}")
            except Exception as e:
                print(f"Error processing {relative_path}: {e}")


def process_alpha_images(config: Config) -> None:
    """Process alpha images and combine them with their RGB counterparts."""
    print("\nProcessing alpha images...")
    alpha_processor = AlphaProcessor(config.output_dir)
    alpha_processor.process_alpha_images()
    print("Alpha image processing complete!") 