/* Groww MF Facts - front-end interaction v2 */
(function() {
  'use strict';

  const SCHEMES = [
    { name: 'Groww Large Cap Fund', category: 'Equity - Large Cap' },
    { name: 'Groww Value Fund', category: 'Equity - Value' },
    { name: 'Groww Small Cap Fund', category: 'Equity - Small Cap' },
    { name: 'Groww ELSS Tax Saver Fund', category: 'Equity - ELSS (80C)' },
    { name: 'Groww Nifty 50 Index Fund', category: 'Passive - Index' },
    { name: 'Groww Liquid Fund', category: 'Debt - Liquid' },
    { name: 'Groww Overnight Fund', category: 'Debt - Overnight' },
  ];

  const form = document.getElementById('ask-form');
  const input = document.getElementById('ask-input');
  const submit = document.getElementById('ask-submit');
  const turns = document.getElementById('turns');
  const autocomplete = document.getElementById('autocomplete');

  let acItems = [];
  let acActiveIdx = -1;

  function escapeHtml(s) {
    return (s || '').replace(/[&<>"']/g, ch => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }[ch]));
  }

  function highlightData(text) {
    let t = escapeHtml(text);
    t = t.replace(/(\d+(?:\.\d+)?%)/g, '<span class="num">$1</span>');
    t = t.replace(/([\u20B9][\d,]+)/g, '<span class="num">$1</span>');
    t = t.replace(/(Rs\.?\s*[\d,]+)/g, '<span class="num">$1</span>');
    t = t.replace(/(\d+\s+(?:year|day|month|week)s?)/gi, '<span class="num">$1</span>');
    t = t.replace(/\b(Nil)\b/g, '<span class="risk-chip">$1</span>');
    t = t.replace(/\b(Very High Risk|High Risk|Moderately High Risk|Moderate Risk|Low to Moderate Risk|Low Risk)\b/g,
      '<span class="risk-chip">$1</span>');
    return t;
  }

  function issuerFromUrl(url) {
    if (!url) return 'Official source';
    if (url.includes('growwmf.in')) return 'Groww Asset Management Ltd.';
    if (url.includes('groww.in')) return 'Groww (distributor page)';
    if (url.includes('investor.sebi.gov.in')) return 'SEBI Investor';
    if (url.includes('sebi.gov.in')) return 'Securities and Exchange Board of India';
    if (url.includes('amfiindia.com')) return 'Association of Mutual Funds in India';
    return 'Official source';
  }

  function doctypeFromResult(r) {
    const t = (r.citation_title || '').toLowerCase();
    if (t.includes('scheme information document') || t.includes('sid')) return 'Scheme Information Document';
    if (t.includes('key information memorandum') || t.includes('kim')) return 'Key Information Memorandum';
    if (t.includes('factsheet') || t.includes('fact sheet')) return 'Monthly Factsheet';
    if (t.includes('faq')) return 'Regulatory FAQ';
    if (t.includes('riskometer')) return 'Regulatory Explainer - Riskometer';
    if (t.includes('exit load')) return 'Regulatory Explainer - Exit Load';
    if (t.includes('capital gains statement') || t.includes('statement')) return 'Help Article - Statements';
    if (t.includes('direct growth') || t.includes('regular growth')) return 'Scheme Page';
    return 'Official public source';
  }

  function citationCard(r) {
    if (!r || !r.citation_url) return '';
    const issuer = escapeHtml(issuerFromUrl(r.citation_url));
    const doctype = escapeHtml(doctypeFromResult(r));
    const asof = escapeHtml(r.last_updated || '-');
    const url = escapeHtml(r.citation_url);
    const urlDisplay = escapeHtml(r.citation_url.replace(/^https?:\/\//, '').slice(0, 75) + (r.citation_url.length > 75 ? '...' : ''));
    return `
      <div class="citation" role="note" aria-label="Source citation">
        <span class="citation__label">Source</span>
        <div class="citation__issuer">${issuer}</div>
        <div class="citation__doctype">${doctype}</div>
        <div class="citation__meta">As of ${asof}</div>
        <a class="citation__link" href="${url}" target="_blank" rel="noopener noreferrer">${urlDisplay}</a>
      </div>
    `;
  }

  function boundaryCard(answer, r) {
    let html = `
      <div class="boundary" role="note">
        <span class="boundary__label">Outside scope</span>
        <div>${escapeHtml(answer)}</div>
      </div>
    `;
    if (r && r.citation_url) {
      html += citationCard(r);
    }
    return html;
  }

  function unavailableCard(msg, hintLink) {
    return `
      <div class="unavailable" role="alert">
        <span class="unavailable__label">Couldn't verify</span>
        <div>${escapeHtml(msg)}</div>
        ${hintLink ? `<div class="unavailable__hint">Check the official AMC page: <a href="${escapeHtml(hintLink)}" target="_blank" rel="noopener noreferrer">growwmf.in/downloads</a></div>` : ''}
      </div>
    `;
  }

  function renderTurn(question, result, isLoading) {
    const turn = document.createElement('article');
    turn.className = 'turn';

    const q = document.createElement('div');
    q.className = 'turn__question';
    q.textContent = question;
    turn.appendChild(q);

    if (isLoading) {
      const loading = document.createElement('div');
      loading.className = 'loading';
      loading.innerHTML = '<span class="loading__dot"></span> Checking the official source...';
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

    if (r.route === 'refusal' || r.route === 'out_of_scope') {
      wrap.innerHTML = boundaryCard(r.answer, r);
      return wrap;
    }

    if (r.route === 'factual') {
      let answerBody = r.answer || '';
      let lastUpdatedLine = '';
      const luMatch = answerBody.match(/^(.+?)\s*\n+Last updated from sources:\s*(.+)$/s);
      if (luMatch) {
        answerBody = luMatch[1].trim();
        lastUpdatedLine = luMatch[2].trim();
      }

      if (answerBody.toLowerCase().includes("couldn't find")) {
        wrap.innerHTML = unavailableCard(answerBody, 'https://www.growwmf.in/downloads/sid');
        return wrap;
      }

      const isStatementQuery = (r.intent === 'factual_statement');
      if (isStatementQuery && answerBody.length > 80) {
        const sents = answerBody.split(/(?<=[.!?])\s+/).filter(s => s.trim());
        const stepsHtml = sents.map(s => `<li class="steps__item">${highlightData(s)}</li>`).join('');
        wrap.innerHTML = `
          <div class="answer">
            <div class="answer__direct"><ol class="steps">${stepsHtml}</ol></div>
            <div class="answer__scope">Last updated from sources: ${escapeHtml(lastUpdatedLine)}</div>
            ${citationCard(r)}
          </div>
        `;
      } else {
        wrap.innerHTML = `
          <div class="answer">
            <div class="answer__direct">${highlightData(answerBody)}</div>
            ${lastUpdatedLine ? `<div class="answer__scope">Last updated from sources: ${escapeHtml(lastUpdatedLine)}</div>` : ''}
            ${citationCard(r)}
          </div>
        `;
      }
      return wrap;
    }

    wrap.innerHTML = `<div class="answer"><div class="answer__direct">${escapeHtml(r.answer || '')}</div></div>`;
    return wrap;
  }

  async function ask(question) {
    question = (question || '').trim();
    if (!question) return;

    input.value = '';
    closeAutocomplete();

    const intro = document.querySelector('.intro');
    const menu = document.querySelector('.menu');
    if (intro) intro.style.display = 'none';
    if (menu) menu.style.display = 'none';

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

      const loading = turn.querySelector('.loading');
      if (loading) loading.remove();
      turn.appendChild(renderResult(result));
      turn.scrollIntoView({ behavior: 'smooth', block: 'end' });
    } catch (err) {
      const loading = turn.querySelector('.loading');
      if (loading) loading.remove();
      const errDiv = document.createElement('div');
      errDiv.innerHTML = unavailableCard('Network error - could not reach the lookup service.', 'https://www.growwmf.in/downloads/sid');
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

  document.querySelectorAll('.chip').forEach(chip => {
    chip.addEventListener('click', () => {
      const q = chip.getAttribute('data-q');
      if (q) ask(q);
    });
  });

  /* Autocomplete */
  function openAutocomplete(matches) {
    acItems = matches;
    acActiveIdx = -1;
    if (!matches.length) { closeAutocomplete(); return; }
    autocomplete.innerHTML = matches.map((m, i) => `
      <div class="autocomplete__item" role="option" data-idx="${i}">
        ${escapeHtml(m.name)}<span class="autocomplete__category">${escapeHtml(m.category)}</span>
      </div>
    `).join('');
    autocomplete.classList.add('autocomplete--open');
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

  document.addEventListener('click', e => {
    if (!autocomplete.contains(e.target) && e.target !== input) {
      closeAutocomplete();
    }
  });

  input.focus();
})();
