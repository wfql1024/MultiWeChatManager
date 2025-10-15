import requests
import os

# 仓库信息
owner = "wfql1024"
repo = "MultiWeChatManager"
branch = "master"
path = "utils"

# GitHub API 请求 URL
url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}?ref={branch}"

# 发送 API 请求
response = requests.get(url)
response.raise_for_status()  # 检查请求是否成功

# 下载文件
for file in response.json():
    file_url = file["download_url"]
    file_name = os.path.join(r"E:\Now\Inbox\test", file["name"])

    file_response = requests.get(file_url)
    file_response.raise_for_status()

    with open(file_name, "wb") as f:
        f.write(file_response.content)

print(f"Files from '{path}' downloaded successfully.")