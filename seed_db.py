"""
seed_db.py - Build a fake, internally consistent bank database (bank.db)
for the multi-agent banking chatbot demo.

Run:  pip install faker
      python seed_db.py
"""
import random
import sqlite3
from datetime import date, timedelta

from faker import Faker

DB_PATH = "bank.db"
TODAY = date(2026, 10, 26)  # fixed "today" so every run gives identical data
NUM_CUSTOMERS = 5
RANDOM_TXNS_PER_ACCOUNT = 9  # + 3 salary + 3 rent = 15 per account

Faker.seed(42)
random.seed(42)
fake = Faker("en_US")

# Realistic merchants and amount ranges (USD) per spending category
MERCHANTS = {
    "groceries": ["Whole Foods Market", "Kroger", "Trader Joe's", "Safeway", "Costco"],
    "dining": ["Chipotle", "Starbucks", "Olive Garden", "Panera Bread", "Shake Shack"],
    "shopping": ["Amazon.com", "Target", "Walmart", "Best Buy", "Macy's"],
    "utilities": ["ConEdison", "Verizon Wireless", "Comcast Xfinity", "PG&E", "AT&T"],
    "travel": ["Delta Air Lines", "Uber", "Marriott Hotels", "Shell", "Amtrak"],
}
AMOUNT_RANGES = {
    "groceries": (25, 220),
    "dining": (8, 95),
    "shopping": (15, 350),
    "utilities": (45, 210),
    "travel": (12, 650),
}
DESCRIPTIONS = {
    "groceries": "Debit card purchase",
    "dining": "Debit card purchase",
    "shopping": "Online purchase",
    "utilities": "Bill payment - autopay",
    "travel": "Debit card purchase",
}
SUBSCRIPTIONS = {"Netflix": 15.49, "Spotify": 11.99, "Apple iCloud": 2.99, "Hulu": 17.99}
SPEND_CATEGORIES = list(MERCHANTS) + ["subscription", "transfer"]

SCHEMA = """
CREATE TABLE bank_info (
    bank_name TEXT, routing_number TEXT, swift_code TEXT,
    customer_service_phone TEXT, headquarters_address TEXT, website TEXT
);
CREATE TABLE customers (
    customer_id INTEGER PRIMARY KEY, full_name TEXT, email TEXT, phone TEXT,
    address TEXT, date_of_birth TEXT, customer_since TEXT
);
CREATE TABLE accounts (
    account_id INTEGER PRIMARY KEY,
    customer_id INTEGER REFERENCES customers(customer_id),
    account_number TEXT UNIQUE, routing_number TEXT,
    account_type TEXT CHECK (account_type IN ('checking', 'savings')),
    branch_name TEXT, branch_address TEXT,
    opening_balance REAL, current_balance REAL, opened_date TEXT
);
CREATE TABLE transactions (
    txn_id INTEGER PRIMARY KEY,
    account_id INTEGER REFERENCES accounts(account_id),
    txn_date TEXT, merchant TEXT, category TEXT,
    amount REAL CHECK (amount > 0),
    txn_type TEXT CHECK (txn_type IN ('debit', 'credit')),
    description TEXT
);
CREATE TABLE credit_cards (
    card_id INTEGER PRIMARY KEY,
    customer_id INTEGER REFERENCES customers(customer_id),
    card_number TEXT, card_type TEXT, credit_limit REAL,
    current_balance REAL, available_credit REAL, apr REAL,
    status TEXT CHECK (status IN ('active', 'blocked'))
);
CREATE TABLE card_statements (
    statement_id INTEGER PRIMARY KEY,
    card_id INTEGER REFERENCES credit_cards(card_id),
    statement_date TEXT, due_date TEXT, statement_balance REAL,
    minimum_payment REAL, amount_paid REAL,
    payment_status TEXT CHECK (payment_status IN ('paid', 'partial', 'unpaid', 'overdue'))
);
CREATE TABLE audit_log (
    log_id INTEGER PRIMARY KEY, timestamp TEXT, session_id TEXT,
    customer_id INTEGER, step INTEGER, agent_name TEXT, tool_name TEXT,
    outcome TEXT, tokens INTEGER
);
"""
TABLES = ["audit_log", "card_statements", "credit_cards", "transactions",
          "accounts", "customers", "bank_info"]


# ---------- helpers (money is kept in integer cents to avoid float drift) ----------
def rand_cents(lo, hi):
    return random.randint(int(lo * 100), int(hi * 100))


def usd(cents):
    return round(cents / 100, 2)


def months_back(d, k):
    y, m = d.year, d.month - k
    while m <= 0:
        m += 12
        y -= 1
    return date(y, m, d.day)


def last_n_monthly_dates(day, n):
    """The n most recent dates (oldest first) falling on `day` of the month, up to TODAY."""
    start = date(TODAY.year, TODAY.month, day)
    if start > TODAY:
        start = months_back(start, 1)
    return [months_back(start, k) for k in range(n)][::-1]


