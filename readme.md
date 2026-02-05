# The Project

A conversational AI-powered system that intelligently answers questions about vehicle damage assessments and repair quotes using natural language. The project combines AI-powered query understanding with robust error handling to ensure accurate and secure database interactions.

## What It Does

The project allows users to ask questions in plain English about vehicle damage, repairs, and quotes. Behind the scenes, an AI system (powered by Mistral) converts these questions into database queries, validates them for safety and correctness, and returns clear, human-readable answers.

**Example questions you can ask:**
- "How many high-severity damages were detected on Toyota vehicles?"
- "What is the total estimated cost for repairs on vehicle card 5?"
- "Which panels have approved repairs?"
- "Show me all vehicles manufactured in 2020"

## Key Features

- **Natural Language Processing**: Ask questions in regular English
- **Intelligent Query Conversion**: Automatically converts your questions to SQL queries
- **Smart Results**: Provides clear, concise answers based on database results
- **Error Handling**: Validates questions and alerts you if something doesn't make sense

## How to Set Up

### Prerequisites
- Python 3.8 or higher
- PostgreSQL database (for storing vehicle and repair data)
- Mistral API key for AI-powered conversions

### Installation Steps

1. **Clone or download the project** to your computer

2. **Install required packages:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables:**
   Create a `.env` file in the project directory with:
   ```
   MISTRAL_API_KEY=your_api_key_here
   DB_USER=your_database_user
   DB_PASSWORD=your_database_password
   DB_PORT=5432
   DB_NAME=your_database_name
   ```

4. **Prepare your data:**
   - Place your CSV files in the `data/` folder:
     - `vehicle_cards.csv` - Vehicle information
     - `damage_detections.csv` - Detected damages
     - `repairs.csv` - Repair details
     - `quotes.csv` - Cost estimates

5. **Run the project:**
   ```bash
   python main.py
   ```

## How to Use

Once running, the project will show a prompt asking for your question:
```
Ask a question (or type "q" to quit):
```

Type your question and press Enter. The system will:
1. Convert your question to a SQL query
2. Run it against the database
3. Provide a natural language answer

**To exit:** Type `q` and press Enter

## Data Structure

The project works with four connected database tables:

| Table | Purpose |
|-------|---------|
| `vehicle_cards` | Stores vehicle information (make, model, year, etc.) |
| `damage_detections` | Records detected damage to vehicle panels with severity levels |
| `repairs` | Tracks repair actions, costs, and approval status |
| `quotes` | Stores total estimated repair costs |

## Project Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    User Interface                           │
│              (Text-based Question Prompt)                   │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│         Query Validation & Parsing Layer                    │
│    (Mistral AI + Schema Validation)                         │
│                                                              │
│  ✓ Validates against database schema                        │
│  ✓ Rejects modification attempts (INSERT, UPDATE, etc.)    │
│  ✓ Detects invalid tables/columns                          │
│  ✓ Auto-retries on API failures (3 attempts)              │
│  ✓ Returns "INCORRECT" for invalid queries                 │
└──────────────────────────┬──────────────────────────────────┘
                           │
                    ┌──────┴──────┐
                    │             │
            INCORRECT?      Valid SQL?
                    │             │
                    ▼             ▼
        ┌───────────────────┐   ┌─────────────────────────────┐
        │ Prompt for        │   │ SQL Execution Layer         │
        │ Clarification     │   │ (SQLAlchemy + PostgreSQL)   │
        │                   │   │                             │
        │ "Your question    │   │ ✓ Stream large results      │
        │  seems incorrect. │   │ ✓ Error handling & logging  │
        │  Please rephrase" │   │ ✓ Connection management     │
        └───────────────────┘   └────────────┬────────────────┘
                                             │
                                             ▼
                                ┌─────────────────────────────┐
                                │ Result Summarization Layer  │
                                │ (Mistral AI)                │
                                │                             │
                                │ ✓ Detects ambiguous results │
                                │ ✓ Handles empty results     │
                                │ ✓ Converts to natural lang. │
                                │ ✓ Deterministic responses   │
                                └────────────┬────────────────┘
                                             │
                                    ┌────────┴────────┐
                                    │                 │
                            AMBIGUOUS?    Valid Answer?
                                    │                 │
                                    ▼                 ▼
                    ┌───────────────────────┐  ┌───────────────┐
                    │ Prompt for            │  │ User-Friendly │
                    │ Clarification         │  │ Natural Lang. │
                    │                       │  │ Response      │
                    │ "Your question seems  │  └───────────────┘
                    │  ambiguous. Could     │
                    │  you clarify?"        │
                    └───────────────────────┘
