import json
import os
import sys
import subprocess
from pathlib import Path

_BASE_DIR = Path(__file__).parent
_DEFAULT_VAULT = _BASE_DIR / 'vault'
_GALLERY_DL = _BASE_DIR / 'venv' / 'bin' / 'gallery-dl'

_STATE_SUBDIR = '.pixiv-vault'
_DL_SUBDIR = 'artworks'
_VIEW_SUBDIR = 'views'

_BOOKMARK_ORDER_FILE = 'bookmark_order.txt'
_BOOKMARK_ORDER_DROP_THRESHOLD = 0.01

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

        self._state_dir = self._vault_dir / _STATE_SUBDIR
        self._state_dir.mkdir(parents=True, exist_ok=True)
        self._dl_dir = self._vault_dir / _DL_SUBDIR
        self._dl_dir.mkdir(parents=True, exist_ok=True)
        self._view_dir = self._vault_dir / _VIEW_SUBDIR
        self._view_dir.mkdir(parents=True, exist_ok=True)

        self._order_file = self._state_dir / _BOOKMARK_ORDER_FILE
        self._order_drop_thres = _BOOKMARK_ORDER_DROP_THRESHOLD

        # Set API URLs
        self._bookmarks_url = f'https://www.pixiv.net/users/{self._user_id}/bookmarks/artworks'
        self._following_url = f'https://www.pixiv.net/users/{self._user_id}/following'

        # Use a custom config and import our refresh token from GPPT
        self._executable = [str(_GALLERY_DL)]
        self._base_args = self._executable + [
            '-o', f'cache.file={str(self._state_dir / "cache.sqlite3")}',
            '-o', f'extractor.pixiv.refresh-token={self._refresh_token}',
        ]
        self._download_args = self._base_args + [
            '--download-archive', str(self._state_dir / 'archive.sqlite'),
            '-o', 'skip=true',
            '-o', 'extractor.pixiv.directory=[]',
            '-o', 'extractor.pixiv.ugoira=true',
            '-o', ('extractor.pixiv.postprocessors='
               '[{"name":"ugoira","extension":"mkv",'
               '"ffmpeg-args":["-c:v","copy"],'
               '"repeat-last-frame":false}]'),
            '--directory', str(self._dl_dir),
        ]

        self._bookmarks_args = self._download_args + [
            '-o', 'metadata-bookmark=true',
            '-o', ('extractor.postprocessors='
               '[{"name":"metadata","event":["file","skip"]}]'),
            self._bookmarks_url,
        ]

        self._following_args = self._download_args + [
            '-o', 'extractor.postprocessors=[{"name":"metadata"}]',
            self._following_url,
        ]

        self._bookmarks_sort_args = self._base_args + [
            '--dump-json',
            self._bookmarks_url,
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

    def sort_bookmarks(self):
        # This function is some AI bs but it seems to do fine
        # Generates a .txt file with downloaded bookmarks in the order they were bookmarked by the user, since this isn't included in metadata.
        # Files in this list are kept there permanently, with removed bookmarks left in place but marked with a preceding '#' symbol. This is because we can't tell whether the bookmark was removed by the user, or the artwork was deleted/privated by the artist, and we want to preserve the order of deleted artworks in our local archive.
        order_file = self._order_file
        tmp_file = order_file.with_suffix(order_file.suffix + '.part')

        try:
            result = subprocess.run(self._bookmarks_sort_args, capture_output=True, text=True, check=True)
        except KeyboardInterrupt:
            print("\nCancelled bookmark sorting. (Keyboard interrupt)")
            res = input("Continue with download anyway? [y/N] ").strip().lower()
            if res in ('y', 'yes'):
                return
            else:
                raise
        items = json.loads(result.stdout)

        current: list[str] = []
        seen: set[str] = set()
        for item in items:
            # message type 3 = url-with-metadata
            if item[0] == 3:
                illust_id = str(item[2]['id'])
                if illust_id not in seen:
                    current.append(illust_id)
                    seen.add(illust_id)
        current_set = set(current)

        # --- Read prior state, if any ---
        prior: list[str] = []
        prior_active: list[str] = []
        if order_file.exists():
            for line in order_file.read_text().splitlines():
                line = line.rstrip()
                if not line:
                    continue
                prior.append(line)
                if not line.startswith('#'):
                    prior_active.append(line)

        # --- Sanity check: refuse to merge on suspicious drops ---
        if prior_active:
            drop = (len(prior_active) - len(current)) / len(prior_active)
            if drop > drop_threshold:
                raise RuntimeError(
                    f"Active bookmark count dropped from {len(prior_active)} "
                    f"to {len(current)} ({drop:.1%}); refusing to merge. "
                    f"Investigate manually; if real, delete or edit "
                    f"{order_file} and rerun."
                )

        # --- Find the boundary: topmost prior-active ID still present ---
        boundary_id: str | None = None
        for iid in prior_active:
            if iid in current_set:
                boundary_id = iid
                break

        # --- Compute new lines ---
        if boundary_id is None:
            # First run, or every prior bookmark was removed.
            # Prepend all current IDs; carry the prior file verbatim below.
            new_ids = current
            tail = prior
        else:
            # Current IDs above the boundary are genuinely new bookmarks.
            new_ids = current[:current.index(boundary_id)]
            # Tail starts at the boundary in the prior file (preserves order).
            tail = prior[prior.index(boundary_id):]

        new_lines: list[str] = list(new_ids)
        for entry in tail:
            if entry.startswith('#'):
                new_lines.append(entry)            # already removed, keep marked
            elif entry in current_set:
                new_lines.append(entry)            # still bookmarked
            else:
                new_lines.append(f'# {entry}')     # newly removed, mark out

        # --- Write atomically: temp file, then rename ---
        tmp_file.write_text('\n'.join(new_lines) + '\n')
        tmp_file.replace(order_file)
