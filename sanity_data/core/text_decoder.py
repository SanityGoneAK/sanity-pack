import os
import json
from pathlib import Path
from typing import Optional, Callable
import bson
import numpy as np
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

from ..models.config import Config, Server
from ..utils.decoder import get_modules_from_package_name

# Known file extensions to skip
_EXT_KNOWN = (
    ".atlas",
    ".skel",
    ".wav",
    ".mp3",
    ".m4a",
    ".mp4",
    ".avi",
    ".mov",
    ".mkv",
    ".flv",
    ".png",
)
_EXT_AB = (".ab", ".bin")

class TextAssetDecoder:
    """Handles decoding of text assets using either FlatBuffers or AES decryption."""
    
    def __init__(self, config: Config):
        self.config = config
        self.output_dir = Path(config.output_dir)
        
    def is_binary_file(self, path: str) -> bool:
        """Check if a file is binary."""
        try:
            with open(path, 'rb') as f:
                chunk = f.read(1024)
                return b'\0' in chunk
        except Exception:
            return False
            
    def should_process_file(self, path: str) -> bool:
        """Determine if a file should be processed."""
        if not os.path.isfile(path):
            return False
            
        ext = os.path.splitext(path)[1].lower()
        if ext in _EXT_KNOWN:
            return False
            
        if ext in _EXT_AB:
            return False
        
        if Path(path).is_file() and self.is_binary_file(path):
            return True
            
        return False
        
    def aes_cbc_decrypt_bytes(self, data: bytes, has_rsa: bool = True) -> bytes:
        """Decrypt AES-CBC encrypted data."""
        mask = bytes.fromhex("554954704169383270484157776e7a7148524d4377506f6e4a4c49423357436c")

        if has_rsa:
            data = data[128:]

        aes_key = mask[:16]
        aes_iv = bytearray(b ^ m for b, m in zip(data[:16], mask[16:]))
        aes = AES.new(aes_key, AES.MODE_CBC, aes_iv)

        decrypted_padded = aes.decrypt(data[16:])
        decrypted = decrypted_padded[: -decrypted_padded[-1]]
        return decrypted
        
    def decode_aes(self, path: str) -> dict:
        """Decode AES encrypted file."""
        try:
            with open(path, "rb") as f:
                data = f.read()
                
            decrypted = self.aes_cbc_decrypt_bytes(data)
            
            # If it's a .lua file, save it as text
            if path.endswith('.lua'):
                print(f'[DEBUG] Decoded Lua file: "{path}"')
                return decrypted
                
            try:
                # Try JSON first
                result = json.loads(decrypted)
                print(f'[DEBUG] Decoded JSON document: "{path}"')
            except UnicodeError:
                # Fall back to BSON
                result = bson.loads(decrypted)
                print(f'[DEBUG] Decoded BSON document: "{path}"')
                
            return result
        except Exception as e:
            print(f'[ERROR] Failed to decode AES file "{path}": {str(e)}')
            return {}
            
    def decode_flatbuffer(self, path: str) -> tuple[dict, str]:
        """Decode FlatBuffer file."""
        try:
            # Import FlatBuffers schema based on server
            server = self._get_server_from_path(path)
            if not server:
                return {}, None
                
            # Get the appropriate FlatBuffers module
            fbs_modules = self._get_fbs_modules(server)
            if not fbs_modules:
                return {}, None
                
            # Read and decode the file
            with open(path, "rb") as f:
                data = bytearray(f.read())[128:]  # Skip header
                
            # Get root type and decode
            fbs_name, root_type = self._guess_root_type(path, fbs_modules)
            if not root_type:
                return {}, None
                
            handle = FBOHandler(data, root_type)
            return handle.to_json_dict(), fbs_name
            
        except Exception as e:
            print(f'[ERROR] Failed to decode FlatBuffer file "{path}": {str(e)}')
            return {}, None
            
    def _get_server_from_path(self, path: str) -> Optional[Server]:
        """Determine server from file path."""
        parts = Path(path).parts
        for server in Server:
            if server.value.lower() in map(str.lower, parts):
                return server 
        return None

        
    def _get_fbs_modules(self, server: Server):
        """Get the appropriate FlatBuffers module for the server."""
        try:
            # Import the server-specific FBS module
            severType = 'cn' if server.value == "CN" else 'global'
            return get_modules_from_package_name(f"sanity_data.fbs._generated.{severType}")
        except ImportError:
            print(f"[ERROR] Could not import FBS module for server {server}")
            return None
            
    def _guess_root_type(self, path: str, fbs_modules) -> Optional[tuple[str, type]]:
        """Guess the root type of a FlatBuffer file."""
        target = os.path.basename(path)
        for module_name, module in fbs_modules.items():
            name = module.__name__.split(".")[-1]
            if name in target:
                return module_name, getattr(module, "ROOT_TYPE", None)
        return None
        
    def process_directory(self, directory: Path) -> None:
        """Process all files in a directory."""
        for root, _, files in os.walk(directory):
            for file in files:
                file_path = os.path.join(root, file)
                if self.should_process_file(file_path):
                    self.process_file(file_path)
                    
    def process_file(self, path: str) -> None:
        """Process a single file."""
        try:
            # Try FlatBuffer decoding first
            result, fbs_name = self.decode_flatbuffer(path)
            if result:
                output_path = Path(path).parent / f"{fbs_name}.json"
                self._save_result(output_path, result)
                Path(path).unlink()
                return
                
            # Fall back to AES decoding
            result = self.decode_aes(path)
            if result:
                self._save_result(Path(path), result)
                
        except Exception as e:
            print(f'[ERROR] Failed to process file "{path}": {str(e)}')
            
    def _save_result(self, path: Path, result: dict) -> None:
        """Save decoded result to JSON file."""

        try:
            if path.suffix == '.lua':
                output_path = path.with_suffix('.lua')
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(result.decode('utf-8'))
                print(f'[INFO] Saved decoded result to: {output_path}')
            else:
                output_path = path.with_suffix('.json')
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                print(f'[INFO] Saved decoded result to: {output_path}')
        except Exception as e:
            print(f'[ERROR] Failed to save result for "{path}": {str(e)}')

