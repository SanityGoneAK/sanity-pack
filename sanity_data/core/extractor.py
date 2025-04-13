import asyncio
import json
from pathlib import Path
from typing import Dict, List, Optional, Union, Tuple, Any

import UnityPy
from UnityPy.enums.BundleFile import CompressionFlags
from UnityPy.helpers import CompressionHelper
from UnityPy.classes import Texture2D, Sprite, AssetBundle, TextAsset, MonoBehaviour, AudioClip
from PIL import Image

from ..models.config import Config, Server
from ..utils.compression import decompress_lz4ak

CompressionHelper.DECOMPRESSION_MAP[CompressionFlags.LZHAM] = decompress_lz4ak


class UnityAssetExtractor:
    """Handles extraction of Unity assets from downloaded game files."""

    def __init__(self, config: Config):
        self.config = config
        self._semaphore = asyncio.Semaphore(8)  # Limit concurrent extractions
        self._object_semaphore = asyncio.Semaphore(8)  # Limit concurrent object processing

    def _get_env(self, server: Server, asset_path: str) -> UnityPy.Environment:
        """Get or create a UnityPy environment for the given asset."""
        server_dir = self.config.output_dir / server.lower()
        asset_file = server_dir / asset_path
        return UnityPy.load(str(asset_file))

    async def _process_texture(self, obj: Any) -> Optional[Tuple[str, Image.Image]]:
        """Process a Texture2D object."""
        try:
            data = obj.read()
            return data.m_Name, data.image
        except Exception as e:
            print(f"Error processing texture: {e}")
            return None

    async def _process_sprite(self, obj: Any) -> Optional[Tuple[str, Image.Image]]:
        """Process a Sprite object."""
        try:
            data = obj.read()
            return data.m_Name, data.image
        except Exception as e:
            print(f"Error processing sprite: {e}")
            return None

    async def _process_text_asset(self, obj: Any) -> Optional[Tuple[str, bytes]]:
        """Process a TextAsset object."""
        try:
            data = obj.read()
            return data.m_Name, data.m_Script.encode("utf-8", "surrogateescape")
        except Exception as e:
            print(f"Error processing text asset: {e}")
            return None

    async def _process_mono_behaviour(self, obj: Any) -> Optional[Tuple[str, Any]]:
        """Process a MonoBehaviour object."""
        try:
            data = obj.read()
            if obj.serialized_type.node:
                tree = obj.read_typetree()
                return tree['m_Name'], tree
        except Exception as e:
            print(f"Error processing MonoBehaviour: {e}")
        return None

    async def _process_audio_clip(self, obj: Any) -> Dict[str, bytes]:
        """Process an AudioClip object."""
        try:
            clip = obj.read()
            return {name: byte for name, byte in clip.samples.items()}
        except Exception as e:
            print(f"Error processing AudioClip: {e}")
            return {}

    async def _process_object(self, obj: Any) -> Tuple[
        Optional[Tuple[str, Image.Image]],  # texture
        Optional[Tuple[str, Image.Image]],  # sprite
        Optional[Tuple[str, bytes]],        # text asset
        Optional[Tuple[str, Any]],          # mono behaviour
        Optional[Tuple[str, bytes]]         # audio clips
    ]:
        """Process a single Unity object."""
        async with self._object_semaphore:
            try:
                obj_type = obj.read()
                if isinstance(obj_type, Texture2D):
                    texture = await self._process_texture(obj)
                    return texture, None, None, None, {}
                elif isinstance(obj_type, Sprite):
                    sprite = await self._process_sprite(obj)
                    return None, sprite, None, None, {}
                elif isinstance(obj_type, TextAsset):
                    text = await self._process_text_asset(obj)
                    return None, None, text, None, {}
                elif isinstance(obj_type, MonoBehaviour):
                    mono = await self._process_mono_behaviour(obj)
                    return None, None, None, mono, {}
                elif isinstance(obj_type, AudioClip):
                    audio = await self._process_audio_clip(obj)
                    return None, None, None, None, audio
                elif isinstance(obj, AssetBundle):
                    if getattr(obj, "m_Name", None):
                        print(f'Found AssetBundle named "{obj.m_Name}"')
            except Exception as e:
                print(f"Error processing object: {e}")
            return None, None, None, None, {}
    
    async def extract_assets(
        self, 
        server: Server, 
        asset_path: str
    ) -> Tuple[Dict[str, Image.Image], Dict[str, Image.Image], Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
        """Extract all textures, sprites, text assets, MonoBehaviours, and audio clips from a Unity asset file in a single pass."""
        env = self._get_env(server, asset_path)
        textures: Dict[str, Image.Image] = {}
        sprites: Dict[str, Image.Image] = {}
        text_assets: Dict[str, Any] = {}
        mono_behaviours: Dict[str, Any] = {}
        audio_clips: Dict[str, Any] = {}

        # Process all objects concurrently
        tasks = [self._process_object(obj) for obj in env.objects]
        results = await asyncio.gather(*tasks)

        # Combine results
        for texture, sprite, text, mono, audio in results:
            if texture:
                name, image = texture
                textures[name] = image
            if sprite:
                name, image = sprite
                sprites[name] = image
            if text:
                name, content = text
                text_assets[name] = content
            if mono:
                name, content = mono
                mono_behaviours[name] = content
            audio_clips.update(audio)

        return textures, sprites, text_assets, mono_behaviours, audio_clips

    async def process_asset(self, server: Server, asset_path: Path) -> None:
        """Process a single asset file asynchronously."""
        async with self._semaphore:
            try:
                relative_path = asset_path.relative_to(self.config.output_dir / server.lower())
                print(f"Extracting {relative_path}...")
                
                textures, sprites, text_assets, mono_behaviours, audio_clips = await self.extract_assets(
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
                    output_path = base_dir / f"{name}"
                    with open(output_path, 'wb') as f:
                        f.write(content)
                
                # Save MonoBehaviours
                for name, content in mono_behaviours.items():
                    output_path = base_dir / f"{name}.json"
                    with open(output_path, 'w', encoding='utf-8') as f:
                        json.dump(content, f, indent=2, ensure_ascii=False)
                
                # Save audio clips
                for name, audio_data in audio_clips.items():
                    folder_name = asset_path.stem
                    folder_dir = base_dir / folder_name
                    folder_dir.mkdir(exist_ok=True)
                    
                    output_path = folder_dir / f"{name}"
                    with open(output_path, 'wb') as f:
                        f.write(audio_data)
                
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
            for asset_path in server_dir.glob("**/*.bin"):
                tasks.append(self.process_asset(server, asset_path))
        
        # Run all extraction tasks concurrently
        await asyncio.gather(*tasks) 