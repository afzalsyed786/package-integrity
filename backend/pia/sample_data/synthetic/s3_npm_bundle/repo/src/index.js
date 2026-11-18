'use strict';

/**
 * Remove leading whitespace (synthetic PIA demo library).
 * @param {string} input
 * @returns {string}
 */
function leftTrim(input) {
  if (typeof input !== 'string') {
    throw new TypeError('expected a string');
  }
  return input.replace(/^\s+/, '');
}

module.exports = leftTrim;
module.exports.default = leftTrim;
