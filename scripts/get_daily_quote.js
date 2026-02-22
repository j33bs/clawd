#!/usr/bin/env node
/**
 * Daily Quote Generator
 * 
 * Selects a quote for the day:
 * - 80% from curated quotes.json (local literature, Nietzsche, philosophy)
 * - 20% from QuoteAPI (dynamically fetched)
 */

import fs from 'fs';
import path from 'path';
import https from 'https';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const QUOTES_FILE = path.join(process.env.HOME, '.openclaw/workspace/data/quotes.json');
const STATE_FILE = path.join(process.env.HOME, '.openclaw/workspace/data/quotes-state.json');

// Ensure data dir exists
const DATA_DIR = path.dirname(QUOTES_FILE);
if (!fs.existsSync(DATA_DIR)) {
  fs.mkdirSync(DATA_DIR, { recursive: true });
}

// Load quotes
let quotesData;
try {
  quotesData = JSON.parse(fs.readFileSync(QUOTES_FILE, 'utf8'));
} catch (e) {
  console.error("Quotes file not found:", e.message);
  process.exit(1);
}

// Load state
let state = { lastQuoteDate: null, apiUsed: false };
if (fs.existsSync(STATE_FILE)) {
  state = JSON.parse(fs.readFileSync(STATE_FILE, 'utf8'));
}

// Check if already ran today
const today = new Date().toISOString().split('T')[0];
if (process.argv.includes('--check') && state.lastQuoteDate === today) {
  console.log("ALREADY_DELIVERED");
  process.exit(0);
}

// Determine source: 20% chance of API
const useApi = !state.apiUsed && Math.random() < 0.2;

let quote;

if (useApi) {
  // Fetch from API
  quote = await fetchApiQuote();
  if (!quote) {
    // Fallback to local if API fails
    quote = getRandomQuote(quotesData.quotes);
  } else {
    state.apiUsed = true;
  }
} else {
  // Use local curated quotes
  quote = getRandomQuote(quotesData.quotes);
}

// Output
console.log(`THEME: ${quote.themes.join(', ')}`);
console.log("--- QUOTE ---");
console.log(quote.text);
if (quote.author) {
  console.log(`— ${quote.author}`);
}
console.log("--- END QUOTE ---");

// Update state
state.lastQuoteDate = today;
fs.writeFileSync(STATE_FILE, JSON.stringify(state, null, 2));

function getRandomQuote(quotes) {
  return quotes[Math.floor(Math.random() * quotes.length)];
}

function fetchApiQuote() {
  return new Promise((resolve) => {
    https.get('https://zenquotes.io/api/today', (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          const [q] = JSON.parse(data);
          resolve({
            text: q.q,
            author: q.a,
            source: 'Quote API',
            themes: ['Vitality'] // default theme for API quotes
          });
        } catch (e) {
          resolve(null);
        }
      });
    }).on('error', () => resolve(null));
  });
}
