/**
 * Living Mood Widget - Circumnplex Emotion Model
 * 
 * A living, breathing representation of agent state.
 * Reflects the TACTI(C)-R principles:
 * - Valence (pleasure): -1 to +1
 * - Arousal (activation): 0 to 1
 * 
 * The mood is not static - it breathes, pulses, and reflects
 * the continuous state of the agent's inner world.
 */

const MOOD_COLORS = {
  // Positive valence (right side)
  excited:    { hue: 45,  sat: 100, light: 60, emoji: '🤩', label: 'EXCITED' },
  happy:      { hue: 90,  sat: 80,  light: 65, emoji: '😊', label: 'HAPPY' },
  content:    { hue: 120, sat: 60,  light: 55, emoji: '🙂', label: 'CONTENT' },
  calm:       { hue: 150, sat: 40,  light: 50, emoji: '😌', label: 'CALM' },
  relaxed:    { hue: 180, sat: 30,  light: 45, emoji: '😴', label: 'RELAXED' },
  
  // Negative valence (left side)
  anxious:    { hue: 30,  sat: 90,  light: 55, emoji: '😰', label: 'ANXIOUS' },
  stressed:   { hue: 15,  sat: 95,  light: 50, emoji: '😫', label: 'STRESSED' },
  frustrated: { hue: 0,   sat: 80,  light: 45, emoji: '😤', label: 'FRUSTRATED' },
  sad:        { hue: 240, sat: 60,  light: 50, emoji: '😢', label: 'SAD' },
  bored:      { hue: 270, sat: 30,  light: 45, emoji: '😐', label: 'BORED' },
  
  // Neutral
  neutral:    { hue: 200, sat: 10, light: 50, emoji: '😐', label: 'NEUTRAL' },
};

/**
 * Calculate position on circumplex from valence/arousal
 */
function circumplex(valence, arousal) {
  // Map valence (-1 to 1) to x (0 to 1)
  const x = (valence + 1) / 2;
  // Map arousal (0 to 1) to y (0 to 1)
  const y = arousal;
  
  return { x, y, valence, arousal };
}

/**
 * Interpolate between moods based on position
 */
function interpolateMood(valence, arousal) {
  const pos = circumplex(valence, arousal);
  
  // Determine quadrant
  const isRight = pos.x > 0.5;
  const isHigh = pos.y > 0.5;
  
  let baseMood;
  if (isRight && isHigh) baseMood = 'excited';
  else if (isRight && !isHigh) baseMood = 'calm';
  else if (!isRight && isHigh) baseMood = 'anxious';
  else baseMood = 'sad';
  
  // Blend with neighbors based on exact position
  const blendX = Math.abs(pos.x - 0.5) * 2; // 0 at center, 1 at edges
  const blendY = pos.y;
  
  return {
    ...MOOD_COLORS[baseMood],
    x: pos.x,
    y: pos.y,
    valence: valence,
    arousal: arousal,
    blend: blendX,
    pulseSpeed: 0.5 + (arousal * 1.5), // Higher arousal = faster pulse
    breatheDepth: 0.02 + (Math.abs(valence) * 0.08),
  };
}

/**
 * Render the living mood widget
 */
