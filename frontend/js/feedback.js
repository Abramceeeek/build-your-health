const FeedbackModule = (() => {
  let _currentPage = '';

  function open(page) {
    _currentPage = page || document.querySelector('.page.active')?.id || '';
    _renderPanel();
    document.getElementById('feedbackPanel')?.classList.add('active');
  }

  function close() {
    document.getElementById('feedbackPanel')?.classList.remove('active');
  }

  async function submit() {
    const category = document.querySelector('#feedbackPanel .fb-chip.selected')?.dataset.val || 'other';
    const rating = parseInt(document.querySelector('#feedbackPanel .fb-star.active:last-of-type')?.dataset.val || '0');
    const message = document.getElementById('feedbackMessage')?.value?.trim();
    const btn = document.getElementById('feedbackSubmitBtn');

    if (!message) {
      showToast('Write something first', 'error');
      return;
    }

    btn.disabled = true;
    btn.textContent = 'Sending...';

    try {
      await api('/api/feedback', {
        method: 'POST',
        body: JSON.stringify({ category, rating: rating || null, message, page: _currentPage }),
      });
      showToast('Feedback sent. Thank you.');
      haptic('success');
      close();
    } catch (e) {
      showToast(e.message || 'Failed to send', 'error');
    } finally {
      btn.disabled = false;
      btn.textContent = 'Send';
    }
  }

  function _renderPanel() {
    let panel = document.getElementById('feedbackPanel');
    if (!panel) {
      panel = document.createElement('div');
      panel.id = 'feedbackPanel';
      panel.className = 'wearable-slide-panel';
      document.body.appendChild(panel);
      _injectStyles();
    }

    panel.innerHTML = `
      <div class="wearable-panel-inner">
        <div class="wearable-panel-header">
          <h3>Send Feedback</h3>
          <button class="wearable-close" id="feedbackCloseBtn">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>

        <div class="fb-section">
          <div class="fb-label">Category</div>
          <div class="fb-chips">
            <span class="fb-chip selected" data-val="idea">Idea</span>
            <span class="fb-chip" data-val="bug">Bug</span>
            <span class="fb-chip" data-val="praise">Praise</span>
            <span class="fb-chip" data-val="other">Other</span>
          </div>
        </div>

        <div class="fb-section">
          <div class="fb-label">Rating (optional)</div>
          <div class="fb-stars">
            <span class="fb-star" data-val="1">★</span>
            <span class="fb-star" data-val="2">★</span>
            <span class="fb-star" data-val="3">★</span>
            <span class="fb-star" data-val="4">★</span>
            <span class="fb-star" data-val="5">★</span>
          </div>
        </div>

        <div class="fb-section">
          <div class="fb-label">Message</div>
          <textarea id="feedbackMessage" class="fb-textarea" placeholder="What's on your mind?" maxlength="1000" rows="4"></textarea>
        </div>

        <button class="wearable-save-btn" id="feedbackSubmitBtn">Send</button>
      </div>
    `;

    panel.querySelector('#feedbackCloseBtn').addEventListener('click', close);
    panel.querySelector('#feedbackSubmitBtn').addEventListener('click', submit);

    panel.querySelectorAll('.fb-chip').forEach(chip => {
      chip.addEventListener('click', () => {
        panel.querySelectorAll('.fb-chip').forEach(c => c.classList.remove('selected'));
        chip.classList.add('selected');
      });
    });

    panel.querySelectorAll('.fb-star').forEach(star => {
      star.addEventListener('click', () => {
        const val = parseInt(star.dataset.val);
        panel.querySelectorAll('.fb-star').forEach(s => {
          s.classList.toggle('active', parseInt(s.dataset.val) <= val);
        });
      });
    });
  }

  function _injectStyles() {
    if (document.querySelector('#feedbackStyles')) return;
    const s = document.createElement('style');
    s.id = 'feedbackStyles';
    s.textContent = `
      .fb-section { margin-bottom: 18px; }
      .fb-label { font-size: 0.8rem; color: var(--text-secondary, #888); margin-bottom: 8px; }
      .fb-chips { display: flex; gap: 8px; flex-wrap: wrap; }
      .fb-chip {
        padding: 6px 14px;
        border-radius: 20px;
        border: 1px solid var(--border, rgba(255,255,255,0.1));
        font-size: 0.83rem;
        cursor: pointer;
        color: var(--text-secondary, #aaa);
        transition: all 0.15s;
      }
      .fb-chip.selected {
        background: var(--primary, #4a9eff);
        border-color: var(--primary, #4a9eff);
        color: #fff;
      }
      .fb-stars { display: flex; gap: 6px; }
      .fb-star {
        font-size: 1.6rem;
        color: var(--border, rgba(255,255,255,0.15));
        cursor: pointer;
        transition: color 0.12s;
        line-height: 1;
      }
      .fb-star.active { color: #ffc107; }
      .fb-textarea {
        width: 100%;
        background: var(--bg-tertiary, #1a1a2e);
        border: 1px solid var(--border, rgba(255,255,255,0.1));
        border-radius: 10px;
        color: var(--text-primary, #fff);
        padding: 12px;
        font-size: 0.9rem;
        font-family: inherit;
        resize: none;
        box-sizing: border-box;
        outline: none;
      }
      .fb-textarea:focus { border-color: var(--primary, #4a9eff); }
    `;
    document.head.appendChild(s);
  }

  return { open, close };
})();