class FBOHandler:
    """Handler for FlatBuffers Objects conversion to Python dict."""
    
    def __init__(self, data: bytearray, root_type: type):
        self._root = root_type.GetRootAs(data, 0)
        
    @staticmethod
    def _to_literal(obj: object):
        if obj is None:
            return None
        if isinstance(obj, bytes):
            return str(obj, encoding="UTF-8")
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if not isinstance(obj, (bool, int, float, str, dict, list)):
            return FBOHandler._to_json_dict(obj)
        return obj
        
    @staticmethod
    def _to_json_dict(obj: object):
        if obj is None:
            return None
            
        data = {}
        
        # Handle key-value tables
        if "Key" in dir(obj) and "Value" in dir(obj):
            val = None
            val_len_method = getattr(obj, "ValueLength", None)
            if val_len_method:
                val = [FBOHandler._to_literal(obj.Value(i)) for i in range(val_len_method())]
            else:
                val = FBOHandler._to_literal(obj.Value())
            data[FBOHandler._to_literal(obj.Key())] = val
        else:
            # Handle general objects
            for field_name in dir(obj):
                if field_name in ("Init") or field_name.startswith(("_", "GetRootAs")) or field_name.endswith(("IsNone", "Length")):
                    continue
                    
                field = getattr(obj, field_name)
                if callable(field):
                    val = None
                    
                    # Check if field is None
                    is_none_method = getattr(obj, f"{field_name}IsNone", None)
                    if is_none_method and is_none_method():
                        continue
                        
                    # Handle arrays/tables
                    field_len_method = getattr(obj, f"{field_name}Length", None)
                    if field_len_method:
                        field_len = field_len_method()
                        if field_len:
                            if "Key" in dir(field(0)):
                                val = {}
                                for i in range(field_len):
                                    val.update(FBOHandler._to_json_dict(field(i)))
                            else:
                                val = []
                                for i in range(field_len):
                                    val.append(FBOHandler._to_literal(field(i)))
                    else:
                        val = FBOHandler._to_literal(field())
                        
                    data[field_name] = val
                    
        return data
        
    def to_json_dict(self):
        return FBOHandler._to_json_dict(self._root) 