function renderLivingMood(valence, arousal) {
  const mood = interpolateMood(valence, arousal);
  const container = document.getElementById('mood-widget');
  if (!container) return;
  
  const hue = mood.hue;
  const color = `hsl(${hue}, ${mood.sat}%, ${mood.light}%)`;
  const bgColor = `hsla(${hue}, ${mood.sat}%, ${mood.light - 20}%, 0.3)`;
  
  container.innerHTML = `
    <div class="living-mood" style="
      position: relative;
      padding: 12px;
      background: linear-gradient(135deg, ${bgColor} 0%, rgba(20,20,40,0.8) 100%);
      border-radius: 12px;
      border: 1px solid ${color}44;
      overflow: hidden;
    ">
      <!-- Breathing background -->
      <div class="mood-breathe" style="
        position: absolute;
        top: 50%;
        left: 50%;
        width: 150%;
        height: 150%;
        transform: translate(-50%, -50%);
        background: radial-gradient(circle, ${color}08 0%, transparent 70%);
        animation: breathe ${3 / mood.pulseSpeed}s ease-in-out infinite;
      "></div>
      
      <!-- Circumplex position indicator -->
      <div class="mood-position" style="
        position: absolute;
        left: ${mood.x * 100}%;
        top: ${(1 - mood.y) * 100}%;
        width: 8px;
        height: 8px;
        background: ${color};
        border-radius: 50%;
        transform: translate(-50%, -50%);
        box-shadow: 0 0 ${10 + mood.arousal * 20}px ${color};
        animation: pulse ${2 / mood.pulseSpeed}s ease-in-out infinite;
      "></div>
      
      <!-- Axis lines -->
      <svg style="position: absolute; inset: 0; width: 100%; height: 100%; opacity: 0.15;" viewBox="0 0 100 100">
        <!-- Horizontal axis (valence) -->
        <line x1="0" y1="50" x2="100" y2="50" stroke="white" stroke-width="0.5" stroke-dasharray="2,2"/>
        <!-- Vertical axis (arousal) -->
        <line x1="50" y1="0" x2="50" y2="100" stroke="white" stroke-width="0.5" stroke-dasharray="2,2"/>
        <!-- Circumplex circle -->
        <circle cx="50" cy="50" r="45" fill="none" stroke="white" stroke-width="0.3"/>
      </svg>
      
      <!-- Main content -->
      <div style="position: relative; z-index: 1; display: flex; align-items: center; gap: 10px;">
        <div class="mood-emoji" style="
          font-size: 28px;
          animation: float ${3 - mood.arousal}s ease-in-out infinite;
        ">${mood.emoji}</div>
        <div style="flex: 1;">
          <div class="mood-label" style="
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 1.5px;
            color: ${color};
            text-shadow: 0 0 10px ${color}44;
          ">${mood.label}</div>
          <div class="mood-values" style="
            font-size: 9px;
            color: #888;
            font-family: 'JetBrains Mono', monospace;
            margin-top: 2px;
          ">
            <span style="color: ${valence >= 0 ? '#4f8' : '#f48'};">V:${valence.toFixed(2)}</span>
            <span style="color: #48f; margin-left: 6px;">A:${arousal.toFixed(2)}</span>
          </div>
        </div>
      </div>
      
      <!-- Energy bar -->
      <div class="energy-bar" style="
        position: absolute;
        bottom: 0;
        left: 0;
        right: 0;
        height: 3px;
        background: #222;
        overflow: hidden;
      ">
        <div class="energy-fill" style="
          height: 100%;
          width: ${mood.arousal * 100}%;
          background: linear-gradient(90deg, ${color}, ${color}88);
          animation: energyFlow ${4 - mood.arousal * 2}s linear infinite;
        "></div>
      </div>
    </div>
    
    <style>
      @keyframes breathe {
        0%, 100% { transform: translate(-50%, -50%) scale(1); opacity: 0.6; }
        50% { transform: translate(-50%, -50%) scale(1.1); opacity: 1; }
      }
      @keyframes pulse {
        0%, 100% { transform: translate(-50%, -50%) scale(1); }
        50% { transform: translate(-50%, -50%) scale(1.3); }
      }
      @keyframes float {
        0%, 100% { transform: translateY(0); }
        50% { transform: translateY(-3px); }
      }
      @keyframes energyFlow {
        0% { transform: translateX(-100%); }
        100% { transform: translateX(100%); }
      }
    </style>
  `;
}

/**
 * Load and render mood from system state
 */
async function initMood() {
  const emoji = document.getElementById('mood-emoji');
  const label = document.getElementById('mood-label');
  const valenceEl = document.getElementById('mood-valence');
  
  async function update() {
    try {
      const response = await fetch('/api/state/valence/planner.json');
      if (response.ok) {
        const state = await response.json();
        const v = state.valence || 0;
        // Derive arousal from time if not available
        const hour = new Date().getHours();
        const a = (hour >= 9 && hour <= 17) ? 0.7 : (hour >= 22 || hour <= 6) ? 0.2 : 0.5;
        
        renderLivingMood(v, a);
      }
    } catch (e) {
      renderLivingMood(0, 0.5); // Neutral default
    }
  }
  
  // Initial render
  await update();
  
  // Update every heartbeat
  setInterval(update, 15000);
}

// Legacy compatibility
function updateMoodDisplay(valence) {
  const arousal = 0.5;
  renderLivingMood(valence, arousal);
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { MOOD_COLORS, circumplex, interpolateMood, renderLivingMood, initMood };
}
