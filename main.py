import os, time
import pandas as pd
from mistralai import Mistral
from dotenv import load_dotenv
from sqlalchemy import (
    MetaData, Table, Column,
    Integer, Text, Float, Date, create_engine, ForeignKey, Boolean, inspect, text
)
from system_prompts import parse_prompt, summarise_prompt

load_dotenv()

# Initialize Mistral client
if not os.getenv("MISTRAL_API_KEY"):
    raise ValueError("MISTRAL_API_KEY not found in environment variables.")

mistral_api_key = os.getenv("MISTRAL_API_KEY")
model = "mistral-large-latest"

client = Mistral(api_key=mistral_api_key)

# Database Configuration parameters
if not all([os.getenv("DB_USER"), os.getenv("DB_PASSWORD"), os.getenv("DB_PORT"), os.getenv("DB_NAME")]):
    raise ValueError("Database configuration parameters (DB_USER, DB_PASSWORD, DB_PORT, DB_NAME) are required in environment variables.")

db_user = os.getenv("DB_USER")
password = os.getenv("DB_PASSWORD")
port = os.getenv("DB_PORT")
db_name = os.getenv("DB_NAME")

# Database Connection 
DATABASE_URL = (
    f"postgresql+psycopg2://{db_user}:{password}@localhost:{port}/{db_name}"
)
engine = create_engine(DATABASE_URL)
inspector = inspect(engine)

# Function to create tables
def create_tables():
    metadata = MetaData()
    vehicle_cards = Table(
        "vehicle_cards", metadata,
        Column("card_id", Integer, primary_key=True),
        Column("vehicle_type", Text),
        Column("manufacturer", Text),
        Column("model", Text),
        Column("manufacture_year", Float),
        Column("created_at", Date)
    )

    damage_detections = Table(
        "damage_detections", metadata,
        Column("damage_id", Integer, primary_key=True),
        Column("card_id", Integer, ForeignKey("vehicle_cards.card_id")),
        Column("panel_name", Text),
        Column("damage_type", Text),
        Column("severity", Text),
        Column("confidence", Float),
        Column("detected_at", Date)
    )

    repairs = Table(
        "repairs", metadata,
        Column("repair_id", Integer, primary_key=True),
        Column("card_id", Integer, ForeignKey("vehicle_cards.card_id")),
        Column("panel_name", Text),
        Column("repair_action", Text),
        Column("repair_cost", Float),
        Column("approved", Boolean),
        Column("created_at", Date)
    )

    quotes = Table(
        "quotes", metadata,
        Column("quote_id", Integer, primary_key=True),
        Column("card_id", Integer, ForeignKey("vehicle_cards.card_id")),
        Column("total_estimated_cost", Integer),
        Column("currency", Text),
        Column("generated_at", Date)
    )

    metadata.create_all(engine)

# Function to load data from CSV to DB
def load_data_to_db(engine, path, tables):
    date_columns = {
        "vehicle_cards": ["created_at"],
        "damage_detections": ["detected_at"],
        "repairs": ["created_at"],
        "quotes": ["generated_at"]
    }

    for table in tables:
        try:
            df = pd.read_csv(f"{path}/{table}.csv")
            for col in date_columns.get(table, []):
                df[col] = pd.to_datetime(df[col], errors='coerce').dt.date
            df.to_sql(table, engine, if_exists="append", index=False, method="multi", chunksize=1000)
        except Exception as e:
            print(f"Error loading {table}: {e}")

# Function to ensure tables exist
def ensure_tables_exist():
    tables_to_check = ["vehicle_cards", "damage_detections", "repairs", "quotes"]

    for table_name in tables_to_check:
        if not inspector.has_table(table_name, schema="public"):
            print(f"Table {table_name} missing. Creating tables...")
            create_tables()
            tables = ["vehicle_cards", "damage_detections", "repairs", "quotes"]
            path = "data/"
            load_data_to_db(engine, path, tables)
            print("Data loaded into the tables successfully.")
            break
    else:
        print("All tables already exist...")

# Function to parse user query into PostgreSQL Query
def parse_user_query(question: str, retries=3, delay=2) -> str:
    for attempt in range(retries):
        try:
            response = client.chat.complete(
                model=model,
                messages=[
                    {"role": "system", "content": parse_prompt},
                    {"role": "user", "content": question}
                ],
                temperature=0
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"LLM call failed: {e}. Retrying {attempt+1}/{retries}...")
            time.sleep(delay)
    return "INCORRECT"

# Function to run SQL query and fetch results
def run_sql(sql: str):
    try:
        with engine.connect() as conn:
            result = conn.execution_options(stream_results=True).execute(text(sql))
            return [dict(row._mapping) for row in result]
    except Exception as e:
        print(f"SQL execution error: {e}")
        return []

# Function to summarize SQL query results into natural language answer
def summarize_results(question: str, results: list) -> str:
    try:
        user_input = f"Question: {question}\nQuery results: {results}\nProvide a concise, user-friendly natural language answer."
        response = client.chat.complete(
            model=model,
            messages=[
                {"role": "system", "content": summarise_prompt},
                {"role": "user", "content": user_input}
            ],
            temperature=0
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Error generating summary: {e}"

# Function to prompt user for clarification
def prompt_clarification(reason: str):
    messages = {
        "ambiguous": "AI: Your question seems ambiguous. Could you clarify?",
        "incorrect": "AI: Your question seems incorrect. Please rephrase."
    }
    print(messages.get(reason, "AI: Please clarify your question."), end="\n")

ensure_tables_exist()

# Main interaction loop
while True:
    try:
        question = input('Ask a question (or type "q" to quit): ')
        if question.lower() == "q":
            break
        
        # Parse user query to SQL
        sql_query = parse_user_query(question)
        if sql_query == "INCORRECT":
            prompt_clarification("incorrect")
            continue
        print("SQL Query Generated: ", sql_query, end="\n\n")
        # Execute SQL query
        results = run_sql(sql_query)
        if not results:
            print("AI: No results found.")
            continue
        
        # Summarize results
        answer = summarize_results(question, results)
        if answer == "AMBIGUOUS":
            prompt_clarification("ambiguous")
            continue
        print("AI: ", answer, end="\n\n")

    except KeyboardInterrupt:
        print("\nExiting...")
        break

    except Exception as e:
        print(f"An error occurred: {e}")    
