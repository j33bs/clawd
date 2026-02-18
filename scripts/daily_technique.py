#!/usr/bin/env python3
"""
Therapeutic Techniques Database
Curated collection of techniques for daily briefing

Techniques aligned with: Vitality, Cognition, Flow, Malleability, Agency
(TACTI(C)-R principles)
"""
import json
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

# Curated therapeutic techniques
TECHNIQUES = [
    {
        "name": "Box Breathing",
        "category": "somatic",
        "principle": "vitality",
        "description": "A calming technique used by Navy SEALs. Inhale for 4 counts, hold for 4, exhale for 4, hold for 4. Activates parasympathetic nervous system.",
        "duration": "2-4 minutes",
        "when": "Morning or during stress",
        "benefits": ["Reduces cortisol", "Improves focus", "Calms anxiety"],
        "how": [
            "Sit comfortably with spine straight",
            "Inhale through nose for 4 counts",
            "Hold breath for 4 counts", 
            "Exhale slowly for 4 counts",
            "Hold empty for 4 counts",
            "Repeat 4-6 cycles"
        ]
    },
    {
        "name": "Body Scan Meditation",
        "category": "somatic",
        "principle": "vitality",
        "description": "Systematic attention to physical sensations throughout the body. Builds interoceptive awareness.",
        "duration": "10-20 minutes",
        "when": "Before sleep or after exercise",
        "benefits": ["Reduces body tension", "Improves sleep", "Builds body awareness"],
        "how": [
            "Lie down or sit comfortably",
            "Close eyes, breathe naturally",
            "Start at toes, notice sensations",
            "Move slowly up to crown of head",
            "Without judgment, observe each area",
            "Spend 5-10 seconds per body region"
        ]
    },
    {
        "name": "Cognitive Defusion",
        "category": "act",
        "principle": "cognition",
        "description": "ACT technique that creates distance from thoughts. Instead of 'I am a failure', say 'I'm having the thought I am a failure.'",
        "duration": "5-10 minutes",
        "when": "During negative thought spirals",
        "benefits": ["Reduces thought believability", "Decreases rumination", "Increases flexibility"],
        "how": [
            "Notice the thought appearing",
            "Label it: 'I'm having the thought that...'",
            "Add: 'I notice I'm thinking...'",
            "Try singing the thought (silly)",
            "Imagine thoughts as leaves floating by",
            "Return to present moment"
        ]
    },
    {
        "name": "Values Clarification",
        "category": "act",
        "principle": "agency",
        "description": "Identify what truly matters to you, independent of outcomes. Creates intrinsic direction.",
        "duration": "15-20 minutes",
        "when": "Decision-making or life transitions",
        "benefits": ["Increases clarity", "Reduces decision fatigue", "Builds intrinsic motivation"],
        "how": [
            "If you had $10M and 10 years, what would you do?",
            "What would you do even if you got paid nothing?",
            "What do you want remembered for?",
            "What problems do you enjoy solving?",
            "Rank: Family, Creativity, Learning, Growth, Service",
            "Write your top 3 values in one sentence each"
        ]
    },
    {
        "name": "Two-Chair Dialogue",
        "category": "gestalt",
        "principle": "cognition",
        "description": "Externalize internal conflicts by switching between two chairs representing different parts of yourself.",
        "duration": "10-15 minutes",
        "when": "Internal conflict or indecision",
        "benefits": ["Integrates shadow", "Resolves ambivalence", "Builds self-compassion"],
        "how": [
            "Place two chairs facing each other",
            "Sit in one, express one side's view",
            "Switch chairs, respond as the other",
            "Continue dialogue 3-5 rounds",
            "Find common ground or resolution",
            "Summarize insight in own words"
        ]
    },
    {
        "name": "Gratitude Letter",
        "category": "positive",
        "principle": "malleability",
        "description": "Write a letter to someone who positively impacted your life. Can be sent or kept private.",
        "duration": "15 minutes",
        "when": "Evening or weekend",
        "benefits": ["Increases happiness", "Strengthens relationships", "Improves wellbeing"],
        "how": [
            "Think of someone who helped you",
            "Write specific details: what they did, how it impacted you",
            "Include concrete examples",
            "Express genuine appreciation",
            "Read aloud to yourself",
            "Optionally send to the person"
        ]
    },
    {
        "name": "Mindful Walking",
        "category": "somatic",
        "principle": "flow",
        "description": "Walking meditation that transforms mundane movement into mindfulness practice.",
        "duration": "15-30 minutes",
        "when": "Any time, especially during blocks",
        "benefits": ["Generates dopamine", "Clears mental fog", "Connects mind-body"],
        "how": [
            "Walk slowly, heel-to-toe",
            "Notice each foot's sensation",
            "Sync breath with steps",
            "If distracted, gently return to walking",
            "Expand awareness: sounds, sights, smells",
            "End with 1 minute standing still"
        ]
    },
    {
        "name": "Self-Compassion Break",
        "category": "cbt",
        "principle": "malleability",
        "description": " Kristin Neff's technique: acknowledge suffering, common humanity, kindness to self.",
        "duration": "2-3 minutes",
        "when": "Self-criticism or shame",
        "benefits": ["Reduces self-criticism", "Increases emotional resilience", "Builds self-esteem"],
        "how": [
            "Place hand on heart or self-soothing touch",
            "Say: 'This is a moment of suffering' (mindfulness)",
            "Say: 'Suffering is part of human experience' (common humanity)",
            "Say: 'May I be kind to myself' (self-kindness)",
            "Or: 'May I give myself the compassion I need'",
            "Repeat until felt sense shifts"
        ]
    },
    {
        "name": "Acceptance Prayer (REBT)",
        "category": "rebt",
        "principle": "malleability",
        "description": "REBT technique for unshakeable core acceptance. 'I totally accept myself even with my flaws.'",
        "duration": "5 minutes",
        "when": "Deep-seated shame or worthiness issues",
        "benefits": ["Builds unconditional self-acceptance", "Reduces shame", "Increases psychological robustness"],
        "how": [
            "Sit quietly, breathe deeply",
            "Repeat: 'I am a flawed human being'",
            "Add: 'I am not perfect but I am acceptable'",
            "Say: 'I accept myself totally, unconditionally'",
            "Feel the difference between 'trying to accept' and 'actually accepting'",
            "Anchor with physical sensation"
        ]
    },
    {
        "name": "S.T.O.P. Technique",
        "category": "mindfulness",
        "principle": "cognition",
        "description": "Quick mindfulness intervention for reactive moments. Creates pause before action.",
        "duration": "30-60 seconds",
        "when": "Before reacting, during strong emotions",
        "benefits": ["Prevents reactive decisions", "Creates space", "Increases choice"],
        "how": [
            "S - Stop what you're doing",
            "T - Take a deep breath",
            "O - Observe: What am I feeling? What thoughts?",
            "P - Proceed mindfully with awareness"
        ]
    },
    {
        "name": "Worst-Best-Range",
        "category": "cbt",
        "principle": "cognition",
        "description": "Put anxious predictions in realistic perspective by considering range of outcomes.",
        "duration": "5 minutes",
        "when": "Anxiety about future events",
        "benefits": ["Reduces catastrophic thinking", "Creates realistic optimism", "Builds tolerance"],
        "how": [
            "Identify the anxious thought",
            "Ask: What's the WORST that could happen? (usually 5-10%)",
            "Ask: What's the BEST that could happen? (usually 10-20%)",
            "Ask: What's the MOST LIKELY? (usually 60-80%)",
            "Consider: Even if worst happened, could you cope?",
            "Adjust prediction accordingly"
        ]
    },
    {
        "name": "Loving-Kindness Meditation",
        "category": "humanistic",
        "principle": "malleability",
        "description": "Metta meditation. Generate feelings of love and goodwill toward self and others.",
        "duration": "10-20 minutes",
        "when": "Evening or connection needed",
        "benefits": ["Increases positive emotions", "Reduces depression", "Builds social connection"],
        "how": [
            "Sit comfortably, close eyes",
            "Generate love toward self: 'May I be happy, may I be healthy...'",
            "Extend to benefactor: 'May they be happy...'",
            "Extend to neutral person: 'May they be happy...'",
            "Extend to difficult person: 'May they be happy...'",
            "Extend to all beings: 'May all beings be happy...'"
        ]
    },
    {
        "name": "Bilateral Activation",
        "category": "somatic",
        "principle": "vitality",
        "description": "EMDR technique using left-right stimulation to process difficult material.",
        "duration": "5-10 minutes",
        "when": "Trauma processing or emotional regulation",
        "benefits": ["Processes trauma", "Reduces PTSD symptoms", "Integrates memory"],
        "how": [
            "Tap alternating left-right thighs (or arms)",
            "Or alternate looking left-right",
            "Or alternate auditory: 'left... right...'",
            "Focus on disturbing memory while tapping",
            "Continue until intensity decreases",
            "Notice what shifts"
        ]
    },
    {
        "name": "Schema Break",
        "category": "schema",
        "principle": "cognition",
        "description": "Identify early maladaptive schemas and actively challenge with adult perspective.",
        "duration": "10-15 minutes",
        "when": "Deep pattern recognition",
        "benefits": ["Identifies root patterns", "Weakens schemas", "Builds adult coping"],
        "how": [
            "Notice recurring emotional reaction",
            "Name the schema: 'I'm unlovable', 'I'm worthless', 'I must be perfect'",
            "Ask: When did I first feel this?",
            "What did I need then that I didn't get?",
            "What do I need NOW as an adult?",
            "Write a compassionate adult response"
        ]
    },
    {
        "name": "Sensory Grounding (5-4-3-2-1)",
        "category": "somatic",
        "principle": "vitality",
        "description": "Quick grounding technique using all 5 senses. Perfect for anxiety or dissociation.",
        "duration": "2-5 minutes",
        "when": "Anxiety, panic, dissociation, flashbacks",
        "benefits": ["Stops panic", "Brings to present", "Regulates nervous system"],
        "how": [
            "Name 5 things you SEE",
            "Name 4 things you can TOUCH",
            "Name 3 things you HEAR",
            "Name 2 things you can SMELL",
            "Name 1 thing you can TASTE",
            "Add: 1 slow deep breath"
        ]
    },
    {
        "name": "Commitment Action",
        "category": "act",
        "principle": "agency",
        "description": "Make one small committed action toward a value, despite fear or discomfort.",
        "duration": "5-10 minutes",
        "when": "Procrastination or avoidance",
        "benefits": ["Builds momentum", "Overcomes avoidance", "Moves toward values"],
        "how": [
            "Identify value you're moving toward",
            "What's one TINY action toward it? (5 minutes or less)",
            "Remove all pressure: just experiment",
            "Set timer, do it immediately",
            "Notice what resistance appears",
            "Complete and notice the aftermath"
        ]
    },
    {
        "name": "Ritual of Transition",
        "category": "existential",
        "principle": "agency",
        "description": "Create intentional transitions between life roles or phases.",
        "duration": "5-10 minutes",
        "when": "Role changes or life transitions",
        "benefits": ["Creates closure", "Builds identity", "Honors transitions"],
        "how": [
            "Name the transition (e.g., work to home)",
            "Create a physical cue: walk around building once",
            "Or verbal: 'I am transitioning from X to Y'",
            "Notice what you release, what you carry forward",
            "Breathe in new role, breathe out old",
            "Arrive fully in new context"
        ]
    },
    {
        "name": "Emotional Granulation",
        "category": "cbt",
        "principle": "cognition",
        "description": "Break broad emotions into specific feelings for better regulation.",
        "duration": "5 minutes",
        "when": "Overwhelmed by vague negative emotions",
        "benefits": ["Increases emotional granularity", "Improves regulation", "Reduces emotional chaos"],
        "how": [
            "Notice the emotion (e.g., 'bad feeling')",
            "Ask: What EXACTLY am I feeling?",
            "List: Anxious vs scared vs worried vs panicked",
            "Angry vs frustrated vs irritated vs furious",
            "Sad vs disappointed vs hurt vs hopeless",
            "Name the most precise one"
        ]
    },
    {
        "name": "TACTI(C)-R: Temporality Check",
        "category": "tacti",
        "principle": "tacti",
        "description": "Assess your experience across multiple time scales: moment, day, week, life.",
        "duration": "5 minutes",
        "when": "Integration or existential check-in",
        "benefits": ["Builds temporal perspective", "Integrates identity", "Reduces present bias"],
        "how": [
            "Moment: What am I experiencing RIGHT NOW? (sensation, emotion, thought)",
            "Today: What's the arc of today? (morning energy, afternoon dip?)",
            "Week: Where am I in the weekly cycle?",
            "Life: What chapter am I in? What's the theme?",
            "Eternity: How does this fit in the larger story?",
            "Return to now with expanded perspective"
        ]
    },
    {
        "name": "TACTI(C)-R: Arousal Audit",
        "category": "tacti",
        "principle": "tacti",
        "description": "Assess your arousal state across nervous system dimensions.",
        "duration": "3-5 minutes",
        "when": "Energy management or mood check",
        "benefits": ["Optimizes performance", "Prevents burnout", "Matches task to arousal"],
        "how": [
            "Energy: Low (depressed) ↔ High (manic)?",
            "Activation: Slow/lethargic ↔ Ramped/tense?",
            "Focus: Diffuse/scattered ↔ Narrow/rigid?",
            "Social: Withdrawn ↔ Over-connected?",
            "Regulate: What does your nervous system need?",
            "Choose one regulation action"
        ]
    }
]


