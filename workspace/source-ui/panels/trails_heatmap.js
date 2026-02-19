// Minimal trails heatmap panel data loader (D3-ready payload)
export async function loadTrailsHeatmap(fetchFn = fetch) {
  const resp = await fetchFn('/api/trails/heatmap');
  if (!resp.ok) {
    throw new Error(`heatmap_request_failed:${resp.status}`);
  }
  return resp.json();
}
