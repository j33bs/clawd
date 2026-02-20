/**
 * Living Mood Widget - Circumnplex Emotion Model
 */

const MOOD_COLORS = {
  excited:    { hue: 45,  sat: 100, light: 60, emoji: '🤩', label: 'EXCITED' },
  happy:      { hue: 90,  sat: 80,  light: 65, emoji: '😊', label: 'HAPPY' },
  content:    { hue: 120, sat: 60,  light: 55, emoji: '🙂', label: 'CONTENT' },
  calm:       { hue: 150, sat: 40,  light: 50, emoji: '😌', label: 'CALM' },
  relaxed:    { hue: 180, sat: 30,  light: 45, emoji: '😴', label: 'RELAXED' },
  anxious:    { hue: 30,  sat: 90,  light: 55, emoji: '😰', label: 'ANXIOUS' },
  stressed:   { hue: 15,  sat: 95,  light: 50, emoji: '😫', label: 'STRESSED' },
  frustrated: { hue: 0,   sat: 80,  light: 45, emoji: '😤', label: 'FRUSTRATED' },
  sad:        { hue: 240, sat: 60,  light: 50, emoji: '😢', label: 'SAD' },
  bored:      { hue: 270, sat: 30,  light: 45, emoji: '😐', label: 'BORED' },
  neutral:    { hue: 200, sat: 10, light: 50, emoji: '😐', label: 'NEUTRAL' },
};

function renderLivingMood(valence, arousal) {
  console.log('Rendering mood:', valence, arousal);
  const container = document.getElementById('mood-widget');
  if (!container) {
    console.log('Container not found!');
    return;
  }
  
  const pos = { x: (valence + 1) / 2, y: arousal };
  const isRight = pos.x > 0.5;
  const isHigh = pos.y > 0.5;
  
  let baseMood = isRight ? (isHigh ? 'excited' : 'calm') : (isHigh ? 'anxious' : 'sad');
  const mood = MOOD_COLORS[baseMood];
  const hue = mood.hue;
  const color = `hsl(${hue}, ${mood.sat}%, ${mood.light}%)`;
  
  container.innerHTML = `
    <div style="position:relative;padding:12px;background:linear-gradient(135deg,hsla(${hue},60%,30%,0.3) 0%,#141428 100%);border-radius:12px;border:1px solid ${color}44;overflow:hidden;">
      <div style="position:absolute;top:50%;left:50%;width:150%;height:150%;transform:translate(-50%,-50%);background:radial-gradient(circle,${color}08 0%,transparent 70%);animation:breathe 3s ease-in-out infinite;"></div>
      <svg style="position:absolute;inset:0;width:100%;height:100%;opacity:0.15;" viewBox="0 0 100 100">
        <line x1="0" y1="50" x2="100" y2="50" stroke="white" stroke-width="0.5" stroke-dasharray="2,2"/>
        <line x1="50" y1="0" x2="50" y2="100" stroke="white" stroke-width="0.5" stroke-dasharray="2,2"/>
        <circle cx="50" cy="50" r="45" fill="none" stroke="white" stroke-width="0.3"/>
      </svg>
      <div style="position:relative;z-index:1;display:flex;align-items:center;gap:10px;">
        <div style="font-size:28px;animation:float 3s ease-in-out infinite;">${mood.emoji}</div>
        <div style="flex:1;">
          <div style="font-size:11px;font-weight:700;letter-spacing:1.5px;color:${color};text-shadow:0 0 10px ${color}44;">${mood.label}</div>
          <div style="font-size:9px;color:#888;font-family:monospace;margin-top:2px;">
            <span style="color:${valence >= 0 ? '#4f8' : '#f48'};">V:${valence.toFixed(2)}</span>
            <span style="color:#48f;margin-left:6px;">A:${arousal.toFixed(2)}</span>
          </div>
        </div>
      </div>
      <div style="position:absolute;bottom:0;left:0;right:0;height:3px;background:#222;">
        <div style="height:100%;width:${arousal * 100}%;background:linear-gradient(90deg,${color},${color}88);"></div>
      </div>
    </div>
    <style>
      @keyframes breathe {0%,100%{transform:translate(-50%,-50%)scale(1);opacity:0.6}50%{transform:translate(-50%,-50%)scale(1.1);opacity:1}}
      @keyframes float {0%,100%{transform:translateY(0)}50%{transform:translateY(-3px)}}
    </style>
  `;
}

async function initMood() {
  console.log('initMood called');
  try {
    const response = await fetch('/api/state/valence/planner.json');
    console.log('API response:', response.status);
    if (response.ok) {
      const state = await response.json();
      console.log('State:', state);
      const v = state.valence || 0;
      const hour = new Date().getHours();
      const a = (hour >= 9 && hour <= 17) ? 0.7 : (hour >= 22 || hour <= 6) ? 0.2 : 0.5;
      renderLivingMood(v, a);
    } else {
      renderLivingMood(0, 0.5);
    }
  } catch (e) {
    console.log('Mood error:', e);
    renderLivingMood(0, 0.5);
  }
  
  setInterval(async () => {
    try {
      const response = await fetch('/api/state/valence/planner.json');
      if (response.ok) {
        const state = await response.json();
        renderLivingMood(state.valence || 0, 0.5);
      }
    } catch (e) {}
  }, 15000);
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { MOOD_COLORS, renderLivingMood, initMood };
}
