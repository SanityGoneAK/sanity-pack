import asyncio
import json
from pathlib import Path
from typing import Tuple

from .fetcher import DataFetcher
from .extractor import UnityAssetExtractor
from .alpha_processor import AlphaProcessor
from .portrait_processor import PortraitProcessor
from .text_decoder import TextAssetDecoder
from ..models.cache import AssetCache, VersionCache
from ..models.config import Config, Server, ServerConfig
from ..utils.cache import load_cache, save_cache
from ..utils.logger import logger


def create_default_config() -> Config:
    """Create a default configuration."""
    return Config(
        servers={
            Server.CN: ServerConfig(enabled=False),
            Server.EN: ServerConfig(enabled=False),
            Server.JP: ServerConfig(enabled=False),
            Server.KR: ServerConfig(enabled=False),
        }
    )


def load_or_create_config() -> Config:
    """Load configuration from file or create default if it doesn't exist."""
    
    try:
        logger.info("\nLoading configuration...")
        
        with open("config.json") as f:
            return Config.model_validate(json.load(f))
    except FileNotFoundError:
        logger.info("Config file not found, creating default config.json...")
        
        config = create_default_config()
        with open("config.json", "w") as f:
            json.dump(config.model_dump(), f, indent=2)
        return config


def setup_directories(config: Config) -> None:
    """Create necessary directories if they don't exist."""
    
    config.cache_dir.mkdir(parents=True, exist_ok=True)


def load_caches(config: Config) -> Tuple[VersionCache, AssetCache]:
    """Load or create cache files."""
    
    logger.info("Loading caches")

    version_cache = load_cache(config.cache_dir, "version.json", VersionCache)
    asset_cache = load_cache(config.cache_dir, "assets.json", AssetCache)
    
    return version_cache, asset_cache


async def fetch_assets(config: Config, version_cache: VersionCache, asset_cache: AssetCache) -> None:
    """Fetch assets from all enabled servers."""

    logger.info("\nFetching assets from servers...")

    async with DataFetcher(config) as fetcher:
        fetcher.version_cache = version_cache
        fetcher.asset_cache = asset_cache
        await fetcher.fetch_all()
        save_cache(fetcher.version_cache, config.cache_dir, "version.json")
        save_cache(fetcher.asset_cache, config.cache_dir, "assets.json")


async def process_assets(config: Config) -> None:
    """Process all assets concurrently."""
    extractor = UnityAssetExtractor(config)
    await extractor.extract_all()

def process_alpha_images(config: Config) -> None:
    """Process alpha images and combine them with their RGB counterparts."""
    
    logger.info("\nProcessing alpha images...")
    
    alpha_processor = AlphaProcessor(config.output_dir)
    alpha_processor.process_alpha_images()

    logger.info("Alpha image processing complete!")


def process_portraits(config: Config) -> None:
    """Process character portraits from atlases."""

    logger.info("\nProcessing character portraits...")

    portrait_processor = PortraitProcessor(config)
    portrait_processor.process_portraits()

    logger.info("Portrait processing complete!")

def process_text_assets(config: Config) -> None:
    """Process text assets using FlatBuffers and AES decryption."""

    logger.info("\nProcessing text assets...")
    
    text_decoder = TextAssetDecoder(config)
    text_decoder.process_directory(config.output_dir)

    logger.info("Text asset processing complete!") 