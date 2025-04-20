import os
import json
import re
import subprocess
import shlex
import tempfile
import typing
from pathlib import Path
from typing import Optional, Callable, Any
import bson
import numpy as np
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

from ..models.config import Config, Server
from ..utils.decoder import get_modules_from_package_name
from ..utils.logger import logger

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
            if path.endswith('.lua.bytes'):
                logger.debug(f'Decoded Lua file: "{path}"')
                return decrypted
                
            result = self.load_json_or_bson(decrypted)
            result = json.dumps(result ,indent=4, ensure_ascii=False).encode("utf-8")
                
            return result
        except Exception as e:
            logger.error(f'Failed to decode AES file "{path}": {str(e)}', exc_info=True)
            return {}
            
    def _get_server_from_path(self, path: str) -> Optional[Server]:
        """Determine server from file path."""
        parts = Path(path).parts
        for server in Server:
            if server.value.lower() in map(str.lower, parts):
                return server 
        return None
            
    def _guess_root_type(self, path: str, fbs_modules) -> Optional[tuple[str, type]]:
        """Guess the root type of a FlatBuffer file."""
        target = os.path.basename(path)
        for module_name, module in fbs_modules.items():
            name = module.__name__.split(".")[-1]
            if name in target:
                return module_name, getattr(module, "ROOT_TYPE", None)
        return None, None
        
    def process_directory(self, directory: Path) -> None:
        """Process all files in a directory."""
        for root, _, files in os.walk(directory):
            for file in files:
                file_path = os.path.join(root, file)
                if self.should_process_file(file_path):
                    self.process_file(file_path)
    
    def load_json_or_bson(self, data: bytes) -> any:
        """Load json or possibly bson."""
        if b"\x00" in data[:256]:
            import bson

            return bson.loads(data)

        return json.loads(data)
                    
    def normalize_json(self, data: bytes, *, indent: int = 4, lenient: bool = True) -> bytes:
        """Normalize a json format."""
        if lenient and b"\x00" not in data[:256]:
            return data

        json_data = self.load_json_or_bson(data)
        return json.dumps(json_data, indent=indent, ensure_ascii=False).encode("utf-8")
                    
    def process_file(self, path: str) -> None:
        """Process a single file."""
        try:
            if match := re.search(r"((gamedata/)?.+?\.json)", path):
                with open(path, "rb") as f:
                    data = f.read()
                self._save_result(Path(match.group(1)), self.normalize_json(data))
                return
                
            if match := re.search(r"(gamedata/.+?)\.lua\.bytes", path):
                result = self.decode_aes(path)
                output_path = Path(path).parent / (match.group(1) + '.lua') 
                self._save_result(output_path, bytes(result))
                return
            
            if match := re.search(r"(gamedata/levels/(?:obt|activities)/.+?)\.bytes", path):
                try:
                    with open(path, "rb") as f:
                        data = f.read()
                    text = self.normalize_json(data[128:])
                    self._save_result(Path(path).with_suffix('.json'), bytes(text))
                except UnboundLocalError:
                    result = self.decode_flatbuffer_file(path)
                    if result:
                        output_path = Path(path).parent / f"{Path(match.group(1)).stem}.json"
                        self._save_result(output_path, result)
                        Path(path).unlink()
                return

            if "gamedata/battle/buff_template_data.bytes" in path:
                with open(path, "rb") as f:
                    data = f.read()
                self._save_result(Path(path).with_suffix('.json'), bytes(self.normalize_json(data)))
                return
            
            if match := re.search(r"(gamedata/.+?)(?:[a-fA-F0-9]{6})?\.bytes", path):
                # Try flatbuffer decoding first
                result = self.decode_flatbuffer_file(path)
                if result:
                    output_path = Path(path).parent / f"{Path(match.group(1)).stem}.json"
                    self._save_result(output_path, result)
                    Path(path).unlink()
                    return
                
                # Fall back to AES decoding
                result = self.decode_aes(path)
                if result:
                    output_path = Path(path).with_suffix('.json')
                    self._save_result(output_path, result)
                    Path(path).unlink()
                return
                
            logger.warning(f"Unrecognized file type: {path}")
                
        except Exception as e:
            logger.error(f'Failed to process file "{path}": {str(e)}', exc_info=True)
            
    def _save_result(self, output_path: Path, result: bytes) -> None:
        """Save decoded result to JSON file."""

        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(result)
        except Exception as e:
            logger.error(f'Failed to save result for "{output_path}": {str(e)}', exc_info=True)
    
    def run_flatbuffers(
        self,
        fbs_path: Path,
        fbs_schema_path: Path,
        output_directory: Path,
    ) -> Path:
        """Run the flatbuffers cli. Returns the output filename."""
        args = [
            "flatc",
            "-o",
            str(output_directory),
            str(fbs_schema_path),
            "--",
            str(fbs_path),
            "--json",
            "--strict-json",
            "--natural-utf8",
            "--defaults-json",
            "--unknown-json",
            "--raw-binary",
            "--no-warnings",
            "--force-empty",
        ]
        result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        if result.returncode != 0:
            file = Path(tempfile.mktemp(".log", dir=Path(tempfile.gettempdir()) / "flatbufferlogs"))
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_bytes(result.stdout + b"\n\n\n\n" + result.stderr)
            raise ValueError(
                f"flatc failed with code {result.returncode}: {file} `{shlex.join(args)}` (random exit code likely means a faulty FBS file was provided)",
            )

        return Path(output_directory) / (Path(fbs_path).stem + ".json")

    def recursively_collapse_keys(self, obj: Any) -> Any:
        """Recursively collapse arknights flatc dictionaries."""
        if isinstance(obj, list):
            obj = typing.cast("typing.Any", obj)
            if all(isinstance(item, dict) and item.keys() == {"key", "value"} for item in obj):
                return {item["key"]: self.recursively_collapse_keys(item["value"]) for item in obj}

            return [self.recursively_collapse_keys(item) for item in obj]

        if isinstance(obj, dict):
            obj = typing.cast("typing.Any", obj)
            return {k: self.recursively_collapse_keys(v) for k, v in obj.items()}

        return obj

    def decode_flatbuffer_file(self, path: str, has_rsa: bool = True) -> Optional[bytes]:
        """Decode a flatbuffer file using flatc."""
        try:
            # Extract table name from path
            if match := re.search(r"(\w+_(?:table|data|const|database|text))[0-9a-fA-F]{6}", path):
                table_name = match.group(1)
            else:
                return None

            # Determine server and get schema path
            server = self._get_server_from_path(path)
            if not server:
                return None

            # Use 'yostar' directory for global server, 'cn' for CN server
            server_type = 'cn' if server.value == "CN" else 'yostar'
            schema_dir = Path(__file__).parent.parent / 'fbs' / server_type
            schema_path = schema_dir / f"{table_name}.fbs"

            if not schema_path.exists():
                logger.warning(f"Schema file not found: {schema_path}")
                return None

            # Create temporary directory for flatc output
            temp_dir = Path(tempfile.mkdtemp())
            try:
                # Read and process the input file
                with open(path, "rb") as f:
                    data = f.read()
                
                # Remove RSA header if needed
                if has_rsa:
                    data = data[128:]
                    
                # Create a temporary file with the processed data
                temp_input = temp_dir / "input.bytes"
                temp_input.write_bytes(data)
                
                # Run flatc
                output_path = self.run_flatbuffers(temp_input, schema_path, temp_dir)
                
                # Process the output
                parsed_data = output_path.read_text(encoding="utf-8")
                parsed_data = self.recursively_collapse_keys(json.loads(parsed_data))
                if len(parsed_data) == 1:
                    parsed_data, *_ = parsed_data.values()

                return json.dumps(parsed_data, indent=4, ensure_ascii=False).encode("utf-8")
            finally:
                # Clean up temporary directory
                for file in temp_dir.glob("*"):
                    file.unlink()
                temp_dir.rmdir()

        except Exception as e:
            logger.error(f'Failed to decode FlatBuffer file "{path}": {str(e)}', exc_info=True)
            return None 