/**
 * @typedef {Object} NestedOrganization
 * @property {number|string} id
 * @property {string} name
 *
 * @typedef {Object} Facility
 * @property {number|string} id
 * @property {string} name
 * @property {NestedOrganization} organization
 */

/**
 * Creates a normalized Facility object
 * @param {Object} raw
 * @returns {Facility}
 */
export function createFacility(raw = {}) {
  return {
    id: raw.id || '',
    name: raw.name || '',
    organization: {
      id: raw.organization?.id || '',
      name: raw.organization?.name || '',
    },
  };
}
