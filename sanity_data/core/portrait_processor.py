import json
from pathlib import Path
from typing import Dict, List, Optional

from PIL import Image

from ..models.config import Config, Server
from ..utils.image import process_portrait
from ..utils.logger import logger


class PortraitProcessor:
    """Handles processing of character portraits from atlases."""

    def __init__(self, config: Config):
        self.config = config
        self.output_dir = config.output_dir

    def _get_portrait_paths(self, server: Server) -> List[Path]:
        """Get all portrait atlas paths for a server."""
        server_dir = self.output_dir / server.lower()
        portrait_dir = server_dir / "arts" / "charportraits"
        
        if not portrait_dir.exists():
            return []
            
        # Find all portrait atlas JSON files
        return list(portrait_dir.glob("portraits#*.json"))

    def _process_atlas(self, json_path: Path) -> None:
        """Process a single portrait atlas."""
        try:
            # Load the JSON data
            with open(json_path) as f:
                atlas_data = json.load(f)
            
            # Get the atlas image path (same name but with .png extension)
            atlas_image_path = json_path.with_suffix(".png")
            if not atlas_image_path.exists():
                logger.warning(f"Warning: Atlas image not found for {json_path}")
                return
            
            # Process each sprite in the atlas
            for sprite in atlas_data.get("_sprites", []):
                try:
                    char_name = sprite["name"]
                    
                    output_path = json_path.parent / f"{char_name}.png"
                    process_portrait(atlas_image_path, sprite, output_path)
                    logger.info(f"Processed portrait: {char_name}")
                    
                except Exception as e:
                    logger.error(f"Error processing sprite {sprite.get('name', 'unknown')}: {str(e)}", exc_info=True)
            
            # Clean up original files
            json_path.unlink()
            atlas_image_path.unlink()
            logger.info(f"Cleaned up atlas files: {json_path.stem}")
            
        except Exception as e:
            logger.error(f"Error processing atlas {json_path}: {str(e)}", exc_info=True)

    def process_portraits(self) -> None:
        """Process all portraits for all enabled servers."""
        for server, server_config in self.config.servers.items():
            if not server_config.enabled:
                continue
                
            logger.info(f"\nProcessing portraits for {server} server...")
            portrait_paths = self._get_portrait_paths(server)
            
            for json_path in portrait_paths:
                self._process_atlas(json_path) 