```

## Intelligence: Handling Ambiguous & Incorrect Queries

### 🛡️ Query Validation - Catching Incorrect Queries

The project intelligently validates every user question **before** it ever touches the database:

**Rejected Query Examples:**
```
❌ "Delete all repair records" → INCORRECT (modification attempt)
❌ "Show me data from the users table" → INCORRECT (table doesn't exist)
❌ "What's the price column?" → INCORRECT (column doesn't exist)
❌ "Insert a new vehicle" → INCORRECT (read-only constraint)
```

**How it works:**
1. Question is sent to Mistral AI with strict instructions
2. AI checks against the actual database schema:
   - `vehicle_cards` (card_id, vehicle_type, manufacturer, model, manufacture_year, created_at)
   - `damage_detections` (damage_id, card_id, panel_name, damage_type, severity, confidence, detected_at)
   - `repairs` (repair_id, card_id, panel_name, repair_action, repair_cost, approved, created_at)
   - `quotes` (quote_id, card_id, total_estimated_cost, currency, generated_at)
3. If question references non-existent tables/columns → Returns "INCORRECT"
4. If question attempts to modify data → Returns "INCORRECT"
5. User gets prompted: **"Your question seems incorrect. Please rephrase."**

### 🔄 Smart Context Inference

The AI understands context-based mapping:
- Question mentions **"Fortuner"** → Automatically assumes it refers to the **model** column, not vehicle_type
- Question mentions **"Toyota"** → Correctly maps to the **manufacturer** column
- Partial information → AI intelligently infers what you're asking about

### 🤔 Ambiguity Detection - Handling Multiple Interpretations

Even when a query is valid SQL, the project detects when results could have multiple interpretations:

**Example Ambiguous Scenarios:**
```
Q: "How much does it cost?"
A: AMBIGUOUS (which vehicle? which repair? multiple possible answers)

Q: "Tell me about panel damages"
A: AMBIGUOUS (high-severity damages? all damages? specific panel?)
```

**How it works:**
1. SQL query executes successfully and returns results
2. Mistral AI summarization layer receives: the original question + raw results
3. AI applies logic: *"Does this question have 1 logical answer but I'm getting multiple different answers?"*
4. If yes → Returns "AMBIGUOUS"
5. User gets prompted: **"Your question seems ambiguous. Could you clarify?"**

**Fixed Examples:**
```
Q: "How many high-severity damages exist?" 
A: ✓ Single, unambiguous number

Q: "Show me all approved repairs with their costs"
A: ✓ Clear, structured data matching the request
```

### 🔁 Automatic Retry Logic

If the AI API temporarily fails:
- Automatically retries **up to 3 times** with 2-second delays
- Prevents single network hiccups from breaking the conversation
- Falls back gracefully if all retries fail

### 🚫 No Results Handling

When a valid query returns no data:
- System detects the empty result set
- User sees: **"No results found."**
- User can refine their question and try again

## Why The Project is Intelligent

✅ **Three-Layer Validation**
- Input Validation (is the question about valid tables/columns?)
- Result Validation (do the results match the question's intent?)
- Database Validation (does the executed query actually work?)

✅ **Context-Aware Processing**
- Understands vehicle naming conventions
- Maps ambiguous terms to correct columns
- Infers database relationships from questions

✅ **Fault-Tolerant**
- Gracefully handles API failures with retries
- Manages SQL execution errors without crashing
- Provides meaningful error messages for users

✅ **Security-First**
- Blocks all modification attempts (DELETE, INSERT, UPDATE)
- Prevents schema exploitation (non-existent table/column access)
- Validates every query against the actual schema

✅ **User Experience**
- Guides users to rephrase incorrect/ambiguous questions
- Shows generated SQL so users understand what's happening
- Provides concise, natural language answers instead of raw data tables

## Flow Diagram

1. **User asks a question** → "How many high-severity damages exist?"
2. **Validation layer** → Checks if tables, columns, and query type are valid
   - ✓ Valid → Proceeds to step 3
   - ✗ Invalid → Asks user to rephrase (goes back to step 1)
3. **SQL conversion** → Converts to SQL query
4. **Query execution** → Runs against PostgreSQL database
5. **Result analysis** → Checks if results are clear and unambiguous
   - ✓ Clear answer → Proceeds to step 6
   - ✗ Ambiguous → Asks user to clarify (goes back to step 1)
6. **Summarization** → Converts raw data to natural language
7. **Response display** → Shows user-friendly answer

If any step fails or detects a problem, the user is immediately notified and guided to improve their question.

## Project Files

- `main.py` - Core application with the conversation loop
- `system_prompts.py` - AI prompts that guide the query conversion and result summarization
- `requirements.txt` - Python package dependencies
- `data/` - Folder containing CSV files with initial data

## Notes

- The project is read-only (cannot modify the database)
- Uses PostgreSQL as the database backend
- Powered by Mistral AI's `mistral-large-latest` model
- Questions are validated before being converted to SQL queries