def get_technique_for_day(date: datetime = None) -> Dict:
    """Get a technique based on the day of year (rotates through)."""
    if date is None:
        date = datetime.now(timezone.utc)
    
    # Day of year (1-365)
    day_of_year = date.timetuple().tm_yday
    
    # Index into techniques (cycles through)
    index = (day_of_year - 1) % len(TECHNIQUES)
    
    return TECHNIQUES[index]


def get_technique_by_principle(principle: str) -> List[Dict]:
    """Get techniques filtered by TACTI(C)-R principle."""
    return [t for t in TECHNIQUES if t.get("principle") == principle]


def format_briefing(technique: Dict) -> str:
    """Format technique for daily briefing."""
    benefits = ", ".join(technique.get("benefits", []))
    steps = "\n  ".join(technique.get("how", []))
    
    return f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🌿 DAILY THERAPEUTIC TECHNIQUE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📌 **{technique['name']}**
   Category: {technique['category']} | Principle: {technique['principle'].upper()}
   Duration: {technique['duration']}

📖 **What it is:**
   {technique['description']}

✨ **Benefits:** {benefits}

🧭 **When:** {technique['when']}

📝 **How:**
  {steps}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""


def main():
    # Today's technique
    technique = get_technique_for_day()
    print(format_briefing(technique))
    
    # Show principle breakdown
    print("\n📊 Principle Distribution:")
    principles = {}
    for t in TECHNIQUES:
        p = t.get("principle", "unknown")
        principles[p] = principles.get(p, 0) + 1
    for p, count in sorted(principles.items()):
        print(f"  {p.upper()}: {count} techniques")


if __name__ == "__main__":
    main()
