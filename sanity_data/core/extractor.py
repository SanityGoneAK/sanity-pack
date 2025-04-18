import asyncio
import json
from dataclasses import dataclass
import traceback
from pathlib import Path
from typing import Dict, List, Optional, Union, Tuple, Any, Protocol, runtime_checkable, TypeVar, Generic

import UnityPy
from UnityPy.enums.BundleFile import CompressionFlags
from UnityPy.helpers import CompressionHelper
from UnityPy.classes import Texture2D, Sprite, AssetBundle, TextAsset, MonoBehaviour, AudioClip, Object
from PIL import Image

from ..models.config import Config, Server
from ..utils.compression import decompress_lz4ak

CompressionHelper.DECOMPRESSION_MAP[CompressionFlags.LZHAM] = decompress_lz4ak

T = TypeVar('T', bound=Object)

@dataclass
class AssetResult:
    """Result of processing an asset."""
    obj: Object
    content: Any
    object_type: type
    name: str

@runtime_checkable
class AssetProcessor(Protocol[T]):
    """Protocol for asset processors."""
    async def process(self, obj: T) -> Optional[AssetResult]:
        """Process a Unity object and return the result."""
        ...

class TextureProcessor(AssetProcessor[Texture2D]):
    """Processor for Texture2D objects."""
    async def process(self, obj: Texture2D) -> Optional[AssetResult]:
        try:
            data = obj.read()
            return AssetResult(
                name=getattr(data, 'm_Name', None),
                obj=obj,
                content=data.image,
                object_type=Texture2D,
            )
        except Exception as e:
            print(f"Error processing texture: {e}")
            return None

class SpriteProcessor(AssetProcessor[Sprite]):
    """Processor for Sprite objects."""
    async def process(self, obj: Sprite) -> Optional[AssetResult]:
        try:
            data = obj.read()
            return AssetResult(
                name=getattr(data, 'm_Name', None),
                obj=obj,
                content=data.image,
                object_type=Sprite,
            )
        except Exception as e:
            print(f"Error processing sprite: {e}")
            return None

class TextAssetProcessor(AssetProcessor[TextAsset]):
    """Processor for TextAsset objects."""
    async def process(self, obj: TextAsset) -> Optional[AssetResult]:
        try:
            data = obj.read()
            return AssetResult(
                name=getattr(data, 'm_Name', None),
                obj=obj,
                content=data.m_Script.encode("utf-8", "surrogateescape"),
                object_type=TextAsset,
            )
        except Exception as e:
            print(f"Error processing text asset: {e}")
            return None

class MonoBehaviourProcessor(AssetProcessor[MonoBehaviour]):
    """Processor for MonoBehaviour objects."""
    async def process(self, obj: MonoBehaviour) -> Optional[AssetResult]:
        try:
            data = obj.read()
            if obj.serialized_type.node:
                tree = obj.read_typetree()
                return AssetResult(
                    name=tree["m_Name"],
                    obj=obj,
                    content=tree,
                    object_type=MonoBehaviour,
                )
        except Exception as e:
            print(f"Error processing MonoBehaviour: {e}")
        return None

class AudioClipProcessor(AssetProcessor[AudioClip]):
    """Processor for AudioClip objects."""
    async def process(self, obj: AudioClip) -> Optional[AssetResult]:
        try:
            clip = obj.read()
            # path = str(Path(obj.container).parent.stem)
            return AssetResult(
                obj=obj,
                name=str(Path(obj.container).stem),
                content={name: byte for name, byte in clip.samples.items()},
                object_type=AudioClip,
            )
        except Exception as e:
            print(f"Error processing AudioClip: {e}")
            return None

class AssetProcessorFactory:
    """Factory for creating asset processors."""
    @staticmethod
    def get_processor(obj: Object) -> Optional[AssetProcessor]:
        """Get the appropriate processor for a Unity object."""
        try:
            obj_type = obj.read()
            match obj_type:
                case Texture2D():
                    return TextureProcessor()
                case Sprite():
                    return SpriteProcessor()
                case TextAsset():
                    return TextAssetProcessor()
                case MonoBehaviour():
                    return MonoBehaviourProcessor()
                case AudioClip():
                    return AudioClipProcessor()
                case _:
                    if isinstance(obj, AssetBundle) and getattr(obj, "m_Name", None):
                        print(f'Found AssetBundle named "{obj.m_Name}"')
                    return None
        except Exception as e:
            print(f"Error determining processor: {e}")
            return None

