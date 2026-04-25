import os
import sys
import subprocess
from pathlib import Path

_BASE_DIR = Path(__file__).parent
_DEFAULT_VAULT = _BASE_DIR / 'vault'
_GALLERY_DL = _BASE_DIR / 'venv' / 'bin' / 'gallery-dl'

class GalleryDL:
    def __init__(self, refresh_token: str, user_id: str, vault_dir: str | None = None):
        self._refresh_token = refresh_token
        if not self._refresh_token:
            raise ValueError("No refresh token provided! Log into Pixiv before attempting to download.")

        self._user_id = user_id
        if not self._user_id:
            raise ValueError("No Pixiv user ID provided! Log into Pixiv or regenerate your .env file before attempting to download.")

        self._vault_dir = Path(os.path.expandvars(vault_dir)).expanduser() if vault_dir else _DEFAULT_VAULT
        if not vault_dir:
            print(f"WARNING: No vault directory provided! Using {str(_DEFAULT_VAULT)}", file=sys.stderr)
        self._vault_dir.mkdir(parents=True, exist_ok=True)

        # Use a custom config and import our refresh token from GPPT
        self._base_args = [
            str(_GALLERY_DL),
            '--directory', str(self._vault_dir),
            '-o', f'cache.file={str(_BASE_DIR / "cache.sqlite3")}',
            '-o', f'extractor.pixiv.refresh-token={self._refresh_token}',
            '-o', 'extractor.pixiv.directory=[]',
            '-o', 'extractor.pixiv.ugoira=copy',
            '-o', 'extractor.postprocessors=[{"name":"metadata"}]',
        ]

        # Use separate archive DBs for bookmarks and following. This allows us to use a flat layout while still tricking gallery-dl into redownloading files when they become bookmarked, updating the metadata to reflect this change. Works will never be un-bookmarked in the local copy.
        self._bookmarks_args = self._base_args + [
            '--download-archive', str(_BASE_DIR / 'archive_bookmarks.sqlite'),
            #'-o', 'skip=false',
            f'https://www.pixiv.net/users/{self._user_id}/bookmarks/artworks',
        ]

        self._following_args = self._base_args + [
            '--download-archive', str(_BASE_DIR / 'archive_following.sqlite'),
            '-o', 'skip=true',
            f'https://www.pixiv.net/users/{self._user_id}/following',
        ]

    def _download(self, args):
        try:
            subprocess.run(args, check=True)
        except KeyboardInterrupt:
            print("\nDownload stopped. (Keyboard interrupt)")
            raise

    def download_bookmarks(self):
        self._download(self._bookmarks_args)

    def download_following(self):
        self._download(self._following_args)