def random_recent_date():
    return TODAY - timedelta(days=random.randint(0, 89))  # within the last ~3 months


def one_line_address():
    return f"{fake.street_address()}, {fake.city()}, {fake.state_abbr()} {fake.zipcode()}"


def alnum(s):
    return "".join(ch for ch in s if ch.isalnum()).lower()


# ---------- generators ----------
def make_transactions(cid):
    """Return (list of txns, net change in cents) for one checking account."""
    txns = []

    def add(d, merchant, category, cents, txn_type, desc):
        txns.append((d, merchant, category, cents, txn_type, desc))

    # Monthly salary (same amount each month)
    employer = fake.company()
    salary = rand_cents(4200, 7500)
    for d in last_n_monthly_dates(1, 3):
        add(d, f"{employer} Payroll", "salary", salary, "credit", "Direct deposit - payroll")

    # Monthly rent
    landlord = f"{fake.last_name()} Property Management"
    rent = rand_cents(1300, 2400)
    for d in last_n_monthly_dates(3, 3):
        add(d, landlord, "rent", rent, "debit", "Monthly rent - ACH payment")

    # Everyday spending
    for _ in range(RANDOM_TXNS_PER_ACCOUNT):
        cat = random.choice(SPEND_CATEGORIES)
        d = random_recent_date()
        if cat == "subscription":
            merchant, price = random.choice(list(SUBSCRIPTIONS.items()))
            add(d, merchant, cat, int(round(price * 100)), "debit", f"Recurring subscription - {merchant}")
        elif cat == "transfer":
            add(d, "Zelle", cat, rand_cents(20, 300), "debit", f"Zelle payment to {fake.first_name()}")
        else:
            merchant = random.choice(MERCHANTS[cat])
            add(d, merchant, cat, rand_cents(*AMOUNT_RANGES[cat]), "debit",
                f"{DESCRIPTIONS[cat]} - {merchant}")

    # Messy case 1: duplicate charge (same merchant, amount, date)
    if cid == 1:
        d = random_recent_date()
        for _ in range(2):
            add(d, "Amazon.com", "shopping", 8799, "debit", "Online purchase - Amazon.com")

    # Messy case 2: large refund credit
    if cid == 2:
        add(random_recent_date(), "Best Buy", "refund", 184999, "credit",
            "Refund - returned laptop, order #BBY-" + fake.numerify("########"))

    txns.sort(key=lambda t: t[0])  # chronological, so txn_ids follow date order
    net = sum(c if t == "credit" else -c for _, _, _, c, t, _ in txns)
    return txns, net


def make_statements(cid, card_balance, limit):
    """Three monthly statements (oldest first) for one card."""
    rows = []
    dates = last_n_monthly_dates(2, 3)
    for i, sd in enumerate(dates):
        latest = i == len(dates) - 1
        if latest:
            bal = int(card_balance * random.uniform(0.85, 1.0))  # close to today's balance
        elif cid == 3:
            bal = int(limit * random.uniform(0.75, 0.9))  # near-limit card has been high for a while
        else:
            bal = int(limit * random.uniform(0.15, 0.5))
        min_pay = max(3500, round(bal * 0.02))  # greater of $35 or 2%
        due = sd + timedelta(days=21)

        if cid == 4 and latest:  # Messy case 4: latest statement overdue
            paid, status = 0, "overdue"
        elif due >= TODAY:  # not due yet
            paid, status = 0, "unpaid"
        elif random.random() < 0.6:
            paid, status = bal, "paid"
        else:
            paid, status = random.randint(min_pay, bal - 1), "partial"

        rows.append((sd.isoformat(), due.isoformat(), usd(bal), usd(min_pay), usd(paid), status))
    return rows


