import asyncio
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
        self._semaphore = asyncio.Semaphore(4)  # Limit concurrent extractions

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

    async def process_asset(self, server: Server, asset_path: Path) -> None:
        """Process a single asset file asynchronously."""
        async with self._semaphore:
            try:
                relative_path = asset_path.relative_to(self.config.output_dir / server.lower())
                print(f"Extracting {relative_path}...")
                
                textures, sprites, text_assets, mono_behaviours = self.extract_assets(
                    server,
                    str(relative_path)
                )
                
                # Save all assets
                base_dir = asset_path.parent
                
                # Save textures
                for name, image in textures.items():
                    image.save(base_dir / f"{name}.png")
                
                # Save sprites
                for name, image in sprites.items():
                    image.save(base_dir / f"{name}.png")
                
                # Save text assets
                for name, content in text_assets.items():
                    output_path = base_dir / f"{name}.json" if isinstance(content, (dict, list)) else base_dir / f"{name}.txt"
                    if isinstance(content, (dict, list)):
                        with open(output_path, 'w', encoding='utf-8') as f:
                            json.dump(content, f, indent=2, ensure_ascii=False)
                    else:
                        with open(output_path, 'w', encoding='utf-8') as f:
                            f.write(content)
                
                # Save MonoBehaviours
                for name, content in mono_behaviours.items():
                    output_path = base_dir / f"{name}.json"
                    with open(output_path, 'w', encoding='utf-8') as f:
                        json.dump(content, f, indent=2, ensure_ascii=False)
                
                # Delete the original asset file
                asset_path.unlink()
                print(f"Successfully extracted assets from {relative_path}")
                
            except Exception as e:
                print(f"Error processing {asset_path}: {e}")

    async def extract_all(self) -> None:
        """Extract all assets from downloaded files concurrently."""
        tasks = []
        for server, server_config in self.config.servers.items():
            if not server_config.enabled:
                continue

            print(f"\nProcessing {server} server assets...")
            server_dir = self.config.output_dir / server.lower()
            
            for asset_path in server_dir.glob("**/*.ab"):
                tasks.append(self.process_asset(server, asset_path))
        
        # Run all extraction tasks concurrently
        await asyncio.gather(*tasks) 