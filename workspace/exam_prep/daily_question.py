#!/usr/bin/env python3
"""Daily practice question for NVIDIA LLM Certification - seeded by date."""

import os
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
QUESTIONS_FILE = os.path.join(SCRIPT_DIR, "questions.md")

def load_questions():
    """Parse questions from the markdown file."""
    with open(QUESTIONS_FILE, "r") as f:
        content = f.read()
    
    # Split by Question markers
    questions = content.split("\n## Question ")[1:]
    return questions

def get_daily_question():
    """Get a question seeded by today's date."""
    questions = load_questions()
    
    # Use date as seed for consistent daily rotation
    today = datetime.now().date()
    day_of_year = today.timetuple().tm_yday
    
    # Rotate through questions based on day of year
    index = day_of_year % len(questions)
    selected = questions[index]
    
    # Split question and answer
    parts = selected.split("**Answer:**")
    if len(parts) == 2:
        question_part = parts[0].strip()
        
        # Get the question text - first line is the number+topic
        q_lines = question_part.split('\n')
        topic_line = q_lines[0] if q_lines else ""
        
        # Get remaining lines (the actual question + options)
        q_content = '\n'.join(q_lines[1:]).strip()
        
        return f"## {topic_line}\n\n{q_content}"
    
    return selected

def get_answer():
    """Get the answer for today's question."""
    questions = load_questions()
    today = datetime.now().date()
    day_of_year = today.timetuple().tm_yday
    index = day_of_year % len(questions)
    selected = questions[index]
    
    parts = selected.split("**Answer:**")
    if len(parts) == 2:
        return parts[1].strip()
    return ""

def main():
    import sys
    show_answer = len(sys.argv) > 1 and sys.argv[1] == "--answer"
    
    if show_answer:
        print(get_answer())
    else:
        print(get_daily_question())

if __name__ == "__main__":
    main()
