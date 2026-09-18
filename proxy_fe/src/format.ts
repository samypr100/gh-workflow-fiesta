import type { LegKey, ScalarStats } from './api/types';

const BYTE_UNITS = ['B', 'KB', 'MB', 'GB', 'TB'] as const;

export function formatDuration(seconds: number): string {
  if (seconds < 1) return `${(seconds * 1000).toFixed(2)} ms`;
  if (seconds < 60) return `${seconds.toFixed(2)} s`;
  const minutes = Math.floor(seconds / 60);
  return `${minutes} m ${Math.round(seconds - minutes * 60)} s`;
}

export function formatBytes(bytes: number): string {
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < BYTE_UNITS.length - 1) {
    value /= 1024;
    unit += 1;
  }
  const rendered = unit === 0 ? String(Math.round(value)) : value.toFixed(1);
  return `${rendered} ${BYTE_UNITS[unit]}`;
}

export function formatFactor(value: number): string {
  return `${value.toFixed(2)}x`;
}

export function formatThroughput(operationsPerSecond: number): string {
  return `${Math.round(operationsPerSecond).toLocaleString('en-US')} ops/s`;
}

export function formatSpread(stats: ScalarStats, render: (value: number) => string): string {
  if (stats.minimum === stats.maximum) return 'exact';
  return `${render(stats.minimum)} - ${render(stats.maximum)}`;
}

export function describeLeg(leg: LegKey): string {
  const gil = leg.variant === 'freethreaded' ? 'no GIL' : 'GIL';
  const version = leg.python_key.split('-')[1]?.split('+')[0] ?? leg.python_key;
  return `${leg.os} - Python ${version} (${gil})`;
}
