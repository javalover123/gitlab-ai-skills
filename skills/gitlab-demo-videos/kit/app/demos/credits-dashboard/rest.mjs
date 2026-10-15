// REST responses the real shell/pages request (path -> JSON body). Served by harness/serve.mjs.
const event = (when, html) => `<li class="event-item gl-border-b-0 gl-pb-3 gl-list-none project-activity-item">
<div class="event-item-timestamp gl-text-sm"><time class="js-timeago" datetime="${when}">${when}</time></div>
<div class="event-title gl-flex"><div class="event-title-block gl-inline-block gl-mr-2">${html}</div></div></li>`;
const now = Date.now();
const iso = (h) => new Date(now - h * 3600e3).toISOString();
export default {
  '/users/arivera/activity': {
    html: [
      event(iso(1), '<span class="event-type opened">Opened</span> <span class="event-target-type">merge request</span> <a class="event-target-link" href="#">!482</a> <span class="event-target-title">"Add retry with backoff to webhook dispatcher"</span> <span class="event-scope">at <a href="#">Acme Corp / Platform / api</a></span>'),
      event(iso(4), '<span class="event-type pushed">Pushed to branch</span> <a href="#">webhook-retries</a> <span class="event-scope">at <a href="#">Acme Corp / Platform / api</a></span>'),
      event(iso(22), '<span class="event-type commented">Commented on</span> <span class="event-target-type">issue</span> <a class="event-target-link" href="#">#1287</a> <span class="event-scope">at <a href="#">Acme Corp / Storefront / web</a></span>'),
    ].join('\n'),
  },
};
