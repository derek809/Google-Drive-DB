---

## 2. alamo_bot.py
This is the complete, single-file implementation of the orchestrator.

```python
#!/usr/bin/env python3
import os
import re
import json
import logging
import requests
from typing import Dict, List, Optional, Any
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Logging setup
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

def load_config():
    with open('config/telegram_config.json') as f:
        t_cfg = json.load(f)
    with open('config/ollama_config.json') as f:
        o_cfg = json.load(f)
    return t_cfg, o_cfg

TELEGRAM_CONFIG, OLLAMA_CONFIG = load_config()

class OllamaLLM:
    def __init__(self, model, base_url):
        self.model = model
        self.api_url = f"{base_url}/api/generate"

    async def generate(self, system_prompt, user_prompt, temperature=0.1):
        full_prompt = f"{system_prompt}\n\n{user_prompt}"
        try:
            response = requests.post(self.api_url, json={
                "model": self.model, "prompt": full_prompt,
                "temperature": temperature, "stream": False
            }, timeout=30)
            return response.json()['response'].strip()
        except Exception as e:
            logger.error(f"Ollama Error: {e}")
            return "I'm having trouble connecting to my local brain."

class IntentClassifier:
    def __init__(self, classification_map, decision_tree):
        self.classification_map = classification_map
        self.decision_tree = decision_tree

    def classify(self, message, session):
        message_lower = message.lower()
        # 1. Check for basic confirmation flow
        if session.get('awaiting_confirmation'):
            if any(word in message_lower for word in ['yes', 'confirm', 'proceed', 'ok']):
                return {'intent': session['current_intent'], 'confidence': 0.95, 'extracted_vars': session['extracted_vars']}
        
        # 2. Pattern Matching
        for intent, config in self.classification_map.items():
            for pattern in config.get('patterns', []):
                match = re.search(pattern, message, re.IGNORECASE)
                if match:
                    return {'intent': intent, 'confidence': 0.9, 'extracted_vars': match.groupdict()}
        
        return {'intent': 'clarification_needed', 'confidence': 0.0, 'extracted_vars': {}}

class DecisionEngine:
    def __init__(self, constraints, refusals):
        self.constraints = constraints
        self.refusals = refusals

    def evaluate(self, intent, vars):
        for refusal in self.refusals:
            if refusal['condition'].lower() in intent.lower():
                return {'action': 'refuse', 'message': refusal['response']}
        return {'action': 'proceed'}

class AlamoBot:
    def __init__(self):
        self.brain_path = "brain/operations_assistant"
        self.brain = self._load_brain()
        self.llm = OllamaLLM(OLLAMA_CONFIG['model'], OLLAMA_CONFIG['base_url'])
        self.classifier = IntentClassifier(self.brain['classification_map'], self.brain['decision_tree'])
        self.engine = DecisionEngine(self.brain['system_constraints'], self.brain['refusal_conditions'])
        self.sessions = {}

    def _load_brain(self):
        data = {}
        files = ['system_constraints', 'decision_tree', 'classification_map', 'response_templates', 'refusal_conditions', 'confidence_thresholds']
        with open(f"{self.brain_path}/core_directive.txt") as f:
            data['core_directive'] = f.read()
        for f_name in files:
            with open(f"{self.brain_path}/{f_name}.json") as f:
                data[f_name] = json.load(f)
        return data

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        if uid not in TELEGRAM_CONFIG['authorized_user_ids']:
            return
            
        text = update.message.text
        session = self.sessions.get(uid, {'awaiting_confirmation': False, 'extracted_vars': {}})
        
        # Logic Flow
        classification = self.classifier.classify(text, session)
        decision = self.engine.evaluate(classification['intent'], classification['extracted_vars'])
        
        if decision['action'] == 'refuse':
            await update.message.reply_text(decision['message'])
            return

        # Template Filling & LLM
        intent_cfg = self.brain['response_templates'].get(classification['intent'], {})
        if classification['confidence'] > 0.7:
            response = intent_cfg.get('template', "Processing...").format(**classification['extracted_vars'])
            if intent_cfg.get('requires_confirmation') and not session['awaiting_confirmation']:
                session.update({'awaiting_confirmation': True, 'current_intent': classification['intent'], 'extracted_vars': classification['extracted_vars']})
                self.sessions[uid] = session
                await update.message.reply_text(f"{response}\n\nShould I proceed? (Yes/No)")
            else:
                await update.message.reply_text(response)
                self.sessions[uid] = {'awaiting_confirmation': False, 'extracted_vars': {}}
        else:
            await update.message.reply_text("I'm not quite sure. Could you rephrase that?")

async def start(u, c):
    await u.message.reply_text("🤖 Alamo Bot Active. How can I assist with OCC Operations?")

def main():
    bot = AlamoBot()
    app = Application.builder().token(TELEGRAM_CONFIG['bot_token']).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_message))
    logger.info("Alamo Bot Started...")
    app.run_polling()

if __name__ == '__main__':
    main()