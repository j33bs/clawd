/**
 * Agent Mood Status Indicator
 * Based on Circumplex Emotion Model (Russell, 1980)
 * 
 * Valence (pleasure): -1 (negative) to +1 (positive)
 * Arousal (activation): 0 (low) to 1 (high)
 * 
 *         High Arousal
 *              │
 *   Excited   │   Anxious
 *   (+V,+A)   │   (-V,+A)
 *    fun 🤩   │    stressful 😰
 *   ----------+----------
 *   Relaxed   │   Bored
 *   (+V,-A)   │   (-V,-A)
 *    calm 😊  │    depressed 😐
 *              │
 *         Low Arousal
 */

const MOOD_POSITIONS = {
  // High Arousal + Positive Valence
  'excited':    { x: 0.8, y: 0.9, emoji: '🤩', label: 'Excited', color: '#ffdd00' },
  'alert':      { x: 0.5, y: 0.8, emoji: '👀', label: 'Alert', color: '#ffaa00' },
  'tense':      { x: 0.2, y: 0.8, emoji: '😬', label: 'Tense', color: '#ff6600' },
  'anxious':    { x: -0.2, y: 0.8, emoji: '😰', label: 'Anxious', color: '#ff4400' },
  'stressed':   { x: -0.5, y: 0.7, emoji: '😫', label: 'Stressed', color: '#ff2200' },
  'frustrated': { x: -0.8, y: 0.6, emoji: '😤', label: 'Frustrated', color: '#ff0000' },
  
  // Low Arousal + Positive Valence
  'happy':      { x: 0.8, y: 0.4, emoji: '😊', label: 'Happy', color: '#88ff00' },
  'content':    { x: 0.5, y: 0.3, emoji: '🙂', label: 'Content', color: '#66cc00' },
  'calm':       { x: 0.2, y: 0.2, emoji: '😌', label: 'Calm', color: '#44aa00' },
  'relaxed':    { x: -0.2, y: 0.2, emoji: '😴', label: 'Relaxed', color: '#228800' },
  'tired':      { x: -0.5, y: 0.3, emoji: '😪', label: 'Tired', color: '#666600' },
  'bored':      { x: -0.8, y: 0.4, emoji: '😐', label: 'Bored', color: '#555500' },
  
  // Low Arousal + Negative Valence  
  'sad':        { x: -0.8, y: -0.2, emoji: '😢', label: 'Sad', color: '#4444ff' },
  'depressed':  { x: -0.5, y: -0.3, emoji: '💔', label: 'Depressed', color: '#3333aa' },
  'lonely':     { x: -0.2, y: -0.4, emoji: '😔', label: 'Lonely', color: '#222288' },
  'neutral':    { x: 0.0, y: 0.0, emoji: '😐', label: 'Neutral', color: '#888888' },
  
  // High Arousal + Negative Valence (bottom right quadrant weird but whatever)
  'worried':    { x: 0.3, y: -0.2, emoji: '😟', label: 'Worried', color: '#aa4400' },
  'fearful':    { x: 0.6, y: -0.3, emoji: '😨', label: 'Fearful', color: '#cc2200' },
  'terrified':  { x: 0.9, y: -0.4, emoji: '🆘', label: 'Terrified', color: '#ff0000' },
};

/**
 * Calculate circumplex position from valence and arousal
 * @param {number} valence -1 to 1
 * @param {number} arousal 0 to 1
 */
function circumplexPosition(valence, arousal) {
  return {
    x: valence,  // -1 to 1
    y: (arousal * 2) - 1  // 0 to 1 → -1 to 1
  };
}

/**
 * Find closest mood to the circumplex position
 */
function findClosestMood(valence, arousal) {
  const pos = circumplexPosition(valence, arousal);
  
  let closest = 'neutral';
  let minDist = Infinity;
  
  for (const [mood, data] of Object.entries(MOOD_POSITIONS)) {
    const dist = Math.sqrt(Math.pow(pos.x - data.x, 2) + Math.pow(pos.y - data.y, 2));
    if (dist < minDist) {
      minDist = dist;
      closest = mood;
    }
  }
  
  return MOOD_POSITIONS[closest];
}

/**
 * Load agent state from filesystem
 */
async function loadAgentState(agentId = 'planner') {
  try {
    const response = await fetch(`/api/state/valence/${agentId}.json`);
    if (response.ok) {
      return await response.json();
    }
  } catch (e) {
    // State not available
  }
  return null;
}

/**
 * Calculate mood from system health + agent state
 */
async function calculateMood() {
  // Default neutral state
  let valence = 0;
  let arousal = 0.5;
  
  // Try to load valence from state
  try {
    const state = await loadAgentState('planner');
    if (state && state.valence !== undefined) {
      valence = state.valence;
    }
  } catch (e) {
    // Use defaults
  }
  
  // Simple arousal from time of day (mock for now)
  const hour = new Date().getHours();
  if (hour >= 9 && hour <= 17) {
    arousal = 0.7; // Working hours = higher arousal
  } else if (hour >= 22 || hour <= 6) {
    arousal = 0.2; // Night = low arousal
  }
  
  return {
    ...findClosestMood(valence, arousal),
    valence,
    arousal,
    raw: { valence, arousal }
  };
}

/**
 * Render mood to container
 */
function renderMood(mood, container) {
  container.innerHTML = `
    <div class="mood-widget" style="
      background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
      border: 2px solid ${mood.color};
      border-radius: 16px;
      padding: 16px;
      font-family: system-ui, -apple-system, sans-serif;
      min-width: 200px;
    ">
      <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 12px;">
        <span style="font-size: 36px;">${mood.emoji}</span>
        <div>
          <div style="color: ${mood.color}; font-size: 18px; font-weight: bold;">${mood.label}</div>
          <div style="color: #888; font-size: 12px;">Circumplex Model</div>
        </div>
      </div>
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; font-size: 11px;">
        <div style="background: rgba(255,255,255,0.1); padding: 6px; border-radius: 6px;">
          <div style="color: #666;">Valence</div>
          <div style="color: ${mood.raw.valence >= 0 ? '#4f4' : '#f44'}; font-weight: bold;">
            ${mood.raw.valence.toFixed(2)}
          </div>
          <div style="color: #555; font-size: 10px;">${mood.raw.valence >= 0 ? 'positive' : 'negative'}</div>
        </div>
        <div style="background: rgba(255,255,255,0.1); padding: 6px; border-radius: 6px;">
          <div style="color: #666;">Arousal</div>
          <div style="color: #4af; font-weight: bold;">${mood.raw.arousal.toFixed(2)}</div>
          <div style="color: #555; font-size: 10px;">${mood.raw.arousal >= 0.5 ? 'activated' : 'resting'}</div>
        </div>
      </div>
    </div>
  `;
}

// Export for module use
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { 
    MOOD_positions: MOOD_POSITIONS,
    circumplexPosition, 
    findClosestMood, 
    calculateMood, 
    renderMood 
  };
}
