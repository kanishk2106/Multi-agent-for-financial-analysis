from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from sqlalchemy import create_engine
from sqlalchemy import text
from pydantic import BaseModel


class CustomerInfo(BaseModel):
    customer_id: int
    full_name: str
    email: str
    phone: str
    address: str
    date_of_birth: str

class BankInfo(BaseModel):
    bank_name: str
    routing_number: str
    swift_code: str
    customer_service_phone: str
    headquarters_address: str

class AccountInfo(BaseModel):
    customer_id: int
    account_number: str
    routing_number: str
    account_type: str
    current_balance: float

mcp = FastMCP(name="customer_bank_info", instructions="Provides tools for retrieving the information about the customer, account and bank details. However the transaction details and credit card details are not provded")
engine=create_engine("sqlite:///bank.db")
@mcp.tool
def customer_info(customer_id: int) -> dict:
    """
    Retrives the information about the customer like name, id, email, phone number, address, and date of birth"""
    with engine.connect() as conn:
        result = conn.execute(
            text("Select * from customers where customer_id = :customer_id"), { "customer_id": customer_id})
        data=result.mappings().first()
        if data is None:
            raise ToolError(f"Customer {customer_id} not found")
        return CustomerInfo(**data).model_dump()

@mcp.tool
def bank_info() -> dict:
    """ Retrieves the bank information that the custmer is related with"""
    with engine.connect() as conn:
        result = conn.execute(text("Select * from bank_info"))
        data = result.mappings().first()
        return BankInfo(**data).model_dump()
@mcp.tool
def account_info(customer_id: int) -> dict:
    """ Retrives the information about the account details for the customer like account number, routing number, account type and current balance"""
    with engine.connect() as conn:
        result = conn.execute(text("Select * from accounts where customer_id=:customer_id"),{"customer_id": customer_id})
        data=result.mappings().first()
        if data is None:
            raise ToolError(f"No account found for customer {customer_id}")
        return AccountInfo(**data).model_dump()
         


if __name__ == "__main__":
    mcp.run(transport="http", host="127.0.0.1", port=8001)

    

