#!/usr/bin/env node
const { spawn } = require('child_process');
const path = require('path');

const args = process.argv.slice(2);

// Prefer python3, fallback to python
const candidates = ['python3', 'python'];

function run(py) {
  const pkgRoot = path.resolve(__dirname, '..');
  const env = { ...process.env };
  // Prepend package root to PYTHONPATH so python can import the bundled skuld module
  const existing = env.PYTHONPATH || '';
  env.PYTHONPATH = existing ? `${pkgRoot}${path.delimiter}${existing}` : pkgRoot;
  const p = spawn(py, ['-m', 'skuld.cli', ...args], { stdio: 'inherit', env });
  p.on('exit', code => process.exit(code));
  p.on('error', err => {
    if (py === 'python3' && err.code === 'ENOENT') {
      run('python');
    } else {
      console.error(`[skuld] failed to spawn ${py}:`, err.message);
      process.exit(1);
    }
  });
}

run(candidates[0]);
