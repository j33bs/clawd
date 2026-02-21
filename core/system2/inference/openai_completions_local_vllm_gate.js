'use strict';

function isLocalVllmTarget(baseUrl) {
  const value = String(baseUrl || '').trim().toLowerCase();
  if (!value) return false;
  if (value.includes('127.0.0.1:8001') || value.includes('localhost:8001') || value.includes('[::1]:8001')) {
    return true;
  }
  return value.includes('/vllm') || value.includes('vllm');
}

function isLocalVllmToolCallEnabled(env) {
  const value = String((env && env.OPENCLAW_VLLM_TOOLCALL) || process.env.OPENCLAW_VLLM_TOOLCALL || '0')
    .trim()
    .toLowerCase();
  return value === '1' || value === 'true' || value === 'yes' || value === 'on';
}

function applyLocalVllmToolPayloadGate(baseUrl, payload, env) {
  const next = payload && typeof payload === 'object' ? { ...payload } : {};
  if (!isLocalVllmTarget(baseUrl)) return next;
  if (isLocalVllmToolCallEnabled(env)) return next;
  delete next.tools;
  delete next.tool_choice;
  return next;
}

module.exports = {
  isLocalVllmTarget,
  isLocalVllmToolCallEnabled,
  applyLocalVllmToolPayloadGate
};
