"""Flatten directory structure for specific image paths."""

import shutil
from pathlib import Path
from typing import List
from typing import Optional, Set

from sanity_pack.pipelines.base import PipelineStep
from sanity_pack.config.models import UnpackMode
from sanity_pack.utils.logger import log


class FlattenImagePathsStep(PipelineStep):
    """Pipeline step to flatten nested directory structures."""

    IMAGE_PATH_OVERRIDES = {
        "/arts/items": "arts/items",
        "/arts/charavatars": "arts/charavatars",
        "/arts/charportraits": "arts/charportraits",
        "/arts/skills": "arts/skills",
        "/arts/characters/*": "arts/characters",
        "/arts/enemies": "arts/enemies",
        "/arts/ui/subprofessionicon": "arts/ui/subprofessionicon",
        "/arts/ui/uniequipimg": "arts/ui/uniequipimg",
        "/arts/ui/uniequiptype": "arts/ui/uniequiptype",
        "/arts/ui/building/skills": "arts/ui/building/skills",
        "/arts/ui/medalicon/*": "arts/ui/medalicon",
    }

    @property
    def name(self) -> str:
        return "Flatten Image Paths"

    @property
    def required_modes(self) -> Optional[Set[UnpackMode]]:
        return {UnpackMode.ARKNIGHTS_STUDIO}

    def _flatten_directory(self, src_path: Path, dst_path: Path) -> int:
        """Helper to flatten a single directory structure."""
        if not src_path.exists():
            return 0

        # Create destination directory if it doesn't exist
        dst_path.mkdir(parents=True, exist_ok=True)
        
        # Collect all files first
        files_to_move: List[Path] = [f for f in src_path.rglob("*") if f.is_file()]
        
        if not files_to_move:
            return 0

        log.info(f"Flattening directory structure: {src_path.name} -> {dst_path.name} ({len(files_to_move)} files)")
        
        current_moved = 0
        for file_path in files_to_move:
            # Skip if already in destination root
            if file_path.parent == dst_path:
                continue
                
            target_path = dst_path / file_path.name
            
            if target_path.exists():
                log.warning(f"Target file exists, overwriting: {target_path}")
            
            try:
                shutil.move(str(file_path), str(target_path))
                current_moved += 1
            except Exception as e:
                log.error(f"Failed to move {file_path} to {target_path}: {e}")

        # Clean up empty nested directories
        cleanup_root = src_path
        
        for dir_path in sorted(cleanup_root.rglob('*'), key=lambda p: len(p.parts), reverse=True):
            if dir_path.is_dir() and dir_path != dst_path: # Don't delete the destination dir
                try:
                    dir_path.rmdir()
                except OSError:
                    pass # Directory not empty
        
        # If src path is different from dst path, try to remove src path itself if empty
        if src_path != dst_path and src_path.exists():
            try:
                src_path.rmdir()
            except OSError:
                pass
                
        return current_moved

    def process(self) -> None:
        """Flatten nested directories for configured paths."""
        total_moved = 0
        
        for src_rel, dst_rel in self.IMAGE_PATH_OVERRIDES.items():
            # Remove leading slash for path joining
            is_wildcard = src_rel.endswith("/*")
            clean_src_rel = src_rel.rstrip("/*") if is_wildcard else src_rel.lstrip("/")
            clean_dst_rel = dst_rel.lstrip("/")

            src_base = self._output_dir / clean_src_rel.strip("/")
            dst_base = self._output_dir / clean_dst_rel

            if not src_base.exists():
                continue

            if is_wildcard:
                # Iterate over first-level subdirectories
                # e.g. arts/characters/char_001, arts/characters/char_002
                for child in src_base.iterdir():
                    if child.is_dir():
                        # We want to flatten child into dst_base / child.name
                        # e.g. flatten arts/characters/char_001 -> arts/characters/char_001
                        # Note: usually dst_base corresponds to src_base in this case, 
                        # but we respect the config mapping.
                        target_dst = dst_base / child.name
                        total_moved += self._flatten_directory(child, target_dst)
            else:
                total_moved += self._flatten_directory(src_base, dst_base)

        if total_moved == 0:
            log.info("No files needed flattening.")
