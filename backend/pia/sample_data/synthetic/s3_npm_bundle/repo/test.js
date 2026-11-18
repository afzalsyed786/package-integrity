const assert = require('assert');
const leftTrim = require('./src/index.js');
assert.strictEqual(leftTrim('   hi'), 'hi');
