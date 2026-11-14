// TEMPORARY, CI only: finds out why a request of the Assign step never reaches the API on the
// GitHub runner (FEAT-007, AC-FEAT-005-13). Remove once the cause is fixed.
//
// The API process registers a C-level SIGUSR1 handler (via sitecustomize) that writes the stack of
// every thread. Every 3 seconds a watcher asks for that dump and lists the sockets of both ports
// (state 01 is established, 06 time-wait, 0A listening); both go into the folder that the workflow
// already uploads when a run fails.
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const work = path.join(os.tmpdir(), 'routepilot-e2e');
export const diagnosticsDir = path.join(work, 'diag');

export function prepareDiagnostics(): void {
  fs.mkdirSync(diagnosticsDir, { recursive: true });
  fs.writeFileSync(
    path.join(diagnosticsDir, 'sitecustomize.py'),
    [
      'import faulthandler, os, signal',
      `_f = open(${JSON.stringify(path.join(diagnosticsDir, 'stacks.log'))}, "a", buffering=1)`,
      'faulthandler.register(signal.SIGUSR1, file=_f, all_threads=True, chain=False)',
      '',
    ].join('\n'),
  );
}

export default function globalSetup(): void {
  if (!process.env.CI) return;
  const results = path.join(work, 'results');
  fs.mkdirSync(results, { recursive: true });
  const script = [
    'while kill -0 "$1" 2>/dev/null; do',
    '  { date -u +%T; awk \'$2 ~ /:(1F4A|0BC2)$/ || $3 ~ /:(1F4A|0BC2)$/ {print $2, $3, $4}\' /proc/net/tcp /proc/net/tcp6 2>/dev/null | sort | uniq -c; } >> "$2/sockets.log"',
    '  for pid in $(pgrep -f "\\.venv/bin/python.* [r]outepilot.main:app"); do',
    '    { echo "=== $(date -u +%T) pid $pid"; } >> "$3/stacks.log"; kill -USR1 "$pid" 2>/dev/null',
    '  done',
    '  sleep 3',
    '  cp "$3/stacks.log" "$2/stacks.log" 2>/dev/null',
    'done',
  ].join('\n');
  spawn('bash', ['-c', script, 'watcher', String(process.pid), results, diagnosticsDir], {
    detached: true,
    stdio: 'ignore',
  }).unref();
}
