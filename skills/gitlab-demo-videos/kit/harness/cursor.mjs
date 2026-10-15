// Node-side cursor driver: smooth, eased mouse movement using real Playwright mouse events
// (so hover states, tooltips and menus react exactly like a user would trigger them).
export class Cursor {
  constructor(page, { x = 1400, y = 640 } = {}) {
    this.page = page;
    this.x = x;
    this.y = y;
  }

  static ease(t) {
    return t < 0.5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2; // easeInOutCubic
  }

  async moveToPoint(x, y, { duration } = {}) {
    const dist = Math.hypot(x - this.x, y - this.y);
    const ms = duration ?? Math.min(1100, Math.max(350, 280 + dist * 0.55));
    const steps = Math.max(8, Math.round(ms / 16));
    const sx = this.x;
    const sy = this.y;
    // Slight arc so movement looks hand-driven rather than robotic.
    const nx = -(y - sy) / (dist || 1);
    const ny = (x - sx) / (dist || 1);
    const bow = Math.min(40, dist * 0.08);
    const t0 = Date.now();
    for (let i = 1; i <= steps; i += 1) {
      const t = Cursor.ease(i / steps);
      const arc = Math.sin(Math.PI * t) * bow;
      await this.page.mouse.move(sx + (x - sx) * t + nx * arc, sy + (y - sy) * t + ny * arc);
      const target = t0 + (ms * i) / steps;
      const wait = target - Date.now();
      if (wait > 0) await this.page.waitForTimeout(wait);
    }
    this.x = x;
    this.y = y;
  }

  async point(locator, { dx = 0.5, dy = 0.5, ox = 0, oy = 0 } = {}) {
    await locator.waitFor({ state: 'visible' });
    const b = await locator.boundingBox();
    return { x: b.x + b.width * dx + ox, y: b.y + b.height * dy + oy };
  }

  async moveTo(locator, opts = {}) {
    const p = await this.point(locator, opts);
    await this.moveToPoint(p.x, p.y, opts);
    return p;
  }

  async click(locator, opts = {}) {
    await this.moveTo(locator, opts);
    await this.page.waitForTimeout(opts.settle ?? 140);
    await this.page.mouse.down();
    await this.page.waitForTimeout(90);
    await this.page.mouse.up();
  }

  async clickPoint(x, y, opts = {}) {
    await this.moveToPoint(x, y, opts);
    await this.page.waitForTimeout(opts.settle ?? 140);
    await this.page.mouse.down();
    await this.page.waitForTimeout(90);
    await this.page.mouse.up();
  }

  // Re-dispatch the current position (e.g. right after a navigation).
  async sync() {
    await this.page.mouse.move(this.x, this.y);
  }
}
