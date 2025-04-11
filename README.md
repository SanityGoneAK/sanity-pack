# Sanity Data

A Python tool for extracting and processing game data from Arknights.

## Features

- Downloads game data using Arknights' hot update logic
- Unpacks Unity assets using UnityPy
- Decodes text assets using FlatBuffers
- Processes images:
  - Combines alpha and RGB images
  - Processes character portraits using image atlases

## Installation

1. Make sure you have Python 3.10+ installed
2. Install Poetry if you haven't already:
   ```bash
   curl -sSL https://install.python-poetry.org | python3 -
   ```
3. Clone the repository and install dependencies:
   ```bash
   git clone https://github.com/yourusername/sanity-data.git
   cd sanity-data
   poetry install
   ```

## Configuration

Create a `config.json` file with the following structure:

```json
{
  "server": "EN",  // Options: CN, EN, KR, JP
  "output_dir": "./output",
  "cache_dir": "./cache",
  "path_whitelist": [
    "chararts/",
    "portraits/"
  ]
}
```

## Usage

```bash
poetry run python -m sanity_data
```

## Development

- Format code: `poetry run black .`
- Sort imports: `poetry run isort .`
- Run tests: `poetry run pytest` 