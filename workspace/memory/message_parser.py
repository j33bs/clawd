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
        """Parse message into structured intent."""
        message = message.lower()
        
        # Extract intent
        intents = []
        for intent, patterns in self.intent_patterns.items():
            if any(p in message for p in patterns):
                intents.append(intent)
        
        # Extract entities (simple)
        entities = {
            "urls": re.findall(r'http[s]?://\S+', message),
            "paths": re.findall(r'/[\w/]+', message),
            "numbers": re.findall(r'\d+', message),
        }
        
        # Extract sentiment (very simple)
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
            "length": len(message)
        }
    
    def should_auto_respond(self, parsed):
        """Determine if this should trigger autonomous action."""
        # High sentiment positive + status intent = show status
        if "status" in parsed["intents"] and parsed["sentiment"] > 0.6:
            return True
        
        return False


# Test
if __name__ == "__main__":
    parser = MessageParser()
    
    tests = [
        "how's our relationship doing?",
        "can you research TACTI architecture?",
        "write a function to parse JSON",
        "what is consciousness?",
        "run the integration test"
    ]
    
    print("🧪 Message Parser Test")
    print("=" * 50)
    for msg in tests:
        result = parser.parse(msg)
        print(f"\n📝 '{msg}'")
        print(f"   Intents: {result['intents']}")
        print(f"   Sentiment: {result['sentiment']}")
        print(f"   Auto-respond: {parser.should_auto_respond(result)}")
