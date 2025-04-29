import asyncio
from .core.workflow import (
    load_or_create_config,
    setup_directories,
    load_caches,
    fetch_assets,
    process_assets,
    process_alpha_images,
    process_portraits,
    process_text_assets,
    process_audio_files
)
from .utils.logger import setup_logger


async def main():
    """Main workflow function that runs all processes in the correct order."""
    global logger
    logger = setup_logger(level="INFO")

    # Setup configuration and caches
    config = load_or_create_config()
    setup_directories(config)
    version_cache, asset_cache = load_caches(config)
    
    # Process entire workflow
    await fetch_assets(config, version_cache, asset_cache)
    await process_assets(config)
    process_alpha_images(config)
    process_portraits(config)    
    process_text_assets(config)
    process_audio_files(config)


if __name__ == "__main__":
    asyncio.run(main()) 