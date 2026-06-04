import json
import os
import re
import sys
import subprocess
from collections import Counter
from pathlib import Path

_BASE_DIR = Path(__file__).parent
_OUTER_DIR = _BASE_DIR.parent
_DEFAULT_VAULT = _OUTER_DIR / 'vault'

_MINOR_SEPARATOR = '_'
_MAJOR_SEPARATOR = '-'

_STATE_SUBDIR = '.pixiv-vault'
_DL_SUBDIR = 'artworks'
_VIEW_SUBDIR = 'views'
_BOOKMARKS_VIEW_SUBDIR = 'bookmarks'
_MEDIA_VIEW_SUBDIR = 'media'
_METADATA_VIEW_SUBDIR = 'metadata'
_ARTISTS_VIEW_SUBDIR = 'artists'
_NEW_VIEW_SUBDIR = 'new'
_STATISTICS_SUBDIR = 'statistics'

_BOOKMARK_ORDER_FILE = 'bookmark_order.txt'
_BOOKMARK_ORDER_DROP_THRESHOLD = 0.01

_MAX_ATTEMPTS = 10
_CURSOR_RE = re.compile(r"-o cursor=(\d+)")

class Vault:
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
        self._view_dir = self._vault_dir / _VIEW_SUBDIR
        self._bookmarks_view_dir = self._view_dir / _BOOKMARKS_VIEW_SUBDIR
        self._media_view_dir = self._view_dir / _MEDIA_VIEW_SUBDIR
        self._metadata_view_dir = self._view_dir / _METADATA_VIEW_SUBDIR
        self._artists_view_dir = self._view_dir / _ARTISTS_VIEW_SUBDIR
        self._new_view_dir = self._view_dir / _NEW_VIEW_SUBDIR
        self._statistics_dir = self._vault_dir / _STATISTICS_SUBDIR

        self._order_file = self._state_dir / _BOOKMARK_ORDER_FILE
        self._order_drop_thres = _BOOKMARK_ORDER_DROP_THRESHOLD

        self._gallery_dl = (_BASE_DIR / 'venv' / 'Scripts' / 'gallery-dl.exe'
                            if os.name == 'nt'
                            else _BASE_DIR / 'venv' / 'bin' / 'gallery-dl')
        if not self._gallery_dl.exists():
            print("WARNING: gallery-dl not found. Download functions will be "
                  "unavailable. Try running setup again.")

        # Set API URLs
        self._artworks_url_prefix = 'https://www.pixiv.net/artworks/'
        self._bookmarks_url = f'https://www.pixiv.net/users/{self._user_id}/bookmarks/artworks'
        self._following_url = f'https://www.pixiv.net/users/{self._user_id}/following'

        self._index: dict[str, list[tuple[int, str]]] = None

        # Use a custom config and import our refresh token from GPPT
        self._executable = str(self._gallery_dl)
        self._base_args = [self._executable] + [
            '-o', f'cache.file={str(self._state_dir / "cache.sqlite3")}',
            '-o', f'extractor.pixiv.refresh-token={self._refresh_token}',
        ]
        self._download_args = self._base_args + [
            '--download-archive', str(self._state_dir / 'archive.sqlite'),
            '-o', 'skip=true',
            '-o', 'extractor.pixiv.directory=[]',
            '-o', 'extractor.pixiv.ugoira=true',
            '-o', 'extractor.pixiv.tags=original',
            '-o', ('extractor.pixiv.postprocessors='
               '[{"name":"ugoira","extension":"mkv",'
               '"ffmpeg-args":["-c:v","copy"],'
               '"repeat-last-frame":false}]'),
            '--directory', str(self._dl_dir),
        ]

        self._artworks_args = self._download_args + [
            '-o', 'metadata-bookmark=true',
            '-o', ('extractor.postprocessors='
               '[{"name":"metadata","event":["file","skip"]}]'),
        ]

        self._bookmarks_args = self._download_args + [
            '-o', 'extractor.postprocessors=[{"name":"metadata"}]',
            self._bookmarks_url,
        ]
        self._full_bookmarks_args = self._download_args + [
            '-o', 'metadata-bookmark=true',
            '-o', ('extractor.postprocessors='
               '[{"name":"metadata","event":["file","skip"]}]'),
            self._bookmarks_url,
        ]

        self._following_args = self._download_args + [
            '-o', 'extractor.postprocessors=[{"name":"metadata"}]',
            self._following_url,
        ]

        self._sort_bookmarks_args = self._base_args + [
            '--dump-json',
            self._bookmarks_url,
        ]

    def _download(self, args, capture=False):
        cursor: str | None = None

        self._dl_dir.mkdir(parents=True, exist_ok=True)

        if not Path(self._executable).exists():
            print(f"ERROR: Download helper not found. Checked "
                  f"`{self._executable}'.", file=sys.stderr)
            sys.exit(1)

        for i in range(_MAX_ATTEMPTS):
            if cursor is not None:
                print(f"An error occurred, but may be recoverable using the cursor {cursor}. Restarting download... (attempt {i})")
                args = args + ['-o', f'cursor={cursor}']

            dl = subprocess.run(args,
                                stdout=subprocess.PIPE if capture else None,
                                stderr=subprocess.PIPE,
                                text=True)

            if dl.returncode == 0:
                return dl.stdout if capture else None

            if dl.returncode == 130:
                print("\nDownload stopped. (Keyboard interrupt)")
                raise KeyboardInterrupt()

            print("An error occurred:")

            if dl.stderr:
                print(dl.stderr, end='', flush=True)

            match = None
            for line in dl.stderr.splitlines():
                m = _CURSOR_RE.search(line)
                if m:
                    match = m

            if not match:
                raise subprocess.CalledProcessError(dl.returncode, args, stderr=dl.stderr)

            cursor = match.group(1)

        raise RuntimeError(f"Maximum download attempts reached. gallery-dl exited in failure {_MAX_ATTEMPTS} times.")

    def download_artwork(self, artwork_id):
        args = self._artworks_args + [self._artworks_url_prefix + str(artwork_id)]
        self._download(args)

    def download_bookmarks(self, full = False):
        args = self._full_bookmarks_args if full else self._bookmarks_args
        self._download(args)

    def download_following(self):
        self._download(self._following_args)

    def sort_bookmarks(self):
        # This function is some AI bs but it seems to do fine
        # Generates a .txt file with downloaded bookmarks in the order they were bookmarked by the user, since this isn't included in metadata.
        # Files in this list are kept there permanently, with removed bookmarks left in place but marked with a preceding '#' symbol. This is because we can't tell whether the bookmark was removed by the user, or the artwork was deleted/privated by the artist, and we want to preserve the order of deleted artworks in our local archive.
        order_file = self._order_file
        tmp_file = order_file.with_suffix(order_file.suffix + '.part')

        stdout = self._download(self._sort_bookmarks_args, capture=True)
        items = json.loads(stdout)

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
            if drop > self._order_drop_thres:
                raise RuntimeError(
                    f"Active bookmark count dropped from {len(prior_active)} "
                    f"to {len(current)} ({drop:.1%}); refusing to merge. "
                    f"Investigate manually; if real, delete or edit "
                    f"{order_file} and rerun."
                )

        # --- Find the boundary: topmost prior-active ID still present ---
        boundary_id: str | None = None
        for iid in reversed(prior_active):
            if iid in current_set:
                boundary_id = iid
                break

        # --- Compute new lines ---
        if boundary_id is None:
            # First run, or every prior bookmark was removed.
            # Prepend all current IDs; carry the prior file verbatim below.
            new_ids = list(reversed(current))
            head = prior
        else:
            # Current IDs above the boundary are genuinely new bookmarks.
            new_ids = list(reversed(current[:current.index(boundary_id)]))
            # Tail starts at the boundary in the prior file (preserves order).
            head = prior[:prior.index(boundary_id) + 1]

        new_lines: list[str] = []
        for entry in head:
            if entry.startswith('#'):
                new_lines.append(entry)            # already removed, keep marked
            elif entry in current_set:
                new_lines.append(entry)            # still bookmarked
            else:
                new_lines.append(f'# {entry}')     # newly removed, mark out
        new_lines.extend(new_ids)

        # --- Write atomically: temp file, then rename ---
        tmp_file.write_text('\n'.join(new_lines) + '\n')
        tmp_file.replace(order_file)

    def _index_artworks(self):
        if self._index is not None:
            return self._index
        # Index all artworks
        # Specifically designed for current pixiv filename format:
        # {id}_p{page}.{jpg/png/mkv/zip}
        # Filters sidecars by only allowing one "."
        fname_re = re.compile(r"^(\d+)_p(\d+)\.[^.]+$")
        # {illust_id: [(page1, filename), (page2, filename), ...], ...}
        index: dict[str, list[tuple[int, str]]] = {}
        for entry in os.scandir(self._dl_dir):
            # Explicit check, largely unnecessary
            if entry.name.endswith('.json'):
                continue
            f = fname_re.match(entry.name)
            if not f:
                continue
            illust_id, page = f.group(1), int(f.group(2))
            index.setdefault(illust_id, []).append((page, entry.name))
        for illust in index:
            index[illust].sort()
        self._index = index
        return self._index

    def _reset_view_dir(self, view: Path):
        if view.exists():
            for entry in os.scandir(view):
                if entry.is_dir():
                    self._remove_tree(Path(entry.path))
                else:
                    os.unlink(entry.path)
        else:
            view.mkdir(parents=True)

    def _remove_tree(self, path: Path):
        for entry in os.scandir(path):
            if entry.is_dir():
                self._remove_tree(Path(entry.path))
            else:
                os.unlink(entry.path)
        os.rmdir(path)

    def generate_bookmarks_view(self, newest_first = False):
        if not self._order_file.exists():
            raise RuntimeError(f"No bookmark order file at {str(self._order_file)}. Run sort_bookmarks() first.")

        # Get ordered list of bookmarks
        # [(illust_id, removed?), ...]
        order: list[tuple[str, bool]] = []
        for line in self._order_file.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            is_removed = line.startswith('#')
            illust_id = line.lstrip('#').strip()
            order.append((illust_id, is_removed))

        if newest_first:
            order.reverse()

        index = self._index_artworks()

        # Determine necessary padding of numbers
        pos_width = max(len(str(len(order) - 1)), 1)
        max_pages = max((len(pages) for pages in index.values()), default=1)
        page_width = max(len(str(max_pages - 1)), 1)

        # Nuke existing bookmarks view
        view = self._bookmarks_view_dir
        self._reset_view_dir(view)

        rel_prefix = os.path.relpath(self._dl_dir, view)

        # Create symlinks
        created = 0
        missing = 0
        for pos, (illust_id, is_removed) in enumerate(order):
            pages = index.get(illust_id)
            if not pages:
                missing += 1
                continue
            for page, fname in pages:
                link_name = f"{pos:0{pos_width}d}{_MINOR_SEPARATOR}{page:0{page_width}d}{_MAJOR_SEPARATOR}{fname}"
                os.symlink(f"{rel_prefix}/{fname}", view / link_name)
                created += 1

        if missing:
            print(f"Note: {missing} bookmarked illust(s) had no files in "
                  f"{self._dl_dir} (probably not yet downloaded).",
                  file=sys.stderr)
        print(f"Generated bookmarks view: {created} symlinks in {view}")

    def generate_media_view(self):
        view = self._media_view_dir

        index = self._index_artworks()
        self._reset_view_dir(view)

        # Determine padding for lexical ordering
        max_id_len = max((len(illust_id) for illust_id in index), default=1)
        max_pages = max((len(pages) for pages in index.values()), default=1)
        page_width = max(len(str(max_pages - 1)), 1)

        rel_prefix = os.path.relpath(self._dl_dir, view)

        created = 0
        for illust_id in index:
            for page, fname in index[illust_id]:
                link_name = f"{illust_id:>0{max_id_len}}{_MINOR_SEPARATOR}{page:0{page_width}d}{_MAJOR_SEPARATOR}{fname}"
                os.symlink(f"{rel_prefix}/{fname}", view / link_name)
                created += 1

        print(f"Generated media-only view: {created} symlinks in {view}")

    def generate_metadata_view(self):
        view = self._metadata_view_dir

        index = self._index_artworks()
        self._reset_view_dir(view)

        rel_prefix = os.path.relpath(self._dl_dir, view)

        max_id_len = max((len(illust_id) for illust_id in index), default=1)
        max_pages = max((len(pages) for pages in index.values()), default=1)
        page_width = max(len(str(max_pages - 1)), 1)

        created = 0
        missing = 0
        for illust_id in index:
            for page, fname in index[illust_id]:
                sidecar = fname + '.json'
                if not (self._dl_dir / sidecar).exists():
                    missing += 1
                    continue
                link_name = f"{illust_id:>0{max_id_len}}{_MINOR_SEPARATOR}{page:0{page_width}d}{_MAJOR_SEPARATOR}{sidecar}"
                os.symlink(f"{rel_prefix}/{sidecar}", view / link_name)
                created += 1

        if missing:
            print(f"Note: {missing} artworks had no .json sidecars in "
                  f"{self._dl_dir} (were they manually deleted?).",
                  file=sys.stderr)
        print(f"Generated metadata-only view: {created} symlinks in {view}")

    def generate_artists_view(self):
        view = self._artists_view_dir

        index = self._index_artworks()

        # {(user_id, account): {illust_id: [(page, fname), (...)], [...]}, {...}}
        artists: dict[tuple[str, str], dict] = {}
        bad_sidecars = 0
        for illust_id, files in index.items():
            sidecar_path = self._dl_dir / (files[0][1] + '.json')
            if not sidecar_path.exists():
                bad_sidecars += 1
                continue
            try:
                data = json.loads(sidecar_path.read_text())
                user = data['user']
                user_id = str(user['id'])
                account = user.get('account') or 'unknown'
                is_followed = bool(user.get('is_followed', False))
            except (json.JSONDecodeError, KeyError, TypeError):
                bad_sidecars += 1
                continue
            key = (user_id, account)
            artist = artists.setdefault(key, {'illusts': {}, 'is_followed': is_followed})
            artist['illusts'][illust_id] = files
            artist['is_followed'] = is_followed

        # Get followed status from highest ID artwork
        for key, artist in artists.items():
            latest = max(artist['illusts'], key=int)
            sidecar = self._dl_dir / (artist['illusts'][latest][0][1] + '.json')
            try:
                data = json.loads(sidecar.read_text())
                artist['is_followed'] = bool(data['user'].get('is_followed', False))
            except (FileNotFoundError, json.JSONDecodeError, KeyError, TypeError):
                # Already set by random artwork or default of False
                pass

        self._reset_view_dir(view)

        rel_prefix = os.path.relpath(self._dl_dir, view)

        created = 0
        followed = 0
        unfollowed = 0
        for (user_id, account), artist in artists.items():
            if artist['is_followed']:
                followed += 1
            else:
                unfollowed += 1
            artist_dir = view / ('followed' if artist['is_followed'] else 'unfollowed') / f"{account}_{user_id}"
            artist_dir.mkdir(parents=True, exist_ok=True)
            
            artist_index = artist['illusts']

            max_id_len = max((len(illust_id) for illust_id in artist_index))
            max_pages = max((len(pages) for pages in artist_index.values()))
            page_width = max(len(str(max_pages - 1)), 1)

            artist_rel_prefix = os.path.relpath(self._dl_dir, artist_dir)

            for illust_id, files in artist_index.items():
                for page, fname in files:
                    link_name = f"{illust_id:>0{max_id_len}}_{page:0{page_width}d}_{fname}"
                    os.symlink(f"{artist_rel_prefix}/{fname}", artist_dir / link_name)
                    created += 1

        if bad_sidecars:
            print(f"Note: {bad_sidecars} .json metadata sidecars failed to load "
                  f"from {self._dl_dir} (were they deleted?).",
                  file=sys.stderr)
 
        print(f"Generated artists view: {len(artists)} artists ({followed} followed, {unfollowed} unfollowed), {created} symlinks in {view}")

    def generate_new_view(self):
        view = self._new_view_dir

        index = self._index_artworks()

        # Collect (create_date, illust_id, files) for all works
        entries: list[tuple[str, str, list]] = []
        bad_sidecars = 0
        for illust_id, files in index.items():
            sidecar_path = self._dl_dir / (files[0][1] + '.json')
            if not sidecar_path.exists():
                bad_sidecars += 1
                continue
            try:
                data = json.loads(sidecar_path.read_text())
                create_date = data['create_date']
            except (json.JSONDecodeError, KeyError, TypeError):
                bad_sidecars += 1
                continue
            entries.append((create_date, illust_id, files))

        entries.sort(key=lambda e: e[0], reverse=True)

        self._reset_view_dir(view / 'all')
        all_prefix = os.path.relpath(self._dl_dir, view / 'all')

        # Determine necessary padding of numbers
        pos_width = max(len(str(len(entries) - 1)), 1)
        max_pages = max((len(files) for _, _, files in entries), default=1)
        page_width = max(len(str(max_pages - 1)), 1)

        created = 0
        for pos, (create_date, illust_id, files) in enumerate(entries):
            for page, fname in files:
                link_name = f"{pos:0{pos_width}d}{_MINOR_SEPARATOR}{page:0{page_width}d}{_MAJOR_SEPARATOR}{fname}"
                os.symlink(f"{all_prefix}/{fname}", view / 'all' / link_name)
                created += 1

        if bad_sidecars:
            print(f"Note: {bad_sidecars} .json metadata sidecars failed to load "
                  f"from {self._dl_dir} (were they deleted?).",
                  file=sys.stderr)
        print(f"Generated new works view: {created} symlinks in {view / 'all'}")

    def _write_counts(self, path: Path, rows: list[tuple], delim: str = '\t'):
        if not rows:
            path.write_text('')
            return

        width = len(str(max(row[0] for row in rows)))
        sorted_rows = sorted(rows, key=lambda r: (-r[0], r[1:]))
        lines = [
            f"{row[0]:>{width}}\t" + '\t'.join(row[1:])
            for row in sorted_rows
        ]

        path.write_text('\n'.join(lines) + '\n')

    def generate_statistics(self):
        stats_dir = self._statistics_dir
        stats_dir.mkdir(parents=True, exist_ok=True)

        index = self._index_artworks()

        tags: Counter[str] = Counter()
        tags_bookmarked: Counter[str] = Counter()
        translations: dict[str, str] = {}

        bad_sidecars = 0
        for illust_id, files in index.items():
            sidecar_path = self._dl_dir / (files[0][1] + '.json')
            if not sidecar_path.exists():
                bad_sidecars += 1
                continue
            try:
                data = json.loads(sidecar_path.read_text())
                is_bookmarked = bool(data.get('is_bookmarked', False))
                sidecar_tags = data.get('tags', [])
            except (json.JSONDecodeError, KeyError, TypeError):
                bad_sidecars += 1
                continue

            for tag in sidecar_tags:
                if isinstance(tag, dict):
                    name = tag.get('name')
                    translated = tag.get('translated_name')
                elif isinstance(tag, str):
                    name = tag
                    translated = None
                else:
                    continue
                if not name:
                    continue
                tags[name] += 1
                if is_bookmarked:
                    tags_bookmarked[name] += 1
                if translated:
                    translations[name] = translated.replace('\t', ' ')

        rows = [(count, tag, translations.get(tag, ''))
                for tag, count in tags.items()]
        rows_bookmarked = [(count, tag, translations.get(tag, ''))
                           for tag, count in tags_bookmarked.items()]

        self._write_counts(stats_dir / 'tag_counts.txt', rows)
        self._write_counts(stats_dir / 'tag_counts_bookmarked.txt', rows_bookmarked)

        if bad_sidecars:
            print(f"Note: {bad_sidecars} .json metadata sidecars failed to load from {self._dl_dir} (were they deleted?)")
 
        print(f"Generated tag statistics: {len(tags)} unique tags, {len(tags_bookmarked)} in bookmarks.")
