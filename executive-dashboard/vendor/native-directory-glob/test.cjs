'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {globSync} = require('./index.cjs');
const root = fs.mkdtempSync(path.join(os.tmpdir(), 'directory-glob-test-'));
try {
  for (const name of ['app-one', 'app-two', 'other']) fs.mkdirSync(path.join(root, name));
  fs.writeFileSync(path.join(root, 'app-file'), 'test');
  const options = {onlyDirectories:true};
  assert.deepEqual(globSync(path.join(root, 'app-*'), options).sort(),
    [path.join(root, 'app-one'), path.join(root, 'app-two')]);
  assert.deepEqual(globSync(path.join(root, '{app-one,other}'), options).sort(),
    [path.join(root, 'app-one'), path.join(root, 'other')].sort());
  assert.deepEqual(globSync(path.join(root, 'app-one'), options), [path.join(root, 'app-one')]);
  assert.deepEqual(globSync(path.join(root, 'absent-*'), options), []);
  assert.throws(() => globSync('{'.repeat(10000), options));
  assert.throws(() => globSync('{'.repeat(17)+'x'+'}'.repeat(17), options), RangeError);
  assert.throws(() => globSync('{a,b}'.repeat(9), options), RangeError);
  assert.throws(() => globSync('{1..100000000}', options), RangeError);
  assert.throws(() => globSync('*', {onlyDirectories:true, followSymbolicLinks:true}));
  // Exercise the real installed plugin path: no-html-link-for-pages uses getRootDirs.
  const {getRootDirs} = require('@next/eslint-plugin-next/dist/utils/get-root-dirs');
  assert.deepEqual(getRootDirs({cwd:root, settings:{next:{rootDir:path.join(root, 'app-*')}}}).sort(),
    [path.join(root, 'app-one'), path.join(root, 'app-two')]);
  console.log('Native directory-glob contract and pinned Next.js integration passed');
} finally { fs.rmSync(root, {recursive:true, force:true}); }
