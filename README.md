# stem-extractor

Web UI for [demucs](https://github.com/adefossez/demucs) stem separation. Drag and drop an audio file, pick a model and output format, get stems back as a zip.

## Usage

Requires `demucs` to be installed and in your PATH.

```
uv run app.py
```

Then go to `http://localhost:5000`.

Optionally configure host and port: `uv run app.py 0.0.0.0 8080`

## Supported models

- `htdemucs_6s` — 6 stems (vocals, drums, bass, guitar, piano, other)
- `htdemucs` — 4 stems (vocals, drums, bass, other)
- `hdemucs_mmi` — 4 stems (vocals, drums, bass, other)
