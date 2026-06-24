# Recruiting Metrics Automation Engine — Project Tracker

## Current Status

- Repo folder created
- Files organized into app, config, and sample_data folders
- README architecture updated
- .env file created but API keys not added yet
- requirements.txt exists but dependencies not added yet
- Git not initialized yet

## Next Steps

### 1. Add dependencies to requirements.txt

Paste:

openai
anthropic
python-dotenv
requests
pyyaml
pandas
slack_sdk
schedule
fastapi
uvicorn

### 2. Add API keys to .env

Add real values for:

OPENAI_API_KEY=
ANTHROPIC_API_KEY=
SLACK_WEBHOOK_URL=

Leave these as test values for now:

ATS_API_KEY=test_key
HRIS_API_KEY=test_key

### 3. Initialize Git

Run:

git init
git branch -M main
git status

### 4. Create Python environment

Run:

python -m venv .venv
source .venv/Scripts/activate

### 5. Install dependencies

Run:

pip install -r requirements.txt

### 6. First test run

Run:

python app/tier1_ats_agent.py

### 7. First local commit

Run only if stable:

git add .
git status
git commit -m "Initial recruiting metrics automation engine architecture"