import os
import sys
import util
from dotenv import load_dotenv
from downloader import GalleryDL

def run_stage(func, msg: str | None = None):
    if msg:
        print(msg)

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

    try:
        run_stage(gdl.sort_bookmarks,
                  "Saving bookmark order... (optional, press Ctrl+C to skip)")
        run_stage(gdl.download_bookmarks,
                  "Downloading bookmarks: (Ctrl+C to skip)")
        run_stage(gdl.download_following,
                  "Downloading followed artists: (Ctrl+C to skip)")
    except KeyboardInterrupt:
        print("Skipping remaining downloads.")
        sys.exit(130)

if __name__ == "__main__":
    main()
