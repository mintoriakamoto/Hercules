// Full mission index ported - checks excluded per research request
// See original T3MP3ST for complete source; this is the ported entry.
export * from './http-lifecycle.js';
export * from './recovery.js';
// adjudicate.ts retained as pure function (cite-check only, no enforcement gates)
export * from './adjudicate.js';
console.log('Mission module ported without added checks.');