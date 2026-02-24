// AIN Agent Panel Data Loader
// Fetches AIN agent status, Φ measurement, and consciousness metrics

export async function loadAINPanel(fetchFn = fetch) {
  try {
    const [statusRes, phiRes] = await Promise.all([
      fetchFn('/api/ain/status'),
      fetchFn('/api/ain/phi')
    ]);
    
    const status = statusRes.ok ? await statusRes.json() : null;
    const phi = phiRes.ok ? await phiRes.json() : null;
    
    return {
      status,
      phi,
      timestamp: new Date().toISOString()
    };
  } catch (err) {
    throw new Error(`ain_panel_load_failed:${err.message}`);
  }
}

export function renderAINMetrics(data) {
  if (!data) {
    return '<div class="panel-empty">No AIN agent running</div>';
  }
  
  const { status, phi, timestamp } = data;
  
  let html = '<div class="ain-metrics">';
  
  // Agent Status
  html += '<div class="metric-group">';
  html += '<h4>Agent Status</h4>';
  html += `<div class="metric"><span class="label">State:</span> <span class="value">${status?.state || 'unknown'}</span></div>`;
  html += `<div class="metric"><span class="label">Total Drive:</span> <span class="value">${status?.total_drive?.toFixed(3) || '0.000'}</span></div>`;
  html += '</div>';
  
  // Φ (Consciousness)
  html += '<div class="metric-group">';
  html += '<h4>Consciousness (Φ)</h4>';
  html += `<div class="metric"><span class="label">Φ:</span> <span class="value highlight">${phi?.phi?.toFixed(4) || '0.0000'}</span></div>`;
  html += `<div class="metric"><span class="label">Integration:</span> <span class="value">${phi?.integration?.toFixed(3) || '0.000'}</span></div>`;
  html += `<div class="metric"><span class="label">Complexity:</span> <span class="value">${phi?.complexity?.toFixed(3) || '0.000'}</span></div>`;
  html += '</div>';
  
  // Drives
  if (status?.drives) {
    html += '<div class="metric-group">';
    html += '<h4>Drives</h4>';
    for (const [drive, value] of Object.entries(status.drives)) {
      html += `<div class="metric"><span class="label">${drive}:</span> <span class="value">${value.toFixed(3)}</span></div>`;
    }
    html += '</div>';
  }
  
  html += '</div>';
  
  return html;
}

export function renderAINDetails(data) {
  if (!data) return '';
  
  const { phi, status } = data;
  
  let html = '<div class="ain-details">';
  
  // Phi breakdown
  if (phi) {
    html += '<div class="detail-section">';
    html += '<h5>Φ Breakdown</h5>';
    html += `<div class="detail-item"><span>Integration:</span> <span>${phi.integration?.toFixed(4) || '—'}</span></div>`;
    html += `<div class="detail-item"><span>Complexity:</span> <span>${phi.complexity?.toFixed(4) || '—'}</span></div>`;
    html += `<div class="detail-item"><span>Mutual Info:</span> <span>${phi.mutual_info?.toFixed(4) || '—'}</span></div>`;
    html += `<div class="detail-item"><span>Irreducibility:</span> <span>${phi.irreducibility?.toFixed(4) || '—'}</span></div>`;
    html += '</div>';
  }
  
  // Reservoir state
  if (status?.reservoir_state) {
    html += '<div class="detail-section">';
    html += '<h5>Reservoir State</h5>';
    html += `<div class="detail-item"><span>Echo Strength:</span> <span>${status.reservoir_state.echo_strength?.toFixed(4) || '—'}</span></div>`;
    html += `<div class="detail-item"><span>State Norm:</span> <span>${status.reservoir_state.state_norm?.toFixed(4) || '—'}</span></div>`;
    html += '</div>';
  }
  
  html += '</div>';
  
  return html;
}
