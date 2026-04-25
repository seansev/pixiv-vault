import os
import sys
from dotenv import load_dotenv
from downloader import GalleryDL

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

    print("Downloading bookmarks:")
    gdl.download_bookmarks()

    print("Downloading followed artists:")
    gdl.download_following()

if __name__ == "__main__":
    main()
