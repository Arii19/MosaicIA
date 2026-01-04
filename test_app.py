import os

import requests
from dotenv import load_dotenv

load_dotenv()

token = os.getenv("GITLAB_TOKEN")
if not token:
    raise RuntimeError("Defina GITLAB_TOKEN no .env ou no ambiente antes de testar.")

url = "https://gitlab.com/arii19-group/Arii19-project/-/wikis/home"
headers = {"PRIVATE-TOKEN": token}
resp = requests.get(url, headers=headers, timeout=30)
print(resp.status_code, resp.text[:200])