# Multi-agent for financial analysis

A proof of concept of a multi-agent banking assistant. A supervisor agent reads a customer's question, decides which specialist agents are needed, calls them, checks their answers and writes one final reply. Each specialist gets its data from its own MCP server, which reads a sample bank database.

Built with LangChain, LangGraph, MCP (FastMCP) and Google Gemini.


## Use case

A bank customer asks questions such as:

- What is the account balance for customer 2?
- What is the account balance and credit card limit for customer 2?
- And what is the APR on their card? (a follow-up that relies on the previous question)

One question can need data from more than one part of the bank. The supervisor splits it into smaller questions, sends each to the right agent and combines the answers.




Supervisor
- Plans which agents to call, checks their results, re-plans when needed and writes the final answer.
- Has no data tools of its own.

Customer account agent (customer_agent.py)
- Tools: customer_info, account_info, bank_info
- Customer profile, account number, routing number, account balance, bank details.

Transactions agent (transaction_agent.py)
- Tools: transaction_summary, spending_by_category, spending_by_date
- Checking account money in, money out and spending by category or date. No credit card transactions.

Credit card agent (credit_agent.py)
- Tools: credit_card_info, credit_account_summary
- Card limit, balance, available credit, APR, card status, statements and payment status.

Every specialist replies in the same JSON format:

    {"status": "complete" | "needs_other_agent" | "error",
     "answer": "<short answer>",
     "facts": {<exact values from tools>},
     "tools_used": [<tool names>],
     "needs": "<missing information, or empty>"}


## Agent and skills registry

registry.json describes every agent in one place:

- name: the Python file that builds the agent (for example credit_agent)
- description and skills: used by the supervisor to decide which agent to call
- server: the MCP server URL
- model, temperature, max_output_tokens: model settings for that agent

The supervisor imports agent files by the name in the registry, so adding a new agent only needs a new agent file, a registry entry and a prompt file.


## Agent personas

persona_generation.py uses Gemini to write the system prompt for each agent from a short list of rules (role, what to include, what not to include). The generated prompts are saved in the prompts folder.


## How a question is answered

1. plan: the supervisor model returns a plan as JSON, for example
   {"steps": [{"agent": "credit_card", "question": "What is the credit card limit for customer 2?"}]}
   The plan is checked with a Pydantic model. Only the three real agent names are accepted.
2. agent_execution: every step in the plan is sent to its agent. Agents run at the same time.
3. Each agent calls its MCP tools and returns the JSON result, which is checked with a Pydantic model.
4. If an agent says needs_other_agent, the supervisor makes a new plan for the missing part.
5. final_answer: the checked results are combined into one plain-language answer.


## Real-world problems handled

Routing
- The supervisor model decides which agents a question needs, using the descriptions and skills from the registry.
- One question can be split across several agents.
- The plan is validated, and unknown agent names are rejected.
- If one agent needs information another agent has, the supervisor re-plans, up to 3 rounds.

Context
- A LangGraph checkpointer (MemorySaver) with a thread_id keeps the conversation for the session.
- The last 5 questions and answers are given to the planner, so follow-up questions such as "and their APR?" are resolved to the right customer.
- Each specialist only receives one self-contained question, not the whole conversation.
- Results that belong to one question are cleared before the next question, so old results are not mixed into new answers.

Token cost
- Tokens used by every model call are counted and shown for each question.
- Conversation history is limited to the last 5 exchanges, so prompts do not keep growing.
- History stores only short question and answer pairs, not the agents' full results.
- Only the agents in the plan are called.

Reliability
- If an agent's reply is not valid JSON, it is asked again with the error as feedback, up to 2 retries.
- If the supervisor's plan is not valid JSON, the user gets a safe default reply instead of a crash.
- If a tool cannot find data, the agent reports an error and the final answer says which part could not be answered.

Performance
- Agents in the same plan run in parallel.
- Each agent is built once, when it is first needed, and reused for later questions.




## Run locally

Requirements: Python 3.12 and a Gemini API key.

1. Install the packages:
   
       pip install -r requirements.txt

3. Create a .env file with your key:

       GEMINI_API_KEY=your-key-here

4. Build the sample database:

       python seed_db.py

5. Start the three MCP servers, each in its own terminal:

       python mcp_server/credit_card_info_mcp.py
       python mcp_server/customer_info_mcp.py
       python mcp_server/transaction_info.py

6. Start the supervisor:

       python supervisor_agent.py

Type a question at the "You:" prompt. Type quit to exit.



