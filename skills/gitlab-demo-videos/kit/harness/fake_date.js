// Injected into every page: shifts the clock so the demo always "happens" at a fixed
// instant while time keeps flowing (animations, timeago, etc. still work).
// __DEMO_OFFSET_MS__ is replaced by the recorder.
(() => {
  const OFFSET = __DEMO_OFFSET_MS__;
  const RealDate = Date;
  class DemoDate extends RealDate {
    constructor(...args) {
      if (args.length === 0) super(RealDate.now() + OFFSET);
      else super(...args);
    }
    static now() {
      return RealDate.now() + OFFSET;
    }
  }
  DemoDate.UTC = RealDate.UTC;
  DemoDate.parse = RealDate.parse;
  window.Date = DemoDate;
})();
