from gppt import GetPixivToken
import asyncio
import dotenv
import os

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
        ret = await g.login()

    print("")
    # Extract data needed for pixiv-dl
    refresh_token = ret["refresh_token"]
    print(f"Refresh Token: {refresh_token}")
    user_id = ret["user"]["id"]
    print(f"User ID: {user_id}")
    
    # Save credentials to .env file
    dotenv.set_key(envfile, "REFRESH_TOKEN", refresh_token)
    dotenv.set_key(envfile, "USER_ID", user_id)

    print(f"Credentials saved to '{os.path.relpath(envfile)}'.")

if __name__ == "__main__":
    asyncio.run(main())
