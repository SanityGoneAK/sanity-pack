import asyncio
from .core.workflow import (
    load_or_create_config,
    setup_directories,
    load_caches,
    fetch_assets,
    extract_assets,
    process_alpha_images,
    process_portraits
)


async def main():
    config = load_or_create_config()
    setup_directories(config)
    
    version_cache, asset_cache = load_caches(config)
    
    await fetch_assets(config, version_cache, asset_cache)
    extract_assets(config)
    
    process_alpha_images(config)
    process_portraits(config)


if __name__ == "__main__":
    asyncio.run(main()) 