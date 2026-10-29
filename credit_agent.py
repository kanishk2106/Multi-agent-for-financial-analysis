from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_agent
from langchain.mcp import MCPAdapter
import json
from dotenv import load_dotenv
load_dotenv()
from pathlib import Path
import asyncio

with open("registry.json", "r") as file:
    config=json.load(file)["agents"]["credit_card"]
async def provide_agent():
    async with MCPAdapter(config["server"]) as adapter:
        tools = await adapter.list_tools()
        model=ChatGoogleGenerativeAI(model=config["model"], temperature=config["temperature"], max_output_tokens=config["max_output_tokens"])
        return create_agent(model,tools,system_prompt=Path("prompts/credit_card.md").read_text())

if __name__ == "__main__":
    asyncio.run(provide_agent())