from gppt import GetPixivToken
import asyncio
import dotenv
import os

def _origin_module(exc):
    tb = exc.__traceback__
    if tb is None:
        return None
    while tb.tb_next is not None:
        tb = tb.tb_next
    return tb.tb_frame.f_globals.get("__name__")

def print_chain(exc):
    seen = set()
    current = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        module = _origin_module(current)
        prefix = f"[{module}] " if module else ""
        print(f"{prefix}{type(current).__name__}: {current}")
        current = current.__cause__ or current.__context__

async def main():
    # Read settings
    envfile = dotenv.find_dotenv()
    if not envfile:
        print("No .env file found. Please create one at a common directory to" \
                "this authentication program and your pixiv-dl installation" \
                "(e.g. run `touch ../.env`)")
    dotenv.load_dotenv(envfile)
    username = os.getenv("USERNAME")
    password = os.getenv("PASSWORD")

    if (username and password):
        # Log in headlessly
        print("Logging in headlessly...")
        g = GetPixivToken(headless=True)
        ret = await g.login(username=username, password=password)
    else:
        # Log in manually
        print("Launching browser for manual log-in...")
        g = GetPixivToken(headless=False)
        try:
            ret = await g.login()
        except Exception as e:
            print_chain(e)
            print("Failed to authenticate. Please run './pixiv-dl login' again.")
            exit(1)

    print("")
    # Extract data needed for pixiv-dl
    refresh_token = ret["refresh_token"]
    if not refresh_token:
        print("Failed to get refresh_token. This may be a bug with GPPT!")
        exit(1)
    print(f"Refresh Token: {refresh_token}")
    user_id = ret["user"]["id"]
    if not user_id:
        print("Failed to get user id. This may be a bug with GPPT!")
        exit(1)
    print(f"User ID: {user_id}")
    
    # Save credentials to .env file
    dotenv.set_key(envfile, "REFRESH_TOKEN", refresh_token)
    dotenv.set_key(envfile, "USER_ID", user_id)

    print(f"Credentials saved to '{os.path.relpath(envfile)}'.")

if __name__ == "__main__":
    asyncio.run(main())
