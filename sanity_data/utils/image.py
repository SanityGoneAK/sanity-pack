from pathlib import Path
from typing import Optional, Tuple

from PIL import Image


def combine_alpha_rgb(
    rgb_path: Path,
    alpha_path: Path,
    output_path: Optional[Path] = None
) -> Image.Image:
    """Combine RGB and alpha channel images into a single RGBA image."""
    rgb = Image.open(rgb_path).convert("RGB")
    alpha = Image.open(alpha_path).convert("L")  # Convert to grayscale
    
    # Create RGBA image
    rgba = Image.new("RGBA", rgb.size)
    rgba.paste(rgb, (0, 0))
    rgba.putalpha(alpha)
    
    if output_path:
        rgba.save(output_path)
    
    return rgba


def process_portrait(
    atlas_path: Path,
    json_data: dict,
    output_path: Optional[Path] = None
) -> Image.Image:
    """Process a portrait from an atlas using JSON metadata."""
    # Load the atlas image
    atlas = Image.open(atlas_path)
    
    # Extract sprite information from JSON
    sprite_info = json_data.get("sprite", {})
    rect = sprite_info.get("rect", {})
    x, y, width, height = (
        rect.get("x", 0),
        rect.get("y", 0),
        rect.get("width", 0),
        rect.get("height", 0)
    )
    
    # Extract rotation if present
    rotation = sprite_info.get("rotation", 0)
    
    # Crop the sprite from the atlas
    sprite = atlas.crop((x, y, x + width, y + height))
    
    # Apply rotation if needed
    if rotation != 0:
        sprite = sprite.rotate(rotation, expand=True)
    
    if output_path:
        sprite.save(output_path)
    
    return sprite 