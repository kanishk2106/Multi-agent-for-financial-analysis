from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from sqlalchemy import create_engine, text
from pydantic import BaseModel

class creditCardInfo(BaseModel):
    card_number: str
    card_type: str
    credit_limit: float
    current_balance: float
    available_credit: float
    apr: float
    status: str

class creditStatement(BaseModel):
    statement_id: int
    statement_date: str
    due_date: str
    statement_balance: float
    minimum_payment: float
    amount_paid: float
    payment_status: str


mcp = FastMCP(name="credit_info", instructions="Provides tools to retrieve information about the credit card and credit card statements for the user its retrieval includes card number, card type, credit limit, available credit, apr, card statement, amount paid using the card, statement date, statement balance, statement id, and payment status")
engine=create_engine("sqlite:///bank.db")
@mcp.tool
def credit_card_info(customer_id: int) -> dict:
    """Retrieves details about the card like card number, card type, credit limit, available credit, apr"""
    with engine.connect() as conn:
        result=conn.execute(text("select * from credit_cards where customer_id = :customer_id"), {"customer_id": customer_id})
        data=result.mappings().first()
        if data is None:
            raise ToolError(f"No credit card found for customer {customer_id}")
        return creditCardInfo(**data).model_dump()
        

@mcp.tool
def credit_account_summary(customer_id: int) -> list[dict]:
    """ Retrieves information about the credit card account transactions like statement date, statement balance, statement id, amount paid"""
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT s.statement_id, s.statement_date, s.due_date, s.statement_balance,
                   s.minimum_payment, s.amount_paid, s.payment_status
            FROM card_statements s
            JOIN credit_cards c ON s.card_id = c.card_id
            WHERE c.customer_id = :customer_id
            ORDER BY s.statement_date DESC"""), {"customer_id": customer_id})
        data=result.mappings().all()
        if not data:
            raise ToolError(f"No statements found for customer {customer_id}")
        return [creditStatement(**r).model_dump() for r in data]


if __name__ == "__main__":
    mcp.run(transport="http", host="127.0.0.1", port=8000)
    