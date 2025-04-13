import os
import json
from pathlib import Path
from typing import Dict, List, Optional, Union, Tuple, Any

import UnityPy
from UnityPy.enums.BundleFile import CompressionFlags
from UnityPy.helpers import CompressionHelper
from UnityPy.classes import Texture2D, Sprite, AssetBundle, TextAsset, MonoBehaviour
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
    
    def extract_assets(
        self, 
        server: Server, 
        asset_path: str
    ) -> Tuple[Dict[str, Image.Image], Dict[str, Image.Image], Dict[str, Any], Dict[str, Any]]:
        """Extract all textures, sprites, text assets, and MonoBehaviours from a Unity asset file in a single pass."""
        env = self._get_env(server, asset_path)
        textures: Dict[str, Image.Image] = {}
        sprites: Dict[str, Image.Image] = {}
        text_assets: Dict[str, Any] = {}
        mono_behaviours: Dict[str, Any] = {}

        for obj in env.objects:
            if isinstance(obj.read(), Texture2D):
                data = obj.read()
                textures[data.m_Name] = data.image
            elif isinstance(obj.read(), Sprite):
                data = obj.read()
                sprites[data.m_Name] = data.image
            elif isinstance(obj.read(), TextAsset):
                data = obj.read()
                data = bytes(obj.m_Script)
                # # Try to parse as JSON if it looks like JSON
                # try:
                #     content = data.script.decode('utf-8')
                #     if content.strip().startswith(('{', '[')):
                #         text_assets[data.m_Name] = json.loads(content)
                #     else:
                #         text_assets[data.m_Name] = content
                # except Exception as e:
                #     print(f"Error parsing text asset {data.m_Name}: {e}")
                #     text_assets[data.m_Name] = data.script
            elif isinstance(obj.read(), MonoBehaviour):
                try:
                    data = obj.read()
                    if obj.serialized_type.node:
                        tree = obj.read_typetree()
                        mono_behaviours[tree['m_Name']] = tree
                except Exception as e:
                    print(f"Error serializing MonoBehaviour {data.m_Name}: {e}")
            elif isinstance(obj, AssetBundle):
                if getattr(obj, "m_Name", None):
                    print(f'Found AssetBundle named "{obj.m_Name}"')             

        return textures, sprites, text_assets, mono_behaviours

    def get_available_path(path: Path) -> Path:
        if path.is_file():
            path = path.with_stem(path.stem + "_1")
            index = 1
            while path.is_file():
                index += 1
                new_name = f"_{index}".join(path.stem.rsplit(f"_{index-1}", 1))
                path = path.with_stem(new_name)
        return path
    
    def save_assets(
        self,
        server: Server,
        asset_path: str,
        save_textures: bool = True,
        save_sprites: bool = True,
        save_text_assets: bool = True,
        save_mono_behaviours: bool = True
    ) -> None:
        """Save extracted textures, sprites, text assets, and MonoBehaviours to disk, maintaining the original folder structure."""
        # Get the base directory and filename without extension
        server_dir = self.config.output_dir / server.lower()
        asset_file = server_dir / asset_path
        base_dir = asset_file.parent
        base_name = asset_file.stem
        
        # Extract all assets in a single pass
        textures, sprites, text_assets, mono_behaviours = self.extract_assets(server, asset_path)
        
        # Save textures
        if save_textures and textures:
            for name, image in textures.items():
                image.save(base_dir / f"{name}.png")
        
        # Save sprites
        if save_sprites and sprites:
            for name, image in sprites.items():
                image.save(base_dir / f"{name}.png")

        # Save text assets
        if save_text_assets and text_assets:
            for name, content in text_assets.items():
                output_path = base_dir / f"{name}.json" if isinstance(content, (dict, list)) else base_dir / f"{name}.txt"
                if isinstance(content, (dict, list)):
                    with open(output_path, 'w', encoding='utf-8') as f:
                        json.dump(content, f, indent=2, ensure_ascii=False)
                else:
                    with open(output_path, 'w', encoding='utf-8') as f:
                        f.write(content)

        # Save MonoBehaviours
        if save_mono_behaviours and mono_behaviours:
            for name, content in mono_behaviours.items():
                output_path = base_dir / f"{name}.json"
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(content, f, indent=2, ensure_ascii=False) 