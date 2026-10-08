'use strict';

// @next/eslint-plugin-next 16.3.8 uses only globSync(pattern, {onlyDirectories:true}).
// Keep this intentionally narrow: new upstream API usage must fail explicitly.
const fs = require('node:fs');

function globSync(pattern, options = {}) {
  if (options.onlyDirectories !== true || Object.keys(options).some(key => key !== 'onlyDirectories')) {
    throw new TypeError('Unsupported directory-glob options; review the Next.js plugin integration');
  }
  if (typeof pattern !== 'string' || pattern.length > 4096 || pattern.includes('\0')) {
    throw new TypeError('Invalid directory-glob pattern');
  }
  // Bound recursive brace parsing even for owner-supplied eslint settings.
  let depth = 0;
  for (const character of pattern) {
    if (character === '{' && ++depth > 16) throw new RangeError('Directory-glob nesting exceeds 16');
    if (character === '}' && --depth < 0) throw new TypeError('Unbalanced directory-glob pattern');
  }
  if (depth !== 0) throw new TypeError('Unbalanced directory-glob pattern');
  return [...fs.globSync(pattern)].filter(path => {
    try { return fs.statSync(path).isDirectory(); } catch { return false; }
  });
}

module.exports = {globSync};
