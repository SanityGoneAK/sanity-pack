# Sanity Data

A Python tool for extracting and processing game data from Arknights.

## Features

- Downloads game data using Arknights' hot update logic
- Unpacks Unity assets using UnityPy
- Processes images:
  - Combines alpha and RGB images
  - Processes character portraits using image atlases
- Decodes Text Assets
  - By Flatbuffers using https://github.com/MooncellWiki/OpenArknightsFBS
  - By AES Encryption

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
4. Initialize and update the FlatBuffers submodules:
   ```bash
   git submodule update --init --recursive
   ```

## Configuration

Create a `config.json` file with the following structure:

```json
{
  "output_dir": "./assets",
  "cache_dir": "./cache",
  "servers": { // Options: CN, EN, KR, JP
    "CN": {
      "enabled": true,
      "path_whitelist": [
        "chararts/",
        "portraits/"
      ]
    }
  }
}
```

## Usage

```bash
# Run the main tool
poetry run python -m sanity_data

# Compile FlatBuffers schemas
poetry run compile-fbs
```

## Development

- Format code: `poetry run black .`
- Sort imports: `poetry run isort .`
- Run tests: `poetry run pytest` 

## Acknowledgements

`sanity-data` would not be possible without these projects:
- [UnityPy](https://github.com/K0lb3/UnityPy)
- [Ark-Unpacker](https://github.com/isHarryh/Ark-Unpacker)
- [OpenArknightsFBS](https://github.com/MooncellWiki/OpenArknightsFBS)