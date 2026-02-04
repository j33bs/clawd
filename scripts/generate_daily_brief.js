#!/usr/bin/env node

// Script to generate daily research brief with 3 options
const fs = require('fs');
const path = require('path');

// Function to get today's date in YYYY-MM-DD format
function getToday() {
    const now = new Date();
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, '0');
    const day = String(now.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
}

// Function to generate research options based on Heath's interests
function generateResearchOptions() {
    const topics = [
        {
            title: "Latest IPNB Research",
            description: "Recent findings in Interpersonal Neurobiology and integration studies."
        },
        {
            title: "Psychedelic Therapy Regulatory Updates",
            description: "Current FDA approvals, clinical trials, and legal developments in psychedelic-assisted therapy."
        },
        {
            title: "Michael Levin's Bioelectric Research",
            description: "New developments in bioelectric pattern control and implications for healing."
        },
        {
            title: "ACT and Emotional Regulation Studies",
            description: "Recent research on Acceptance and Commitment Therapy techniques and outcomes."
        },
        {
            title: "HeartMath and Coherence Techniques",
            description: "Latest studies on heart rate variability and coherence training for stress reduction."
        },
        {
            title: "Music Therapy and Neural Plasticity",
            description: "Research on how music production and listening affect brain plasticity and emotional regulation."
        },
        {
            title: "Breathwork and Therapeutic Applications",
            description: "Clinical studies on breathwork techniques and their effectiveness in therapy."
        },
        {
            title: "Cannabis in Therapeutic Contexts",
            description: "Current research on cannabis compounds and therapeutic applications."
        },
        {
            title: "Therapeutic Workshop Effectiveness",
            description: "Studies on group therapy and workshop formats for emotional regulation."
        }
    ];

    // Shuffle and pick 3 random topics
    const shuffled = [...topics].sort(() => 0.5 - Math.random());
    return shuffled.slice(0, 3);
}

// Generate today's brief
const today = getToday();
const researchOptions = generateResearchOptions();

let briefContent = `# Morning Research Brief - ${today}\n\n`;
briefContent += "Good morning! Here are three research topics for you to choose from today:\n\n";

researchOptions.forEach((option, index) => {
    briefContent += `## Option ${(index + 1)}: ${option.title}\n`;
    briefContent += `${option.description}\n\n`;
});

briefContent += "Please select which topic you'd like to dive deeper into today.\n";

// Write to today's memory file
const memoryFilePath = path.join(__dirname, 'memory', `${today}.md`);
const dailyBriefPath = path.join(__dirname, `daily_brief_${today}.md`);

try {
    // Ensure memory directory exists
    const memoryDir = path.dirname(memoryFilePath);
    if (!fs.existsSync(memoryDir)) {
        fs.mkdirSync(memoryDir, { recursive: true });
    }
    
    // Write to daily brief file
    fs.writeFileSync(dailyBriefPath, briefContent);
    
    // Append to today's memory file if it exists, otherwise create it
    if (fs.existsSync(memoryFilePath)) {
        const existingContent = fs.readFileSync(memoryFilePath, 'utf8');
        if (!existingContent.includes("Morning Research Brief")) {
            fs.appendFileSync(memoryFilePath, `\n\n${briefContent}`);
        }
    } else {
        fs.writeFileSync(memoryFilePath, `# Memory - ${today}\n\n${briefContent}`);
    }
    
    console.log(`Daily brief generated for ${today} at ${dailyBriefPath}`);
} catch (error) {
    console.error('Error generating daily brief:', error);
}