//@ts-check

import { logger } from '../../shared/utils/logger.js';

/**
 * Extract LinkedIn cookies and CSRF token from the browser cookie store.
 * Requires host permissions for https://www.linkedin.com/* in the extension manifest.
 * @returns {Promise<{ cookies: Record<string,string>, csrfToken: string|null }>}
 */
export async function getLinkedInCookiesAndCsrf() {
  /** @type {Record<string,string>} */
  const cookieMap = {};
  try {
    const cookies = await chrome.cookies.getAll({ url: 'https://www.linkedin.com' });
    for (const c of cookies) {
      if (!c.name || c.value == null) continue;
      cookieMap[c.name] = c.value;
    }
    const jsession = cookieMap['JSESSIONID'] || cookieMap['jsessionid'] || null;
    const csrfToken = jsession ? jsession.replace(/^"|"$/g, '') : null;
    logger.info(`[COOKIES] Extracted ${Object.keys(cookieMap).length} LinkedIn cookies; csrfToken present: ${!!csrfToken}`, 'linkedin-cookies.util');
    return { cookies: cookieMap, csrfToken };
  } catch (err) {
    logger.error(`[COOKIES] Failed to read LinkedIn cookies: ${err?.message || err}`, 'linkedin-cookies.util');
    return { cookies: cookieMap, csrfToken: null };
  }
}


