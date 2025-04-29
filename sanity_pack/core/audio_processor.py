import os
import asyncio
from pathlib import Path
from typing import List, Set
from concurrent.futures import ThreadPoolExecutor

import aiofiles
from pydub import AudioSegment
from ..models.config import Config
from ..utils.logger import logger

async def convert_audio_file(wav_path: Path, mp3_path: Path) -> None:
    """
    Convert a single WAV file to MP3 format.
    
    Args:
        wav_path (Path): Path to the WAV file
        mp3_path (Path): Path where the MP3 file should be saved
    """
    try:
        # Load WAV file
        audio = AudioSegment.from_wav(str(wav_path))
        
        # Export as MP3 with good quality (192k bitrate)
        audio.export(
            mp3_path,
            format="mp3",
            bitrate="192k"
        )
        
        logger.info(f"Converted {wav_path.name} to MP3")
        
        # Remove original WAV file
        await aiofiles.os.remove(str(wav_path))
        
    except Exception as e:
        logger.error(f"Failed to convert {wav_path.name}: {str(e)}")
        raise

async def process_audio_files(config: Config) -> None:
    """
    Process WAV files from the assets directory and convert them to MP3 format concurrently.
    
    Args:
        config (Config): The configuration object containing output directory information.
    """
    output_dir = Path(config.output_dir)
    wav_files: List[Path] = []
    
    # Find all WAV files in the output directory
    for root, _, files in os.walk(output_dir):
        for file in files:
            if file.lower().endswith('.wav'):
                wav_files.append(Path(root) / file)
    
    if not wav_files:
        logger.info("No WAV files found to process")
        return
    
    logger.info(f"Found {len(wav_files)} WAV files to convert to MP3")
    
    # Create a semaphore to limit concurrent conversions
    semaphore = asyncio.Semaphore(35) 
    
    async def process_with_semaphore(wav_path: Path) -> None:
        async with semaphore:
            mp3_path = wav_path.with_suffix('.mp3')
            await convert_audio_file(wav_path, mp3_path)
    
    # Create tasks for all files
    tasks = [process_with_semaphore(wav_path) for wav_path in wav_files]
    
    # Run all tasks concurrently
    await asyncio.gather(*tasks)
    
    logger.info("Audio processing completed") 