# ---------- main ----------
def seed(conn):
    cur = conn.cursor()
    for t in TABLES:
        cur.execute(f"DROP TABLE IF EXISTS {t}")
    cur.executescript(SCHEMA)

    routing = fake.aba()  # valid-looking 9-digit ABA routing number
    cur.execute("INSERT INTO bank_info VALUES (?, ?, ?, ?, ?, ?)", (
        "Demo National Bank", routing, "DNBKUS33", "1-800-555-0199",
        one_line_address(), "https://www.demonationalbank.com"))

    used_account_numbers = set()
    for cid in range(1, NUM_CUSTOMERS + 1):
        # Customer
        first, last = fake.first_name(), fake.last_name()
        dob = TODAY - timedelta(days=random.randint(25 * 365, 70 * 365))
        since = TODAY - timedelta(days=random.randint(2 * 365, 15 * 365))
        cur.execute("INSERT INTO customers VALUES (?, ?, ?, ?, ?, ?, ?)", (
            cid, f"{first} {last}",
            f"{alnum(first)}.{alnum(last)}@{fake.free_email_domain()}",
            f"({random.randint(201, 989)}) {random.randint(200, 999)}-{random.randint(0, 9999):04d}",
            one_line_address(), dob.isoformat(), since.isoformat()))

        # Checking account: balance = opening + credits - debits
        acct_no = str(random.randint(10**9, 10**10 - 1))
        while acct_no in used_account_numbers:
            acct_no = str(random.randint(10**9, 10**10 - 1))
        used_account_numbers.add(acct_no)

        opened = since + timedelta(days=random.randint(0, (TODAY - timedelta(days=120) - since).days))
        opening = rand_cents(2500, 8000)
        txns, net = make_transactions(cid)
        city = fake.city()
        cur.execute(
            "INSERT INTO accounts (customer_id, account_number, routing_number, account_type, "
            "branch_name, branch_address, opening_balance, current_balance, opened_date) "
            "VALUES (?, ?, ?, 'checking', ?, ?, ?, ?, ?)",
            (cid, acct_no, routing, f"{city} Branch",
             f"{fake.street_address()}, {city}, {fake.state_abbr()} {fake.zipcode()}",
             usd(opening), usd(opening + net), opened.isoformat()))
        account_id = cur.lastrowid
        cur.executemany(
            "INSERT INTO transactions (account_id, txn_date, merchant, category, amount, txn_type, description) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            [(account_id, d.isoformat(), m, c, usd(a), t, desc) for d, m, c, a, t, desc in txns])

        # Credit card: available = limit - balance
        card_type = random.choice(["Visa", "Mastercard"])
        card_no = fake.credit_card_number("visa16" if card_type == "Visa" else "mastercard")
        limit = random.choice([3000, 5000, 7500, 10000, 12000, 15000]) * 100
        if cid == 3:  # Messy case 3: over 90% of limit used
            card_bal = int(limit * random.uniform(0.92, 0.97))
        else:
            card_bal = int(limit * random.uniform(0.10, 0.45))
        status = "blocked" if cid == 5 else "active"  # Messy case 5
        cur.execute(
            "INSERT INTO credit_cards (customer_id, card_number, card_type, credit_limit, "
            "current_balance, available_credit, apr, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (cid, card_no, card_type, usd(limit), usd(card_bal), usd(limit - card_bal),
             random.choice([18.99, 21.49, 22.99, 24.99, 26.99]), status))
        card_id = cur.lastrowid

        cur.executemany(
            "INSERT INTO card_statements (card_id, statement_date, due_date, statement_balance, "
            "minimum_payment, amount_paid, payment_status) VALUES (?, ?, ?, ?, ?, ?, ?)",
            [(card_id, *row) for row in make_statements(cid, card_bal, limit)])

    conn.commit()


def show(cur, title, sql, params=()):
    print(f"\n== {title} ==")
    cur.execute(sql, params)
    print("  " + " | ".join(col[0] for col in cur.description))
    for row in cur.fetchall():
        print("  " + " | ".join(str(v) for v in row))


def report(conn):
    cur = conn.cursor()
    print("Row counts:")
    for t in reversed(TABLES):
        print(f"  {t:<16} {cur.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]}")

    show(cur, "Sample transactions", "SELECT * FROM transactions LIMIT 3")
    show(cur, "Sample card_statements", "SELECT * FROM card_statements LIMIT 3")

    show(cur, "Balance check (opening + credits - debits = current)", """
        SELECT a.account_id, a.opening_balance, a.current_balance,
               ROUND(a.opening_balance + SUM(CASE WHEN t.txn_type='credit' THEN t.amount ELSE -t.amount END), 2)
                   AS recomputed
        FROM accounts a JOIN transactions t USING (account_id) GROUP BY a.account_id""")

    show(cur, "Customer 1: duplicate charge", """
        SELECT t.txn_date, t.merchant, t.amount, COUNT(*) AS times
        FROM transactions t JOIN accounts a USING (account_id)
        WHERE a.customer_id = 1
        GROUP BY t.txn_date, t.merchant, t.amount HAVING COUNT(*) > 1""")
    show(cur, "Customer 2: large refund", """
        SELECT t.txn_date, t.merchant, t.amount, t.description
        FROM transactions t JOIN accounts a USING (account_id)
        WHERE a.customer_id = 2 AND t.category = 'refund'""")
    show(cur, "Customer 3: card near limit", """
        SELECT credit_limit, current_balance, available_credit,
               ROUND(100.0 * current_balance / credit_limit, 1) AS pct_used
        FROM credit_cards WHERE customer_id = 3""")
    show(cur, "Customer 4: latest statement", """
        SELECT s.statement_date, s.due_date, s.statement_balance, s.minimum_payment,
               s.amount_paid, s.payment_status
        FROM card_statements s JOIN credit_cards c USING (card_id)
        WHERE c.customer_id = 4 ORDER BY s.statement_date DESC LIMIT 1""")
    show(cur, "Customer 5: card status",
         "SELECT card_id, card_type, card_number, status FROM credit_cards WHERE customer_id = 5")


if __name__ == "__main__":
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        seed(conn)
        report(conn)
    print(f"\nDone. Database written to {DB_PATH}")
