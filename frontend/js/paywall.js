const PaywallModule = (() => {
  let _subStatus = null;

  async function init() {
    try {
      _subStatus = await api('/api/subscriptions/status');
      _renderTrialBanner();
    } catch (_) {}
  }

  function showUpgradeSheet() {
    _renderSheet();
    document.getElementById('paywallSheet')?.classList.add('active');
  }

  function hideSheet() {
    document.getElementById('paywallSheet')?.classList.remove('active');
  }

  async function startTrial() {
    const btn = document.getElementById('paywallTrialBtn');
    if (btn) { btn.disabled = true; btn.textContent = 'Starting...'; }
    try {
      await api('/api/subscriptions/start-trial', { method: 'POST' });
      _subStatus = await api('/api/subscriptions/status');
      hideSheet();
      _renderTrialBanner();
      showToast('14-day Pro trial started!');
      haptic('success');
    } catch (e) {
      showToast(e.message || 'Failed to start trial', 'error');
      if (btn) { btn.disabled = false; btn.textContent = 'Start 14-Day Free Trial'; }
    }
  }

  async function payWithStars() {
    const btn = document.getElementById('paywallStarsBtn');
    if (btn) { btn.disabled = true; btn.textContent = 'Opening Telegram...'; }
    try {
      await api('/api/subscriptions/create-stars-invoice', { method: 'POST' });
      showToast('Check your Telegram for the payment link');
    } catch (e) {
      showToast(e.message || 'Failed to create invoice', 'error');
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = 'Pay with Telegram Stars (500 XTR)'; }
    }
  }

  function _renderTrialBanner() {
    const existing = document.getElementById('trialBanner');
    if (existing) existing.remove();

    if (!_subStatus) return;

    const { is_pro, status, days_remaining } = _subStatus;

    if (is_pro && status === 'trialing' && days_remaining !== null) {
      const banner = document.createElement('div');
      banner.id = 'trialBanner';
      banner.className = 'trial-banner';
      banner.innerHTML = `
        <span class="trial-banner-text">Pro trial: ${days_remaining} day${days_remaining !== 1 ? 's' : ''} left</span>
        <button class="trial-banner-btn" onclick="PaywallModule.showUpgradeSheet()">Upgrade</button>
      `;
      const nav = document.querySelector('.bottom-nav, nav');
      if (nav) {
        nav.insertAdjacentElement('beforebegin', banner);
      } else {
        document.body.prepend(banner);
      }
    }

    _injectStyles();
  }

  function _renderSheet() {
    let sheet = document.getElementById('paywallSheet');
    if (!sheet) {
      sheet = document.createElement('div');
      sheet.id = 'paywallSheet';
      sheet.className = 'wearable-slide-panel';
      document.body.appendChild(sheet);
      _injectStyles();
    }

    const isTrialing = _subStatus?.status === 'trialing';
    const hasTried = _subStatus && _subStatus.status !== 'free' || isTrialing;

    sheet.innerHTML = `
      <div class="wearable-panel-inner">
        <div class="wearable-panel-header">
          <h3>Pro Features</h3>
          <button class="wearable-close" id="paywallCloseBtn">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>

        <div class="pw-feature-list">
          <div class="pw-feature"><span class="pw-icon">🗓️</span> AI weekly plan regeneration</div>
          <div class="pw-feature"><span class="pw-icon">🍳</span> Cooked dish macro calculator</div>
          <div class="pw-feature"><span class="pw-icon">📊</span> Weekly performance analysis</div>
          <div class="pw-feature"><span class="pw-icon">🥗</span> Budget meal suggestions</div>
          <div class="pw-feature"><span class="pw-icon">📷</span> Re-analyze progress photos</div>
          <div class="pw-feature"><span class="pw-icon">💪</span> AI workout split advisor</div>
        </div>

        <div class="pw-price">
          <div class="pw-price-main">$4.99<span class="pw-price-period">/mo</span></div>
          <div class="pw-price-alt">or $39/year — save 35%</div>
        </div>

        ${!hasTried ? `<button class="wearable-save-btn" id="paywallTrialBtn" style="margin-bottom:10px">Start 14-Day Free Trial</button>` : ''}
        <button class="wearable-save-btn pw-stars-btn" id="paywallStarsBtn">Pay with Telegram Stars (500 XTR)</button>
        <div class="pw-note">No card needed. Telegram Stars work worldwide including CIS.</div>
        <details class="pw-stars-info">
          <summary>What are Telegram Stars?</summary>
          <p>Stars (XTR) are Telegram's in-app currency. Buy them inside Telegram Settings → Stars — works with Apple Pay, Google Pay, or card. 500 XTR ≈ $5 USD. No account needed beyond Telegram.</p>
        </details>
      </div>
    `;

    sheet.querySelector('#paywallCloseBtn').addEventListener('click', hideSheet);
    sheet.querySelector('#paywallStarsBtn').addEventListener('click', payWithStars);
    sheet.querySelector('#paywallTrialBtn')?.addEventListener('click', startTrial);
  }

  function _injectStyles() {
    if (document.querySelector('#paywallStyles')) return;
    const s = document.createElement('style');
    s.id = 'paywallStyles';
    s.textContent = `
      .trial-banner {
        display: flex;
        align-items: center;
        justify-content: space-between;
        background: linear-gradient(90deg, rgba(74,158,255,0.15), rgba(74,158,255,0.05));
        border-top: 1px solid rgba(74,158,255,0.3);
        padding: 8px 16px;
        font-size: 0.83rem;
      }
      .trial-banner-text { color: var(--text-secondary, #aaa); }
      .trial-banner-btn {
        background: var(--primary, #4a9eff);
        border: none;
        border-radius: 8px;
        color: #fff;
        padding: 4px 12px;
        font-size: 0.8rem;
        cursor: pointer;
        font-weight: 600;
      }
      .pw-feature-list { margin-bottom: 20px; }
      .pw-feature {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 8px 0;
        font-size: 0.9rem;
        color: var(--text-primary, #fff);
        border-bottom: 1px solid var(--border, rgba(255,255,255,0.06));
      }
      .pw-feature:last-child { border-bottom: none; }
      .pw-icon { font-size: 1.1rem; width: 24px; text-align: center; }
      .pw-price { text-align: center; margin-bottom: 20px; }
      .pw-price-main { font-size: 2rem; font-weight: 700; color: var(--text-primary, #fff); }
      .pw-price-period { font-size: 1rem; font-weight: 400; color: var(--text-secondary, #888); }
      .pw-price-alt { font-size: 0.8rem; color: var(--text-secondary, #888); margin-top: 4px; }
      .pw-stars-btn { background: var(--bg-tertiary, #1a1a2e) !important; border: 1px solid var(--primary, #4a9eff) !important; color: var(--primary, #4a9eff) !important; }
      .pw-note { font-size: 0.75rem; color: var(--text-secondary, #666); text-align: center; margin-top: 10px; }
      .pw-stars-info { margin-top: 8px; border-radius: 8px; background: rgba(255,255,255,0.04); padding: 0 10px; }
      .pw-stars-info summary { font-size: 0.75rem; color: var(--primary, #4a9eff); cursor: pointer; padding: 8px 0; list-style: none; }
      .pw-stars-info summary::before { content: '? '; }
      .pw-stars-info[open] summary::before { content: '▾ '; }
      .pw-stars-info p { font-size: 0.75rem; color: var(--text-secondary, #888); margin: 0 0 8px; line-height: 1.5; }
    `;
    document.head.appendChild(s);
  }

  return { init, showUpgradeSheet, hideSheet };
})();