class UnityAssetExtractor:
    """Handles extraction of Unity assets from downloaded game files."""

    def __init__(self, config: Config):
        self.config = config
        self._semaphore = asyncio.Semaphore(8)  # Limit concurrent extractions
        self._object_semaphore = asyncio.Semaphore(8)  # Limit concurrent object processing
        self._processor_factory = AssetProcessorFactory()

    def _get_env(self, server: Server, asset_path: str) -> UnityPy.Environment:
        """Get or create a UnityPy environment for the given asset."""
        server_dir = self.config.output_dir / server.lower()
        asset_file = server_dir / asset_path
        return UnityPy.load(str(asset_file))
    
    def _get_target_path(self, obj: Object, name: str, source_dir: Path, output_dir: Path) -> Path:
        """Determine the target path for saving an asset."""
        if obj.container:
            source_dir = Path(*Path(obj.container).parts[1:-1])

        assert isinstance(name, str)
        return output_dir / source_dir / name

    async def _process_object(self, obj: Object) -> Optional[AssetResult]:
        """Process a single Unity object."""
        async with self._object_semaphore:
            processor = self._processor_factory.get_processor(obj)
            if processor:
                return await processor.process(obj)
            return None

    async def _save_asset(self, result: AssetResult, asset_path: Path ,base_dir: Path) -> None:
        """Save an asset to disk."""
        # Get the target path based on the source path and object type
        target_path = self._get_target_path(
            result.obj,
            result.name,
            asset_path.parent,
            base_dir
        )
        target_path.parent.mkdir(parents=True, exist_ok=True)

        if result.object_type in (Texture2D, Sprite):
            target_path = target_path.with_suffix('.png')
            result.content.save(target_path)

        elif result.object_type == TextAsset:
            with open(target_path, 'wb') as f:
                f.write(result.content)

        elif result.object_type == MonoBehaviour:
            target_path = target_path.with_suffix('.json')
            with open(target_path, 'w', encoding='utf-8') as f:
                json.dump(result.content, f, indent=2, ensure_ascii=False)

        elif result.object_type == AudioClip:
            for name, audio_data in result.content.items():
                audio_path = self._get_target_path(result.obj, name, asset_path, base_dir)
                audio_path.parent.mkdir(parents=True, exist_ok=True)
                with open(audio_path, 'wb') as f:
                    f.write(audio_data)

    async def process_asset(self, server: Server, asset_path: Path) -> None:
        """Process a single asset file asynchronously."""
        async with self._semaphore:
            try:
                relative_path = asset_path.relative_to(self.config.output_dir / server.lower())
                print(f"Extracting {relative_path}...")
                
                # 1. Get UnityPy environment
                env = self._get_env(server, str(relative_path))
                
                # 2. Process all objects
                tasks = [self._process_object(obj) for obj in env.objects]
                results = await asyncio.gather(*tasks)
                
                # 3. Save all assets
                base_dir = self.config.output_dir / server.lower()
                for result in results:
                    if result:
                        await self._save_asset(result, relative_path, base_dir)
                
                # 4. Clean up
                asset_path.unlink()
                print(f"Successfully extracted assets from {relative_path}")
                
            except Exception as e:
                print(f"Error processing {asset_path}: {e}")
                traceback.print_exc()

    async def extract_all(self) -> None:
        """Extract all assets from downloaded files concurrently."""
        tasks = []
        for server, server_config in self.config.servers.items():
            if not server_config.enabled:
                continue

            print(f"\nProcessing {server} server assets...")
            server_dir = self.config.output_dir / server.lower()
            
            # 1. Gather files to extract
            for asset_path in server_dir.glob("**/*.ab"):
                tasks.append(self.process_asset(server, asset_path))
            for asset_path in server_dir.glob("**/*.bin"):
                tasks.append(self.process_asset(server, asset_path))
        
        # Run all extraction tasks concurrently
        await asyncio.gather(*tasks) 