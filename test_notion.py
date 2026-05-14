from notion_client import Client

from paper_ai_reader.config import load_settings

settings = load_settings(profile="cli")
notion = Client(auth=settings.notion_token)
database_id = settings.notion_database_id

# 1. 先读取 database
db = notion.databases.retrieve(database_id=database_id)

# 2. 取第一个 data source
data_source_id = db["data_sources"][0]["id"]

# 3. 查询 data source
res = notion.data_sources.query(data_source_id=data_source_id)

for page in res["results"]:
    props = page["properties"]

    title_prop = props.get("Title", {}).get("title", [])
    title = title_prop[0]["plain_text"] if title_prop else "(No title)"

    website = props.get("Website", {}).get("url", "(No URL)")

    print("Title:", title)
    print("Website:", website)
    print("Page ID:", page["id"])
    print("-----")
