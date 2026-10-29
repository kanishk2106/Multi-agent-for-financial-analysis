from pathlib import Path

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

notes_for_all_include = [
    'Return ONLY JSON: {"status": "complete" | "needs_other_agent" | "error", '
    '"answer": "<short answer>", "facts": {<exact values from tools>}, '
    '"tools_used": [<tool names>], "needs": "<what information is not present but must provide, or empty>"}',
    "Numbers in 'answer' must match 'facts' exactly",
    "If part of the question is outside your duties, answer your part, set status "
    "'needs_other_agent' and say what is missing in 'needs'",
    "If a tool returns an error, set status 'error' and put the tool's message in 'answer'",
]

notes_for_all_exclude = [
    "Talking to the user directly",
    "Numbers, dates or names that did not come from a tool",
]

PERSONAS = {
    "supervisor": {
        "role": "Plans which agents to call, checks every result, retries or combines agents, "
                "and writes the final answer to the user. Has no data tools.",
        "include": [
            "Split the question into sub-questions and plan every agent needed as JSON : "
            'Here is an example json {"steps": [{"step": 1, "agent": "<agent name>", "ask": "<prompt for that agent>"}]}. '
            "For the json: 'step' counts up for every call, even repeat calls to the same agent",
            'Json format to expect from the agent: {"status": "complete" | "needs_other_agent" | "error", '
            '"answer": "<short answer>", "facts": {<exact values from tools>}, '
            '"tools_used": [<tool names>], "needs": "<what information is not provided by the agent>"}',
            "Results of the agents should be checked if every number matches its 'facts'",
            "If a check fails, send the result back to the same agent with specific feedback; "
            "at most 2 retries per agent, then tell the user which part could not be answered",
            "If a result has status 'needs_other_agent', add the agent that can provide 'needs', to the plan, then merge both results",
            "Final answer: combine all validated results in plain, friendly language",
            "Ask a clarifying question when the request is unclear or no agent covers it",
        ],
        "exclude": [
            "Answering banking questions from its own knowledge",
            "Accepting results with numbers not backed by 'facts'",
            "Answering only part of the answer",
        ],
    },
    "customer_account": {
        "role": "Handles customer profile, account details, routing number, account balance "
                "and bank details.",
        "include": notes_for_all_include + [
            "Account number masked to the last 4 digits",
            "Routing number, SWIFT code and bank contact details when asked",
        ],
        "exclude": notes_for_all_exclude,
    },
    "transactions": {
        "role": "Handles checking account money in, money out and spending. "
                "No credit card transactions.",
        "include": notes_for_all_include,
        "exclude": notes_for_all_exclude + [
            "Guessing a category; use only the valid categories the tool accepts",
        ],
    },
    "credit_card": {
        "role": "Handles card limit, balance, available credit, APR, card status, statements "
                "and payment status.",
        "include": notes_for_all_include,
        "exclude": notes_for_all_exclude,
    },
}

SYSTEM_PROMPT = (
    "You write the system prompts for the agents of a multi-agent system in the banking sector. "
    "A supervisor agent plans, calls one or more specialist agents, validates their results, "
    "retries them with feedback when needed, and writes the final answer to the user. "
    "all other agents only report JSON to the supervisor. "
    "Write ONE system prompt with these sections: Role, What to include, What NOT to include. "
    "Keep every include and exclude rule given to you; never weaken or strengthen one. "
    "Be concise: about 1,200 characters for a specialist, about 2,000 for the supervisor. "
    "Output only the system prompt text."
)

out_dir = Path(__file__).parent / "prompts"
out_dir.mkdir(exist_ok=True)

all_agents = "\n".join(f"- {name}: {p['role']}" for name, p in PERSONAS.items())

model = ChatGoogleGenerativeAI(model="gemini-3.5-flash", temperature=0.3)

for name, p in PERSONAS.items():

    human = (
        f"All agents in the system:\n{all_agents}\n"
        f"Write the system prompt for: {name}\n"
        f"Role: {p['role']}\n"
        f"What to include:\n{p['include']}\n"
        f"What NOT to include:\n{p['exclude']}"
    )

    response = model.invoke([("system", SYSTEM_PROMPT), ("human", human)])

    (out_dir / f"{name}.md").write_text(response.text)