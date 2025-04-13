import asyncio
from .core.workflow import (
    load_or_create_config,
    setup_directories,
    load_caches,
    fetch_assets,
    process_assets,
    process_alpha_images,
    process_portraits
)


async def main():
    """Main workflow function that runs all processes in the correct order."""
    # Load configuration and setup
    config = load_or_create_config()
    setup_directories(config)
    version_cache, asset_cache = load_caches(config)
    
    # First, fetch all assets
    print("\nFetching assets from servers...")
    await fetch_assets(config, version_cache, asset_cache)
    print("\nAsset fetching complete!")
    
    # Then, process all assets
    print("\nProcessing downloaded assets...")
    await process_assets(config)
    print("\nAsset processing complete!")

    process_alpha_images(config)
    process_portraits(config)


if __name__ == "__main__":
    asyncio.run(main()) 