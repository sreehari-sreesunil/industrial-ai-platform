/**
 * @typedef {Object} Organization
 * @property {number|string} id
 * @property {string} name
 */

/**
 * Creates a normalized Organization object
 * @param {Object} raw
 * @returns {Organization}
 */
export function createOrganization(raw = {}) {
  return {
    id: raw.id || '',
    name: raw.name || '',
  };
}
