/* =========================================================================
   Groww MF Facts — front-end interaction
   Plain JS, no frameworks. Full keyboard nav, reduced-motion respect.
   ========================================================================= */
(function() {
  'use strict';

  // ---- Schemes for autocomplete (7 Groww MF schemes) ----
  const SCHEMES = [
    { name: 'Groww Large Cap Fund',         category: 'Equity · Large Cap' },
    { name: 'Groww Value Fund',             category: 'Equity · Value' },
    { name: 'Groww Small Cap Fund',         category: 'Equity · Small Cap' },
    { name: 'Groww ELSS Tax Saver Fund',    category: 'Equity · ELSS (80C)' },
    { name: 'Groww Nifty 50 Index Fund',    category: 'Passive · Index' },
    { name: 'Groww Liquid Fund',            category: 'Debt · Liquid' },
    { name: 'Groww Overnight Fund',         category: 'Debt · Overnight' },
  ];

  // ---- DOM refs ----
  const form = document.getElementById('ask-form');
  const input = document.getElementById('ask-input');
  const submit = document.getElementById('ask-submit');
  const turns = document.getElementById('turns');
  const autocomplete = document.getElementById('autocomplete');
  const intro = document.getElementById('intro');
  const menu = document.getElementById('menu');

  let acItems = [];        // current autocomplete items
  let acActiveIdx = -1;    // active index in autocomplete

  // ---- Helpers ----
  function escapeHtml(s) {
    return (s || '').replace(/[&<>"']/g, ch => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }[ch]));
  }

  // Extract numeric/data values from answer text and wrap them in <span class="num">
  // Targets: percentages, ₹ amounts, "3 years", "Nil", "Very High Risk"
  function highlightData(text) {
    let t = escapeHtml(text);
    // Percentages: 2.42%, 1%, 0.005%
    t = t.replace(/(\d+(?:\.\d+)?%)/g, '<span class="num">$1</span>');
    // Rupee amounts: ₹500, ₹10,000
    t = t.replace(/(₹[\d,]+)/g, '<span class="num">$1</span>');
    // Year/duration: 3 years, 7 days, 365 days
    t = t.replace(/(\d+\s+(?:year|day|month|week)s?)/gi, '<span class="num">$1</span>');
    // Nil / Very High Risk / High Risk etc as risk-chip
    t = t.replace(/\b(Nil)\b/g, '<span class="risk-chip">$1</span>');
    t = t.replace(/\b(Very High Risk|High Risk|Moderately High Risk|Moderate Risk|Low to Moderate Risk|Low Risk)\b/g,
      '<span class="risk-chip">$1</span>');
    return t;
  }

  // Format an issuer name from a URL
  function issuerFromUrl(url) {
    if (!url) return 'Official source';
    if (url.includes('growwmf.in')) return 'Groww Asset Management Ltd.';
    if (url.includes('groww.in')) return 'Groww (distributor page)';
    if (url.includes('investor.sebi.gov.in')) return 'SEBI Investor (sebi.gov.in)';
    if (url.includes('sebi.gov.in')) return 'Securities and Exchange Board of India';
    if (url.includes('amfiindia.com')) return 'Association of Mutual Funds in India';
    return 'Official source';
  }

  // Format document type from chunk title / URL
  function doctypeFromResult(r) {
    const t = (r.citation_title || '').toLowerCase();
    if (t.includes('scheme information document') || t.includes('sid')) return 'Scheme Information Document';
    if (t.includes('key information memorandum') || t.includes('kim')) return 'Key Information Memorandum';
    if (t.includes('factsheet') || t.includes('fact sheet')) return 'Monthly Factsheet';
    if (t.includes('faq')) return 'Regulatory FAQ';
    if (t.includes('riskometer')) return 'Regulatory Explainer · Riskometer';
    if (t.includes('exit load')) return 'Regulatory Explainer · Exit Load';
    if (t.includes('capital gains statement') || t.includes('statement')) return 'Help Article · Statements';
    if (t.includes('expense ratio') && t.includes('definition')) return 'Topic Explainer · Expense Ratio';
    if (t.includes('amc overview') || t.includes('amc')) return 'AMC Overview';
    if (t.includes('direct growth') || t.includes('regular growth')) return 'Scheme Page';
    return 'Official public source';
  }

  // Build a citation card HTML (the signature element)
  function citationCard(r) {
    if (!r || !r.citation_url) return '';
    const issuer = escapeHtml(issuerFromUrl(r.citation_url));
    const doctype = escapeHtml(doctypeFromResult(r));
    const asof = escapeHtml(r.last_updated || '—');
    const url = escapeHtml(r.citation_url);
    const urlDisplay = escapeHtml(r.citation_url.replace(/^https?:\/\//, '').slice(0, 80) + (r.citation_url.length > 80 ? '…' : ''));
    return `
      <div class="citation" role="note" aria-label="Source citation">
        <span class="citation__label">Source</span>
        <div class="citation__issuer">${issuer}</div>
        <div class="citation__doctype">${doctype}</div>
        <div class="citation__meta">
          <span>As of ${asof}</span>
        </div>
        <a class="citation__link" href="${url}" target="_blank" rel="noopener noreferrer">${urlDisplay}</a>
      </div>
    `;
  }

  // Build a boundary redirect card (no-advice)
  function boundaryCard(answer, citationUrl, citationTitle) {
    let html = `
      <div class="boundary" role="note">
        <span class="boundary__label">Outside scope</span>
        <div>${escapeHtml(answer)}</div>
      </div>
    `;
    if (citationUrl) {
      html += citationCard({ citation_url: citationUrl, citation_title: citationTitle, last_updated: new Date().toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }) });
    }
    return html;
  }

  // Build an unavailable card
  function unavailableCard(msg, hintLink) {
    return `
      <div class="unavailable" role="alert">
        <span class="unavailable__label">Couldn't verify</span>
        <div>${escapeHtml(msg)}</div>
        ${hintLink ? `<div class="unavailable__hint">Check the official AMC page: <a href="${escapeHtml(hintLink)}" target="_blank" rel="noopener noreferrer">growwmf.in/downloads</a></div>` : ''}
      </div>
    `;
  }

  // ---- Render a turn ----
  function renderTurn(question, result, isLoading = false) {
    const turn = document.createElement('article');
    turn.className = 'turn';

    const q = document.createElement('div');
    q.className = 'turn__question';
    q.textContent = question;
    turn.appendChild(q);

    if (isLoading) {
      const loading = document.createElement('div');
      loading.className = 'loading';
      loading.innerHTML = 'Checking the official source<span class="loading__dots">…</span>';
      turn.appendChild(loading);
    } else if (result) {
      turn.appendChild(renderResult(result));
    }

    turns.appendChild(turn);
    turn.scrollIntoView({ behavior: 'smooth', block: 'end' });
    return turn;
  }

  function renderResult(r) {
    const wrap = document.createElement('div');

    if (r.route === 'refusal') {
      // Boundary redirect
      wrap.innerHTML = boundaryCard(r.answer, r.citation_url, r.citation_title);
      return wrap;
    }

    if (r.route === 'out_of_scope') {
      wrap.innerHTML = boundaryCard(r.answer, null, null);
      return wrap;
    }

    if (r.route === 'factual') {
      const answer = document.createElement('div');
      answer.className = 'answer answer--reveal';

      // Split answer from "Last updated" line
      let answerBody = r.answer || '';
      let lastUpdatedLine = '';
      const luMatch = answerBody.match(/^(.+?)(\s*Last updated from sources:\s*.+)$/s);
      if (luMatch) {
        answerBody = luMatch[1].trim();
        lastUpdatedLine = luMatch[2].trim();
      }

      // Check if this looks like a statement-download answer (has steps)
      const isStatementQuery = (r.intent === 'factual_statement');
      if (isStatementQuery && answerBody.length > 80) {
        // Render as numbered steps — naive split on sentences
        const sents = answerBody.split(/(?<=[.!?])\s+/).filter(s => s.trim());
        const stepsHtml = sents.map(s => `<li class="steps__item">${highlightData(s)}</li>`).join('');
        answer.innerHTML = `
          <div class="answer__direct">
            <ol class="steps">${stepsHtml}</ol>
          </div>
          ${citationCard(r)}
        `;
      } else if (answerBody.toLowerCase().startsWith("i couldn't find") ||
                 answerBody.toLowerCase().includes("couldn't find this")) {
        // Unavailable state
        wrap.innerHTML = unavailableCard(answerBody, 'https://www.growwmf.in/downloads/sid');
        return wrap;
      } else {
        answer.innerHTML = `
          <div class="answer__direct">${highlightData(answerBody)}</div>
          <div class="answer__scope">${escapeHtml(lastUpdatedLine || ('Intent: ' + r.intent))}</div>
          ${citationCard(r)}
        `;
      }
      wrap.appendChild(answer);
      return wrap;
    }

    // Fallback
    wrap.innerHTML = `<div class="answer"><div class="answer__direct">${escapeHtml(r.answer || '')}</div></div>`;
    return wrap;
  }

  // ---- Submit handler ----
  async function ask(question) {
    question = (question || '').trim();
    if (!question) return;

    // Clear input + autocomplete
    input.value = '';
    closeAutocomplete();

    // Hide intro/menu after first question
    if (intro) intro.style.display = 'none';
    if (menu) menu.style.display = 'none';

    // Render question + loading
    const turn = renderTurn(question, null, true);
    submit.disabled = true;
    input.disabled = true;

    try {
      const resp = await fetch('/api/answer', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: question }),
      });
      const result = await resp.json();

      // Replace loading with result
      const loading = turn.querySelector('.loading');
      if (loading) loading.remove();
      turn.appendChild(renderResult(result));
      turn.scrollIntoView({ behavior: 'smooth', block: 'end' });
    } catch (err) {
      const loading = turn.querySelector('.loading');
      if (loading) loading.remove();
      const errDiv = document.createElement('div');
      errDiv.innerHTML = unavailableCard(
        'Network error — could not reach the lookup service.',
        'https://www.growwmf.in/downloads/sid'
      );
      turn.appendChild(errDiv.firstChild);
    } finally {
      submit.disabled = false;
      input.disabled = false;
      input.focus();
    }
  }

  form.addEventListener('submit', e => {
    e.preventDefault();
    ask(input.value);
  });

  // ---- Chip click handlers ----
  document.querySelectorAll('.chip').forEach(chip => {
    chip.addEventListener('click', () => {
      const q = chip.getAttribute('data-q');
      if (q) ask(q);
    });
  });

  // ---- Autocomplete ----
  function openAutocomplete(matches) {
    acItems = matches;
    acActiveIdx = -1;
    if (!matches.length) {
      closeAutocomplete();
      return;
    }
    autocomplete.innerHTML = matches.map((m, i) => `
      <div class="autocomplete__item" role="option" data-idx="${i}">
        <span class="autocomplete__scheme">${escapeHtml(m.name)}</span>
        <span class="autocomplete__category">${escapeHtml(m.category)}</span>
      </div>
    `).join('');
    autocomplete.classList.add('autocomplete--open');

    // Click handlers
    autocomplete.querySelectorAll('.autocomplete__item').forEach(el => {
      el.addEventListener('click', () => {
        const idx = parseInt(el.getAttribute('data-idx'));
        selectAutocomplete(idx);
      });
    });
  }

  function closeAutocomplete() {
    autocomplete.classList.remove('autocomplete--open');
    autocomplete.innerHTML = '';
    acItems = [];
    acActiveIdx = -1;
  }

  function selectAutocomplete(idx) {
    if (idx < 0 || idx >= acItems.length) return;
    const s = acItems[idx];
    // Build a default question for this scheme — ask expense ratio
    input.value = `What is the expense ratio of ${s.name}?`;
    closeAutocomplete();
    input.focus();
  }

  function highlightAcItem() {
    autocomplete.querySelectorAll('.autocomplete__item').forEach((el, i) => {
      el.classList.toggle('autocomplete__item--active', i === acActiveIdx);
    });
  }

  input.addEventListener('input', () => {
    const v = input.value.toLowerCase();
    if (v.length < 3) { closeAutocomplete(); return; }
    // Detect if user is typing a scheme name
    const matches = SCHEMES.filter(s =>
      s.name.toLowerCase().includes(v) ||
      s.name.toLowerCase().split(' ').some(w => w.length > 3 && v.includes(w))
    );
    if (matches.length && matches.length < SCHEMES.length) {
      openAutocomplete(matches);
    } else {
      closeAutocomplete();
    }
  });

  input.addEventListener('keydown', e => {
    if (!autocomplete.classList.contains('autocomplete--open')) return;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      acActiveIdx = Math.min(acActiveIdx + 1, acItems.length - 1);
      highlightAcItem();
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      acActiveIdx = Math.max(acActiveIdx - 1, 0);
      highlightAcItem();
    } else if (e.key === 'Enter' && acActiveIdx >= 0) {
      e.preventDefault();
      selectAutocomplete(acActiveIdx);
    } else if (e.key === 'Escape') {
      closeAutocomplete();
    }
  });

  // Close autocomplete on outside click
  document.addEventListener('click', e => {
    if (!autocomplete.contains(e.target) && e.target !== input) {
      closeAutocomplete();
    }
  });

  // ---- Focus input on load ----
  input.focus();
})();
