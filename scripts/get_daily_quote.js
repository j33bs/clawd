#!/usr/bin/env node
const fs = require('fs');
const path = require('path');

const LITERATURE_DIR = path.join(process.env.HOME, 'clawd/memory/literature');
const STATE_FILE = path.join(LITERATURE_DIR, 'state.json');

// Ensure dir exists
if (!fs.existsSync(LITERATURE_DIR)) {
  console.error("Literature directory not found. Run extraction first.");
  process.exit(1);
}

// Load state
let state = { lastQuoteDate: null, deliveredQuotes: [] };
if (fs.existsSync(STATE_FILE)) {
  state = JSON.parse(fs.readFileSync(STATE_FILE, 'utf8'));
}

// Check if already ran today
const today = new Date().toISOString().split('T')[0];
if (process.argv.includes('--check') && state.lastQuoteDate === today) {
  console.log("ALREADY_DELIVERED");
  process.exit(0);
}

// Find text files
const files = fs.readdirSync(LITERATURE_DIR).filter(f => f.endsWith('.txt'));
if (files.length === 0) {
  console.error("No text files found.");
  process.exit(1);
}

// Pick a file (randomly or round-robin)
const file = files[Math.floor(Math.random() * files.length)];
const text = fs.readFileSync(path.join(LITERATURE_DIR, file), 'utf8');

// Pick a random chunk
const chunkSize = 2000;
const maxOffset = Math.max(0, text.length - chunkSize);
const offset = Math.floor(Math.random() * maxOffset);
const chunk = text.substring(offset, offset + chunkSize);

// Output for the agent to refine
console.log(`SOURCE: ${file}`);
console.log(`OFFSET: ${offset}`);
console.log("--- CHUNK ---");
console.log(chunk);
console.log("--- END CHUNK ---");

// Update state
state.lastQuoteDate = today;
fs.writeFileSync(STATE_FILE, JSON.stringify(state, null, 2));
