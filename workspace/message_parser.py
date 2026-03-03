#!/usr/bin/env python3
"""
Message Parser
Parses user messages to extract structured intent.
"""
import re

class MessageParser:
    def __init__(self):
        self.intent_patterns = {
            "research": ["research", "find", "look up", "search", "learn about"],
            "code": ["code", "write", "implement", "build", "create"],
            "question": ["what", "how", "why", "when", "where", "?"],
            "command": ["do", "run", "execute", "call"],
            "status": ["status", "how are", "how's", "check"],
            "relationship": ["relationship", "trust", "bond", "connection"],
        }
    
    def parse(self, message):
        message = message.lower()
        
        intents = []
        for intent, patterns in self.intent_patterns.items():
            if any(p in message for p in patterns):
                intents.append(intent)
        
        entities = {
            "urls": re.findall(r'http[s]?://\S+', message),
            "paths": re.findall(r'/[\w/]+', message),
        }
        
        positive = ["good", "great", "thanks", "love", "yes", "nice"]
        negative = ["bad", "no", "don't", "wrong", "stop"]
        
        sentiment = 0.5
        if any(p in message for p in positive):
            sentiment = 0.7
        if any(p in message for p in negative):
            sentiment = 0.3
        
        return {
            "raw": message,
            "intents": intents,
            "entities": entities,
            "sentiment": sentiment,
        }

if __name__ == "__main__":
    parser = MessageParser()
    tests = [
        "how's our relationship doing?",
        "can you research TACTI?",
        "write a function",
    ]
    for msg in tests:
        r = parser.parse(msg)
        print(f"'{msg}' -> {r['intents']}")
