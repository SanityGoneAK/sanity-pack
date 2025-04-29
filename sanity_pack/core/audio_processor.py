import os
from pathlib import Path
from typing import List

from pydub import AudioSegment
from ..models.config import Config
from ..utils.logger import logger

def process_audio_files(config: Config) -> None:
    """
    Process WAV files from the assets directory and convert them to MP3 format.
    
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
    
    for wav_path in wav_files:
        try:
            # Load WAV file
            audio = AudioSegment.from_wav(str(wav_path))
            
            # Create MP3 path
            mp3_path = wav_path.with_suffix('.mp3')
            
            # Export as MP3 with good quality (192k bitrate)
            audio.export(
                mp3_path,
                format="mp3",
                bitrate="192k"
            )
            
            logger.debug(f"Converted {wav_path.name} to MP3")
            
            # Remove original WAV file
            wav_path.unlink()
            
        except Exception as e:
            logger.error(f"Failed to convert {wav_path.name}: {str(e)}")
            continue
    
    logger.info("Audio processing completed") 