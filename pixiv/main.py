import os
import sys
import util
from dotenv import load_dotenv
from downloader import GalleryDL

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

    gdl = GalleryDL(
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

    try:
        if do_bookmarks_order:
            print("Saving bookmark order... (optional, press Ctrl+C to skip)")
            run_stage(gdl.sort_bookmarks)

        if do_bookmarks:
            label = "full" if do_full_bookmarks else "fast"
            run_stage(lambda: gdl.download_bookmarks(full=do_full_bookmarks),
                      f"Downloading bookmarks ({label}):")

        if do_following:
            run_stage(gdl.download_following,
                      "Downloading followed artists:")

        if do_views:
            run_stage(lambda: gdl.generate_bookmarks_view(newest_first=do_newest_first),
                      "Generating view for bookmarked works:")
            run_stage(gdl.generate_media_view,
                      "Generating view for media-only:")
            run_stage(gdl.generate_metadata_view,
                      "Generating view for metadata-only:")
    except KeyboardInterrupt:
        print("Skipping remaining downloads.")
        sys.exit(130)

if __name__ == "__main__":
    main()
