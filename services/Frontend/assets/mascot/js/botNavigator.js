// botNavigator.js
document.addEventListener('alpine:init', () => {
  // 💬 Greeting Tip
  Alpine.data('botGreeting', () => ({
    open: false,
    toggle() {
      this.open = !this.open;
    }
  }));

  // 🧠 Explainer Bubble
  Alpine.data('storefrontTip', () => ({
    explain: false,
    toggleExplain() {
      this.explain = !this.explain;
    }
  }));

  // 🤝 Promoter Reveal
  Alpine.data('promoterReveal', () => ({
    reveal: false,
    toggleReveal() {
      this.reveal = !this.reveal;
    }
  }));
});
