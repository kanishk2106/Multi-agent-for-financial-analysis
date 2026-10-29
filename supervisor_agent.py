import asyncio
import importlib
import json
import operator
import uuid
from pathlib import Path
from typing import Annotated, Literal

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, ValidationError

load_dotenv()

with open("registry.json") as file:
    config = json.load(file)["agents"]

supervisor_config = config["supervisor"]
supervisor_persona = Path("prompts/supervisor.md").read_text()
agent_name = [name for name in config if name != "supervisor"]
agent_description={name: f"{config[name]['description']} Skills: {', '.join(config[name]['skills'])}" for name in agent_name}
MAX_RETRIES = 2
agents = {}  # agent name -> built agent, built once and reused

supervisor = ChatGoogleGenerativeAI(
    model=config["supervisor"]["model"],
    temperature=config["supervisor"]["temperature"],
    max_output_tokens=config["supervisor"]["max_output_tokens"],
)


class AgentResult(BaseModel):  
    status: Literal["complete", "needs_other_agent", "error"]
    answer: str
    facts: dict
    tools_used: list[str] = []
    needs: str = ""
    agent: str = ""
    retries: int = 0

class Plan(BaseModel):
    agent: Literal["customer_account", "transactions", "credit_card"]
    question: str


class Steps(BaseModel):
    steps: list[Plan]


class State(BaseModel):
    question: str = ""
    plan: list[Plan] = []
    final: str = ""
    status: str = ""
    agent_results: list[AgentResult] = []
    rounds: int = 0
    tokens: int = 0
    history: Annotated[list[dict], operator.add] = []


def count_tokens(messages):
    return sum(m.usage_metadata["total_tokens"] for m in messages if getattr(m, "usage_metadata", None))


def plan(state: State):
    if state.agent_results:
        human = (f"Customer question: {state.question}\n\n"
                 f"Results so far:\n{state.agent_results}\n\n"
                 "Plan only the steps needed to provide what the 'needs' fields ask for. "
                 "Include the facts already found in each step's question. "
                 "Do not repeat steps that are already complete.")
    else:
        human = f"Customer question: {state.question}\nMake a plan."
    if state.history:
        human = (f"Earlier conversation:\n{state.history[-5:]}\n\n"
                 "Use it to fill in what the new question leaves out, like the customer id.\n\n" + human)
    answer = supervisor.invoke([
        ("system", f"{supervisor_persona}\n\nAvailable agents:\n{agent_description}"),
        ("human", human),
    ])
    text = answer.text
    tokens = state.tokens + count_tokens([answer])
    try:
        data = Steps.model_validate_json(text[text.find("{"): text.rfind("}") + 1])
    except ValidationError:
        return {"plan": [], "rounds": state.rounds + 1, "tokens": tokens}
    return {"plan": data.steps, "rounds": state.rounds + 1, "tokens": tokens}


async def get_agent(name):
    if name not in agents:
        module = importlib.import_module(config[name]["name"])
        agents[name] = await module.provide_agent()
    return agents[name]


async def run_step(step: Plan):
    agent = await get_agent(step.agent)
    question = step.question
    tokens = 0
    for attempt in range(MAX_RETRIES + 1):
        response = await agent.ainvoke({"messages": [{"role": "user", "content": question}]})
        tokens += count_tokens(response["messages"])
        text = response["messages"][-1].text
        try:
            result = AgentResult.model_validate_json(text[text.find("{"): text.rfind("}") + 1])
            break
        except ValidationError as e:
            result = AgentResult(status="error", answer=f"Invalid reply: {e}", facts={})
            question = (f"{step.question}\n\nYour previous reply was rejected: {e}\n"
                        "Reply again with ONLY the JSON format from your instructions.")
    result.agent = step.agent
    result.retries = attempt
    return result, tokens


async def agent_execution(state: State):
    finished = await asyncio.gather(*(run_step(step) for step in state.plan))
    results = [result for result, _ in finished]
    tokens = state.tokens + sum(t for _, t in finished)
    return {"agent_results": state.agent_results + results, "tokens": tokens}


def final_answer(state: State):
    if not state.agent_results:
        final = "I can help with your account, transactions and credit card. What would you like to know?"
        return {"final": final, "status": "Incompleted",
                "history": [{"question": state.question, "answer": final}]}

    results = "\n".join(r.model_dump_json() for r in state.agent_results)
    out = supervisor.invoke([
        ("system", "You write the final answer to a bank customer using only the results given."),
        ("human", f"Customer question: {state.question}\n\nResults:\n{results}\n\n"
                  "Write the final answer to the customer in plain, friendly language. "
                  "Say which part could not be answered, if any. "
                  "Do not show JSON, tool names or agent names."),
    ])
    return {"final": out.text, "status": "Completed", "tokens": state.tokens + count_tokens([out]),
            "history": [{"question": state.question, "answer": out.text}]}


def after_plan(state: State) -> str:
    return "agent_execution" if state.plan else "final_answer"


def after_execution(state: State) -> str:
    if state.rounds >= 3:
        return "final_answer"
    latest = state.agent_results[-len(state.plan):]
    if any(r.status == "needs_other_agent" for r in latest):
        return "plan"
    return "final_answer"


agent_builder = StateGraph(State)

agent_builder.add_node("plan", plan)
agent_builder.add_node("agent_execution", agent_execution)
agent_builder.add_node("final_answer", final_answer)

agent_builder.add_edge(START, "plan")
agent_builder.add_conditional_edges("plan", after_plan, ["agent_execution", "final_answer"])
agent_builder.add_conditional_edges("agent_execution", after_execution, ["plan", "final_answer"])
agent_builder.add_edge("final_answer", END)

app = agent_builder.compile(checkpointer=MemorySaver())


async def main():
    session = {"configurable": {"thread_id": str(uuid.uuid4())}}
    while True:
        question = input("\nYou: ").strip()
        if question.lower() in {"", "quit", "exit"}:
            break
        out = await app.ainvoke({"question": question, "plan": [], "agent_results": [],
                                 "rounds": 0, "tokens": 0, "final": "", "status": ""}, session)
        print(out["final"])
        for r in out["agent_results"]:
            print(f"\n {r.agent} {r.status} retries: {r.retries}")
        print(f"[rounds: {out['rounds']} | tokens: {out['tokens']}]")


if __name__ == "__main__":
    asyncio.run(main())