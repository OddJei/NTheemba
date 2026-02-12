/*!
 * NTheemba Mascot Alpine glue
 * Exposes $store.mascot with play() and say()
 */
(function () {
  const init = () => {
    const el = document.querySelector('#mascot');
    if (!el) return;

    // Create engine instance
    const mascot = new window.NTheembaMascot(el, {
      idleAfterMs: 12000,
      slideInOnMount: true,
      mobileBreakpoint: 640,
      debug: false
    });

    // Expose globally and to Alpine store if present
    window.ntheembaMascot = mascot;

    if (window.Alpine && typeof window.Alpine.store === 'function') {
      window.Alpine.store('mascot', {
        play: (name) => mascot.play(name),
        say: (text, ms) => mascot.say(text, ms)
      });
    }

    // Example: wave when mascot enters viewport on desktop
    if (window.matchMedia('(min-width: 640px)').matches) {
      // small delay for a friendly entrance
      setTimeout(() => mascot.play('wave'), 800);
    }
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();

