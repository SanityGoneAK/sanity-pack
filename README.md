# Sanity Pack

A Python tool for extracting and processing game data from Arknights.

## Features

- Downloads game data using Arknights' hot update logic
- Unpacks Unity assets using UnityPy
- Processes images:
    - Combines alpha and RGB images
    - Processes character portraits using image atlases
- Decodes Text Assets
    - By Flatbuffers
    - By AES Encryption
- Transforms audio files form .wav into .mp3 for the web

### Unpack Drivers
Sanity pack has 2 main drivers to work from, UnityPy and ArknightsStudioCLI, for gamedata and flatbuffers UnityPy is recommended as it is faster. For other assets like images and spine data the ArknightsStudioCLI works better as it can detect better files structures. You can switch between these using the config where on `unpack_mode` is set to either `arknights_studio` or `unity_py`, when using arknights_studio you need to specify the DLL of the portable version (this is done so it can be used in all OS)

```json
"arknights_studio": {
    "cli_dll_path": "./ArknightsStudioCLI/ArknightsStudioCLI.dll"
},
```

### Flatc caveats
You can use the regular flatc binary to decode flatbuffers into JSON but it is recommended to use Mooncell's compiled flatc as it has some better defaults for resolving key value pairs and empty values. 

## Installation
1. Make sure you have Python 3.12+ installed
2. Install Poetry if you haven't already:
    ```bash
    curl -sSL https://install.python-poetry.org | python3 -
    ```
3. Install project
    ```bash
    poetry install
    ```
4. (Optional) Install ArknightsStudioCLI portable version
5. Add the flatc binary, make sure the permissions are set to executable, and update its path to the config.json
6. Run FBS commands
    - `poetry run sanity-pack download -c config.fbs.json`
    - `poetry run sanity-pack unpack -c config.fbs.json`
    - `poetry run sanity-pack fbs download && poetry run sanity-pack fbs decode -c config.fbs.json`
    - `poetry run sanity-pack fbs compile -c config.fbs.json`
7. Run poetry commands
    - `poetry run sanity-pack download`
    - `poetry run sanity-pack unpack`
    - `poetry run sanity-pack pipeline `

## Acknowledgements
`sanity-pack` would not be possible without these projects:
- [UnityPy](https://github.com/K0lb3/UnityPy)
- [arkdata](https://github.com/astral4/arkdata)
- [Ark-Unpacker](https://github.com/isHarryh/Ark-Unpacker)
- [ArkPRTS](https://github.com/thesadru/ArkPRTS)
- [ArknightsFlatbuffers](https://github.com/ArknightsAssets/ArknightsFlatbuffers)
- [OpenArknightsFBS](https://github.com/MooncellWiki/OpenArknightsFBS)