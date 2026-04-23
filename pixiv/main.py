import dotenv
import os
from pixivpy3 import AppPixivAPI

envfile = dotenv.find_dotenv()
dotenv.load_dotenv(envfile)

refresh_token = os.environ["REFRESH_TOKEN"]
user_id = os.environ["USER_ID"]

api = AppPixivAPI()
api.auth(refresh_token=refresh_token)
print(api.search_user("example"))
