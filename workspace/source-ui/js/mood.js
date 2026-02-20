/**
 * Agent Mood Status Indicator
 * Displays agent "mood" based on system health
 */

const MOODS = {
  excellent: { emoji: '🤩', label: 'Excellent', color: '#00ff88' },
  good: { emoji: '😊', label: 'Good', color: '#88ff00' },
  okay: { emoji: '😐', label: 'Okay', color: '#ffaa00' },
  stressed: { emoji: '😰', label: 'Stressed', color: '#ff5500' },
  critical: { emoji: '🆘', label: 'Critical', color: '#ff0000' }
};

function calculateMood(health) {
  if (!health) return MOODS.okay;
  
  let score = 100;
  
  // Factor in CPU, memory, disk
  if (health.cpu > 80) score -= 20;
  if (health.memory > 85) score -= 20;
  if (health.disk > 90) score -= 15;
  
  // Factor in failures
  if (health.failures > 0) score -= health.failures * 10;
  
  // Factor in uptime (longer = more stable)
  if (health.uptimeHours && health.uptimeHours < 1) score -= 10;
  
  if (score >= 90) return MOODS.excellent;
  if (score >= 70) return MOODS.good;
  if (score >= 50) return MOODS.okay;
  if (score >= 30) return MOODS.stressed;
  return MOODS.critical;
}

function renderMood(mood, container) {
  container.innerHTML = `
    <div class="mood-indicator" style="
      background: ${mood.color}22;
      border: 2px solid ${mood.color};
      border-radius: 12px;
      padding: 8px 16px;
      display: inline-flex;
      align-items: center;
      gap: 8px;
      font-family: system-ui;
    ">
      <span style="font-size: 24px;">${mood.emoji}</span>
      <span style="color: ${mood.color}; font-weight: bold;">${mood.label}</span>
    </div>
  `;
}

// Export for use
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { MOODS, calculateMood, renderMood };
}
