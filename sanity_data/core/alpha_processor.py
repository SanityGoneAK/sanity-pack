import re
from pathlib import Path
from typing import Optional, List, Tuple

from PIL import Image

from ..utils.image import combine_alpha_rgb


class AlphaProcessor:
    """Handles processing of alpha images and combining them with their RGB counterparts."""

    # Common alpha suffixes used in Arknights
    ALPHA_SUFFIXES = [
        r"\[alpha\](\$[0-9]+)?$",  # [alpha] or [alpha]$1
        r"_alpha(\$[0-9]+)?$",     # _alpha or _alpha$1
        r"alpha(\$[0-9]+)?$",      # alpha or alpha$1
        r"a(\$[0-9]+)?$",          # a or a$1
    ]

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self._suffix_patterns = [re.compile(suffix) for suffix in self.ALPHA_SUFFIXES]

    def _get_rgb_path(self, alpha_path: Path) -> Optional[Path]:
        """Get the corresponding RGB path for an alpha image path."""
        stem = alpha_path.stem
        for pattern in self._suffix_patterns:
            match = pattern.search(stem)
            if match:
                # Remove the alpha suffix and any version number
                base_name = stem[:match.start()]
                return alpha_path.parent / f"{base_name}{alpha_path.suffix}"
        return None

    def process_alpha_images(self) -> None:
        """Process all alpha images in the output directory."""
        # Find all image files in the output directory
        image_extensions = {'.png', '.jpg', '.jpeg', '.webp'}
        alpha_images: List[Tuple[Path, Path]] = []

        # First pass: collect all alpha images and their RGB counterparts
        for image_path in self.output_dir.rglob("*"):
            if image_path.suffix.lower() in image_extensions:
                rgb_path = self._get_rgb_path(image_path)
                if rgb_path and rgb_path.exists():
                    alpha_images.append((rgb_path, image_path))

        # Second pass: process each pair
        for rgb_path, alpha_path in alpha_images:
            try:
                print(f"Processing alpha image: {alpha_path}")
                
                # Combine the images
                combined_image = combine_alpha_rgb(rgb_path, alpha_path)
                
                # Save the combined image over the RGB image
                combined_image.save(rgb_path)
                
                # Delete the alpha image
                alpha_path.unlink()
                print(f"Successfully processed and deleted: {alpha_path}")
                
            except Exception as e:
                print(f"Error processing {alpha_path}: {e}") 