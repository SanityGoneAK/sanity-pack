import os
import json
from pathlib import Path
from typing import Optional, Callable
import bson
import numpy as np
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

from ..models.config import Config, Server

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
)
_EXT_AB = (".ab", ".bin")

# AES decryption constants
AES_MASK_V2 = b"UITpAi82pHAWwnzqHRMCwPonJLIB3WCl"

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
            
        if ext in _EXT_AB and self.is_binary_file(path):
            return True
            
        return False
        
    def aes_cbc_decrypt_bytes(self, data: bytes, mask: bytes = AES_MASK_V2, has_rsa: bool = True) -> bytes:
        """Decrypt AES-CBC encrypted data."""
        # if not isinstance(data, bytes) or len(data) < 16:
        #     raise ValueError("Data should be a bytes object longer than 16 bytes")
            
        # if not isinstance(mask, bytes) or len(mask) != 32:
        #     raise ValueError("Mask should be a 32-byte-long bytes object")
            
        CHAT_MASK = bytes.fromhex('554954704169383270484157776e7a7148524d4377506f6e4a4c49423357436c').decode()

        # Trim RSA signature if present
        # if has_rsa:
        #     data = data[128:]

        aes_key = CHAT_MASK[:16].encode()
        aes_iv = bytearray(
            buffer_bit ^ mask_bit
            for (buffer_bit, mask_bit) in zip(data[:16], CHAT_MASK[16:].encode())
        )

        decrypted = (
            AES.new(aes_key, AES.MODE_CBC, aes_iv)
            .decrypt(data[16:])
        )

        return unpad(decrypted)   
        # # Calculate key and IV
        # key = mask[:16].encode()
        # iv = bytearray(d ^ m for d, m in zip(data[:16], mask[16:]))
        
        # # Decrypt data
        # aes = AES.new(key, AES.MODE_CBC, iv)
        # return unpad(aes.decrypt(data[16:]), AES.block_size)
        
    def decode_aes(self, path: str) -> dict:
        """Decode AES encrypted file."""
        try:
            with open(path, "rb") as f:
                data = f.read()
                
            decrypted = self.aes_cbc_decrypt_bytes(data)
            
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
            
    def decode_flatbuffer(self, path: str) -> dict:
        """Decode FlatBuffer file."""
        try:
            # Import FlatBuffers schema based on server
            server = self._get_server_from_path(path)
            if not server:
                return {}
                
            # Get the appropriate FlatBuffers module
            fbs_module = self._get_fbs_module(server)
            if not fbs_module:
                return {}
                
            # Read and decode the file
            with open(path, "rb") as f:
                data = bytearray(f.read())[128:]  # Skip header
                
            # Get root type and decode
            root_type = self._guess_root_type(path, fbs_module)
            if not root_type:
                return {}
                
            handle = FBOHandler(data, root_type)
            return handle.to_json_dict()
            
        except Exception as e:
            print(f'[ERROR] Failed to decode FlatBuffer file "{path}": {str(e)}')
            return {}
            
    def _get_server_from_path(self, path: str) -> Optional[Server]:
        """Determine server from file path."""
        path = Path(path)
        for server in Server:
            if server.value in str(path):
                return server
        return None
        
    def _get_fbs_module(self, server: Server):
        """Get the appropriate FlatBuffers module for the server."""
        try:
            # Import the server-specific FBS module
            module_name = f"..fbs.{server.value}"
            return __import__(module_name, fromlist=[""])
        except ImportError:
            print(f"[ERROR] Could not import FBS module for server {server}")
            return None
            
    def _guess_root_type(self, path: str, fbs_module) -> Optional[type]:
        """Guess the root type of a FlatBuffer file."""
        target = os.path.basename(path)
        for name in dir(fbs_module):
            if name in target:
                return getattr(fbs_module, "ROOT_TYPE", None)
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
            result = self.decode_flatbuffer(path)
            if result:
                self._save_result(path, result)
                return
                
            # Fall back to AES decoding
            result = self.decode_aes(path)
            if result:
                self._save_result(path, result)
                
        except Exception as e:
            print(f'[ERROR] Failed to process file "{path}": {str(e)}')
            
    def _save_result(self, path: str, result: dict) -> None:
        """Save decoded result to JSON file."""
        try:
            output_path = Path(path).with_suffix('.json')
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