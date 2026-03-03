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

// Build list of available chunks (file + offset), exclude delivered
const chunkSize = 2000;
const available = [];
for (const file of files) {
  const text = fs.readFileSync(path.join(LITERATURE_DIR, file), 'utf8');
  const maxOffset = Math.max(0, text.length - chunkSize);
  // Sample offsets (every 2000 chars = ~100 chunks per file)
  for (let offset = 0; offset < maxOffset; offset += 2000) {
    const id = `${file}:${offset}`;
    if (!state.deliveredQuotes.includes(id)) {
      available.push({ file, offset });
    }
  }
}

if (available.length === 0) {
  // Reset if all delivered
  state.deliveredQuotes = [];
  fs.writeFileSync(STATE_FILE, JSON.stringify(state, null, 2));
  console.log("All quotes delivered. Starting over.");
  process.exit(0);
}

// Pick random available chunk
const pick = available[Math.floor(Math.random() * available.length)];
const text = fs.readFileSync(path.join(LITERATURE_DIR, pick.file), 'utf8');
const chunk = text.substring(pick.offset, pick.offset + chunkSize);

// Output for the agent to refine
console.log(`SOURCE: ${pick.file}`);
console.log(`OFFSET: ${pick.offset}`);
console.log("--- CHUNK ---");
console.log(chunk);
console.log("--- END CHUNK ---");

// Update state - track delivered quote
state.lastQuoteDate = today;
state.deliveredQuotes.push(`${pick.file}:${pick.offset}`);
fs.writeFileSync(STATE_FILE, JSON.stringify(state, null, 2));
