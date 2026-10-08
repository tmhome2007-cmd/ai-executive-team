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
  // Cap nesting and Cartesian expansion before handing patterns to Node.
  // Repeated sibling braces can explode without nesting.
  if (/\{[^{}]*\.\.[^{}]*\}/.test(pattern)) throw new RangeError('Directory-glob brace ranges are unsupported');
  const groups = [{sum:0, product:1}];
  let depth = 0;
  for (const character of pattern) {
    if (character === '{') {
      if (++depth > 16) throw new RangeError('Directory-glob nesting exceeds 16');
      groups.push({sum:0, product:1});
    } else if (character === ',' && depth > 0) {
      const group = groups.at(-1);
      group.sum += group.product;
      group.product = 1;
    } else if (character === '}') {
      if (--depth < 0) throw new TypeError('Unbalanced directory-glob pattern');
      const group = groups.pop();
      groups.at(-1).product *= group.sum + group.product;
    }
    const group = groups.at(-1);
    if (group.sum + group.product > 256) throw new RangeError('Directory-glob expansion exceeds 256');
  }
  if (depth !== 0) throw new TypeError('Unbalanced directory-glob pattern');
  return [...fs.globSync(pattern)].filter(path => {
    try { return fs.statSync(path).isDirectory(); } catch { return false; }
  });
}

module.exports = {globSync};
