# Mode 4 - M1 + Clawdbot via Telegram

Email processing system that runs on your M1 MacBook and receives commands via Telegram.

## Quick Start

### 1. Copy files to M1

Copy this entire `mode4` folder to your M1:
```bash
scp -r mode4 your-m1:~/mode4
```

Also copy `sheets_client.py` from the parent directory:
```bash
scp sheets_client.py your-m1:~/mode4/
```

### 2. Set up Python environment

```bash
cd ~/mode4
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Install Ollama

```bash
brew install ollama
ollama pull llama3.2
```

Start Ollama (runs in background):
```bash
ollama serve
```

### 4. Create Telegram Bot

1. Open Telegram, search for `@BotFather`
2. Send `/newbot`
3. Name: `MCP Email Processor`
4. Username: `your_mcp_bot` (must end in `bot`)
5. Copy the API token

Get your user ID:
1. Send a message to `@userinfobot` on Telegram
2. Note your user ID number

### 5. Configure credentials

Create credentials directory:
```bash
mkdir -p ~/mode4/credentials
```

**Telegram config** - Create `~/mode4/credentials/telegram_config.json`:
```json
{
  "bot_token": "YOUR_BOT_TOKEN_FROM_BOTFATHER",
  "allowed_users": [YOUR_TELEGRAM_USER_ID],
  "admin_chat_id": YOUR_TELEGRAM_USER_ID
}
```

**Google Sheets** - Copy your service account JSON:
```bash
cp path/to/service-account.json ~/mode4/credentials/sheets_service_account.json
```

**Gmail OAuth** - Download OAuth credentials from Google Cloud Console:
1. Go to console.cloud.google.com
2. Select your project, enable Gmail API
3. Go to APIs & Services > Credentials
4. Create OAuth 2.0 Client ID (Desktop app)
5. Download JSON and save as `~/mode4/credentials/gmail_credentials.json`

### 6. Update m1_config.py

Edit `~/mode4/m1_config.py`:
- Set `SPREADSHEET_ID` to your Google Sheet ID
- Set `TELEGRAM_BOT_TOKEN` (or use telegram_config.json)
- Set `TELEGRAM_ALLOWED_USERS` (or use telegram_config.json)

### 7. First run - Gmail OAuth

On first run, Gmail will open a browser for OAuth consent:
```bash
cd ~/mode4
source venv/bin/activate
python gmail_client.py
```

Follow the prompts to authorize Gmail access. Token is saved for future runs.

### 8. Run Mode 4

```bash
cd ~/mode4
source venv/bin/activate
python mode4_processor.py
```

## Usage

Send messages to your Telegram bot in these formats:

```
Re: [subject] - [instruction]
From [sender] - [instruction]
[keyword] - [instruction]
```

Examples:
```
Re: W9 Request - send W9 and wiring instructions
From john@example.com - confirm payment received
latest invoice - approve and confirm timeline
```

Commands:
- `/status` - Check system status
- `/help` - Show help message

## Architecture

```
iPhone/iPad
    |
    v
Telegram Bot --> mode4_processor.py
                      |
          +-----------+-----------+
          |           |           |
          v           v           v
       Gmail      Ollama      Google
       Client     Client      Sheets
          |           |           |
          v           v           |
     Search +     Triage +       |
     Draft        Draft Gen      |
          |           |           |
          +-----------+-----------+
                      |
                      v
               Gmail Drafts
```

## Files

| File | Purpose |
|------|---------|
| `mode4_processor.py` | Main orchestrator |
| `telegram_handler.py` | Telegram bot integration |
| `gmail_client.py` | Gmail search and draft creation |
| `ollama_client.py` | Local LLM triage and generation |
| `pattern_matcher.py` | Pattern matching from Sheets |
| `m1_config.py` | Configuration settings |
| `sheets_client.py` | Google Sheets API wrapper (copied from parent) |

## Troubleshooting

**Ollama not responding**
```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Start Ollama
ollama serve

# Check model is installed
ollama list
```

**Gmail OAuth error**
- Delete `~/mode4/credentials/gmail_token.json` and re-run to re-authenticate

**Telegram bot not responding**
- Check bot token is correct
- Check your user ID is in `allowed_users`
- Check internet connection

**Sheets permission error**
- Ensure spreadsheet is shared with service account email
- Check service account JSON path is correct

## Sync from Work Laptop

Run on work laptop to push patterns/templates to Sheets:
```bash
python bootstrap_sync_sheets.py
```

This syncs SQLite (source of truth) to Google Sheets so M1 can read patterns.

## Logs

Logs are written to `~/mode4/mode4.log`

View recent logs:
```bash
tail -f ~/mode4/mode4.log
```
