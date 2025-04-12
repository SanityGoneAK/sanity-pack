import os
from pathlib import Path
from typing import Dict, List, Optional, Union, Tuple

import UnityPy
from UnityPy.enums.BundleFile import CompressionFlags
from UnityPy.helpers import CompressionHelper
from UnityPy.classes import Texture2D, Sprite
from PIL import Image

from ..models.config import Config, Server
from ..utils.compression import decompress_lz4ak

CompressionHelper.DECOMPRESSION_MAP[CompressionFlags.LZHAM] = decompress_lz4ak



class UnityAssetExtractor:
    """Handles extraction of Unity assets from downloaded game files."""

    def __init__(self, config: Config):
        self.config = config

    def _get_env(self, server: Server, asset_path: str) -> UnityPy.Environment:
        """Get or create a UnityPy environment for the given asset."""
        server_dir = self.config.output_dir / server.lower()
        asset_file = server_dir / asset_path
        return UnityPy.load(str(asset_file))

    def extract_assets(self, server: Server, asset_path: str) -> Tuple[Dict[str, Image.Image], Dict[str, Image.Image]]:
        """Extract all textures and sprites from a Unity asset file in a single pass."""
        env = self._get_env(server, asset_path)
        textures: Dict[str, Image.Image] = {}
        sprites: Dict[str, Image.Image] = {}

        for obj in env.objects:
            if isinstance(obj.read(), Texture2D):
                data = obj.read()
                textures[data.m_Name] = data.image
            elif isinstance(obj.read(), Sprite):
                data = obj.read()
                sprites[data.m_Name] = data.image

        return textures, sprites

    def save_assets(
        self,
        server: Server,
        asset_path: str,
        save_textures: bool = True,
        save_sprites: bool = True
    ) -> None:
        """Save extracted textures and sprites to disk, maintaining the original folder structure."""
        # Get the base directory and filename without extension
        server_dir = self.config.output_dir / server.lower()
        asset_file = server_dir / asset_path
        base_dir = asset_file.parent
        base_name = asset_file.stem
        
        # Extract all assets in a single pass
        textures, sprites = self.extract_assets(server, asset_path)
        
        # Save textures
        if save_textures and textures:
            for name, image in textures.items():
                image.save(base_dir / f"{name}.png")
        
        # Save sprites
        if save_sprites and sprites:
            for name, image in sprites.items():
                image.save(base_dir / f"{name}.png") 