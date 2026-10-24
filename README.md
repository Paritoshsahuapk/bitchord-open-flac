# Open FLAC Search — BitChord add-on

A small self-hosted BitChord add-on that searches Internet Archive audio items and only returns recordings with an actual `.flac` file in the item's public metadata.

## Important limitations

- This is a source project, **not a hosted public URL**. You must deploy it to a host you control before adding it to BitChord.
- Internet Archive is not a complete commercial music catalogue. It will miss many current Punjabi, Bollywood and English chart releases.
- Use BitChord's built-in YouTube Music source as a discovery/fallback source, and keep this add-on enabled for legal open recordings.
- A `.flac` file can itself have been transcoded from a lossy master. This add-on verifies the file/container, not the provenance of the original master.
- Respect each recording's rights and Internet Archive's terms. This add-on does not bypass paywalls, DRM, logins, or provider restrictions.

## Deploy with a Docker-capable host

1. Create a new repository and upload the files in this folder.
2. Deploy the repository to a Docker-capable hosting service that provides a public HTTPS URL.
3. The service should run the included Dockerfile. If your host uses a start command instead, use:
   `gunicorn --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 30 server:app`
4. Open `https://YOUR-HOST/health` and confirm it returns `{"ok":true,...}`.
5. Open `https://YOUR-HOST/manifest.json` and confirm it returns the manifest.
6. In BitChord, open **Settings → Sources → Add an addon** and paste:
   `https://YOUR-HOST/manifest.json`
   Replace `YOUR-HOST` with your actual deployment hostname. This placeholder is not a working link.

## Local test

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python server.py
```

Then test:
- `http://127.0.0.1:8080/manifest.json`
- `http://127.0.0.1:8080/search?q=classical`
- `http://127.0.0.1:8080/health`

A local URL only works on your own device/network; BitChord on your phone needs a reachable host.

## Routes

- `GET /manifest.json`
- `GET /search?q=<search terms>&limit=20`
- `GET /stream/<Internet-Archive-identifier>`
- `GET /health`

The server checks each search result's metadata and only includes it if it has a public FLAC file. It returns direct HTTPS URLs from Internet Archive, not proxied media.

## Troubleshooting

- **No results:** Internet Archive may not have a matching FLAC recording. Try a broader search such as an artist name or album.
- **Manifest rejected:** Check the BitChord version and its current add-on guide; the host must serve valid JSON over HTTPS.
- **Playback fails:** The recording may be unavailable, removed, or not directly playable. Try another result.
