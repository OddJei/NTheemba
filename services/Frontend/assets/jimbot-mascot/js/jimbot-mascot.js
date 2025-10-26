/*!
 * NTheemba Mascot Engine
 * Lightweight, framework-agnostic.
 */
(function () {
  class NTheembaMascot {
    /**
     * @param {HTMLElement} el - container with <img> or inline SVG
     * @param {Object} opts
     */
    constructor(el, opts = {}) {
      if (!el) throw new Error('NTheembaMascot: element not found');
      this.el = el;
      this.target = el.querySelector('img, svg') || el;
      this.opts = Object.assign({
        idleAfterMs: 12000,
        slideInOnMount: true,
        mobileBreakpoint: 640,
        debug: false
      }, opts);

      this._idleTimer = null;
      this._boundActivity = this._onActivity.bind(this);

      this._mount();
    }

    _log(...args) { if (this.opts.debug) console.log('[NTheemba]', ...args); }

    _mount() {
      // Slide in on mount (mobile-first)
      if (this.opts.slideInOnMount && this._isMobile()) {
        this._addAnim('animate-slide-in-up');
      }
      // Start idle loop
      this._attachActivityListeners();
      this._scheduleIdle();
      this._log('mounted');
    }

    destroy() {
      this._detachActivityListeners();
      this._clearIdle();
      this.el = null; this.target = null;
    }

    play(name) {
      if (!this.target) return;
      const cls = this._animClass(name);
      if (!cls) return;
      // Remove any previous animation class to retrigger
      this.target.classList.remove('animate-wiggle','animate-wave','animate-slide-in-up');
      void this.target.offsetWidth; // reflow to reset animation
      this._addAnim(cls);
      this._dispatch('NTheemba:played', { name });
      this._scheduleIdle(); // reset idle timer after an explicit play
    }

    say(text, timeoutMs = 3000) {
      // Create/update bubble
      let bubble = this.el.querySelector('.jb-bubble');
      if (!bubble) {
        bubble = document.createElement('div');
        bubble.className = 'jb-bubble';
        bubble.setAttribute('role', 'status');
        bubble.setAttribute('aria-live', 'polite');
        this.el.style.position = this.el.style.position || 'relative';
        this.el.appendChild(bubble);
      }
      bubble.textContent = text;
      // Auto-hide
      clearTimeout(this._bubbleTimer);
      this._bubbleTimer = setTimeout(() => {
        bubble.remove();
      }, timeoutMs);
    }

    _animClass(name) {
      switch (name) {
        case 'wiggle': return 'animate-wiggle';
        case 'wave': return 'animate-wave';
        case 'slide-in': return 'animate-slide-in-up';
        default: return null;
      }
    }

    _addAnim(cls) {
      this.target.classList.add(cls);
      const onEnd = () => {
        this.target.classList.remove(cls);
        this.target.removeEventListener('animationend', onEnd);
      };
      this.target.addEventListener('animationend', onEnd, { once: true });
    }

    _isMobile() {
      return window.innerWidth < this.opts.mobileBreakpoint;
    }

    _scheduleIdle() {
      this._clearIdle();
      this._idleTimer = setTimeout(() => {
        this.play('wiggle');
      }, this.opts.idleAfterMs);
    }

    _clearIdle() {
      if (this._idleTimer) clearTimeout(this._idleTimer);
      this._idleTimer = null;
    }

    _onActivity() {
      this._scheduleIdle();
    }

    _attachActivityListeners() {
      ['pointermove','keydown','touchstart','scroll'].forEach(ev =>
        window.addEventListener(ev, this._boundActivity, { passive: true })
      );
    }
    _detachActivityListeners() {
      ['pointermove','keydown','touchstart','scroll'].forEach(ev =>
        window.removeEventListener(ev, this._boundActivity)
      );
    }

    _dispatch(name, detail) {
      this.el.dispatchEvent(new CustomEvent(name, { detail }));
    }
  }

  // Export globally
  window.NTheembaMascot = NTheembaMascot;
})();

