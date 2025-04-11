import json
from pathlib import Path
from typing import Optional, Type, TypeVar

from pydantic import BaseModel

T = TypeVar('T', bound=BaseModel)


def load_cache(cache_dir: Path, filename: str, model_class: Type[T]) -> T:
    """Load a cache file, creating a new one if it doesn't exist."""
    cache_path = cache_dir / filename
    
    # Create cache directory if it doesn't exist
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    # Try to load existing cache
    if cache_path.exists():
        try:
            data = json.loads(cache_path.read_text())
            return model_class.model_validate(data)
        except (json.JSONDecodeError, ValueError):
            # If the cache is corrupted, create a new one
            pass
    
    # Create new cache if loading failed or file doesn't exist
    cache = model_class()
    save_cache(cache, cache_dir, filename)
    return cache


def save_cache(cache: BaseModel, cache_dir: Path, filename: str) -> None:
    """Save a cache object to a file."""
    cache_path = cache_dir / filename
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(cache.model_dump_json(indent=2)) 