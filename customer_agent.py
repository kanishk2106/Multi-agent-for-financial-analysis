import json
import asyncio
from langchain.mcp import MCPAdapter
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_agent
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
with open("registry.json") as file:
    data= json.load(file)["agents"]["customer_account"]
async def provide_agent():
    async with MCPAdapter(data["server"]) as adapter:
        tools = await adapter.list_tools()
        model=ChatGoogleGenerativeAI(model=data["model"], temperature=data["temperature"], max_output_tokens=data["max_output_tokens"])
        return create_agent(model=model, tools=tools, system_prompt=Path("prompts/customer_account.md").read_text())
        
if __name__ == "__main__":
    asyncio.run(provide_agent())
