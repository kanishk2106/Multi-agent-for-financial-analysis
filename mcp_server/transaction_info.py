from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from sqlalchemy import create_engine, text
from pydantic import BaseModel
from datetime import date


mcp=FastMCP(name="transaction_info", instructions="Retrieves all transaction details for the customer in the account it does not have the transactions for credit card")
engine=create_engine("sqlite:///bank.db")
categories={"groceries", "dining", "shopping", "utilities", "rent", "travel","salary", "transfer", "refund", "subscription"}
@mcp.tool
def transaction_summary(customer_id: int) -> dict:
    """Get a customer's total money in (credits), money out (debits) and net
    change across their checking account transactions."""
    with engine.connect() as conn:
        result=conn.execute(text("SELECT SUM(CASE WHEN t.txn_type = 'credit' THEN t.amount ELSE 0 END) AS total_in,SUM(CASE WHEN t.txn_type = 'debit'  THEN t.amount ELSE 0 END) AS total_out,SUM(CASE WHEN t.txn_type = 'credit' THEN t.amount ELSE -t.amount END) AS net FROM transactions t JOIN accounts a ON a.account_id = t.account_id WHERE a.customer_id = :customer_id"),{"customer_id":customer_id})
        data=result.mappings().first()
        if data["total_in"] is None:
            raise ToolError(f"No transactions found for customer {customer_id}")
        return dict(data)
@mcp.tool
def spending_by_category(customer_id: int, category: str) -> list[dict]:
    """Get a customer's checking account totals grouped by category Debits are
    money spent (e.g. dining, rent); credits are money received (salary, refund).
    Use for questions like 'where did I spend the most' or 'break down my spending'."""
    if category not in categories:
        raise ValueError("Provided category not present")

    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT t.category,
                   t.txn_type,
                   COUNT(*)                AS txn_count,
                   ROUND(SUM(t.amount), 2) AS total_amount
            FROM transactions t
            JOIN accounts a ON a.account_id = t.account_id
            WHERE a.customer_id = :customer_id and category=:category
            GROUP BY t.category, t.txn_type"""),
            {"customer_id": customer_id, "category": category})
        rows = result.mappings().all()
    return [dict(r) for r in rows]



@mcp.tool
def spending_by_date(customer_id: int, start_date: date, end_date: date) -> list[dict]:
    """Get how much a customer spent (debits only) between two dates, inclusive,
    with a total for each day. Dates use YYYY-MM-DD format. Use for questions like what did I spend between Sep 1 and Sep 15. If the question is only one date include two same dates as the arguements"""
    if start_date > end_date:
        raise ValueError("start_date must be on or before end_date")

    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT t.txn_date,
                   COUNT(*) AS txn_count,
                   ROUND(SUM(t.amount), 2) AS total_spent
            FROM transactions t
            JOIN accounts a ON a.account_id = t.account_id
            WHERE a.customer_id = :customer_id
              AND t.txn_type = 'debit'
              AND t.txn_date BETWEEN :start_date AND :end_date
            GROUP BY t.txn_date
            ORDER BY t.txn_date"""),
            {"customer_id": customer_id,
             "start_date": start_date.isoformat(),
             "end_date": end_date.isoformat()})
        data = result.mappings().all()

    return [dict(r) for r in data]


if __name__ == "__main__":
    mcp.run(transport="http", host="127.0.0.1", port=8002)


