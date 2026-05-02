import os
import sys
import util
from dotenv import load_dotenv
from pixivault import Vault

def run_stage(func, msg: str | None = None):
    if msg:
        print(msg + " (Ctrl+C to skip)")

    try:
        func()
    except KeyboardInterrupt:
        print("\nStage cancelled. (Keyboard interrupt)")
        if not util.confirm("Continue to next stage?"):
            raise

def main():
    load_dotenv()

    refresh_token = os.getenv("REFRESH_TOKEN")
    user_id = os.getenv("USER_ID")
    vault_dir = os.getenv("VAULT_DIR")

    vault = Vault(
        refresh_token=refresh_token,
        user_id=user_id,
        vault_dir=vault_dir,
    )

    do_bookmarks_order = util.env_bool("UPDATE_BOOKMARK_ORDER", True)
    do_bookmarks = util.env_bool("DOWNLOAD_BOOKMARKS", True)
    do_full_bookmarks = util.env_bool("FULL_BOOKMARK_METADATA", False)
    do_following = util.env_bool("DOWNLOAD_FOLLOWING", True)
    do_views = util.env_bool("GENERATE_VIEWS", True)
    do_newest_first = util.env_bool("VIEW_NEWEST_FIRST", False)
    do_statistics = util.env_bool("GENERATE_STATISTICS", True)

    try:
        if do_bookmarks_order:
            print("Saving bookmark order... (optional, press Ctrl+C to skip)")
            run_stage(vault.sort_bookmarks)

        if do_bookmarks:
            label = "full" if do_full_bookmarks else "fast"
            run_stage(lambda: vault.download_bookmarks(full=do_full_bookmarks),
                      f"Downloading bookmarks ({label}):")

        if do_following:
            run_stage(vault.download_following,
                      "Downloading followed artists:")

        if do_views:
            run_stage(lambda: vault.generate_bookmarks_view(newest_first=do_newest_first),
                      "Generating view for bookmarked works:")
            run_stage(vault.generate_media_view,
                      "Generating view for media-only:")
            run_stage(vault.generate_metadata_view,
                      "Generating view for metadata-only:")
            run_stage(vault.generate_artists_view,
                      "Generating view for works by artist:")

        if do_statistics:
            run_stage(vault.generate_statistics,
                      "Generating statistics:")
    except KeyboardInterrupt:
        print("Skipping remaining downloads.")
        sys.exit(130)

if __name__ == "__main__":
    main()
