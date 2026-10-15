// The GitLab version the kit is pinned to, for display text in pages.mjs and scenario.mjs (Node side only).
// Read from gl-src/VERSION once setup has checked GitLab out (e.g. "19.4.1-ee", "19.6.0-pre"), otherwise from
// the tag in gl-src.pin. Change the version with `scripts/setup.sh --gitlab-tag <tag>` (references/setup.md).
//
//   import { GITLAB_VERSION } from '../../src/shell/gitlab_version.mjs';
//   await caption(`GitLab ${GITLAB_VERSION} on GitLab.com`);   // "GitLab 19.4 on GitLab.com"
import fs from 'node:fs';

const ROOT = new URL('../../../', import.meta.url); // the work dir: app/, gl-src/, gl-src.pin
const read = (rel) => {
  try {
    return fs.readFileSync(new URL(rel, ROOT), 'utf8');
  } catch {
    return '';
  }
};

/** Tag or branch from gl-src.pin, e.g. "v19.4.1-ee". */
export const GITLAB_TAG = ((read('gl-src.pin').match(/^tag=(.*)$/m) || [])[1] || '').trim();

const raw = read('gl-src/VERSION').trim() || GITLAB_TAG;
const m = raw.match(/(\d+)\.(\d+)/);

/** "major.minor" for display, e.g. "19.4". Falls back to the raw tag (e.g. "master") when it has no version number. */
export const GITLAB_VERSION = m ? `${m[1]}.${m[2]}` : raw || 'unknown';
