from notion_client import Client

from paper_ai_reader.config import load_settings

settings = load_settings(profile="cli")
notion = Client(auth=settings.notion_token)

page_id = "3526e7e4-145f-8104-b3dc-e4b8443462a6"

res = notion.blocks.children.list(block_id=page_id)

for block in res["results"]:
    block_type = block["type"]

    text = ""
    if "rich_text" in block.get(block_type, {}):
        rich_text = block[block_type]["rich_text"]
        text = rich_text[0]["plain_text"] if rich_text else ""

    print(block_type, ":", text)
