/* Groww MF Facts - B&W Interactive */
(function() {
  'use strict';

  const logoIntro = document.getElementById('logoIntro');
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  if (reduceMotion) {
    if (logoIntro) logoIntro.style.display = 'none';
    initPage();
  } else if (logoIntro) {
    setTimeout(() => {
      logoIntro.classList.add('logo-intro--done');
      setTimeout(() => {
        logoIntro.style.display = 'none';
        initPage();
      }, 700);
    }, 3200);
  } else {
    initPage();
  }

  function initPage() {
    initHeadline();
    initCursor();
    initScrollProgress();
    initNav();
    initMagnetic();
    initRevealOnScroll();
    initSectionTitles();
    initChips();
    initInput();
    initChat();
  }

  /* ===== Headline: word-by-word reveal ===== */
  function initHeadline() {
    const h1 = document.getElementById('heroHeadline');
    if (!h1) return;
    const text = "Factual answers about Groww mutual fund schemes.";
    const words = text.split(' ');
    // Make "Groww" the accent word (italic + underlined)
    h1.innerHTML = words.map((w, i) => {
      const cls = w === 'Groww' ? 'word word--accent' : 'word';
      const delay = (0.3 + i * 0.08).toFixed(2);
      return `<span class="${cls}" style="animation-delay:${delay}s">${w}</span>`;
    }).join(' ');
  }

  /* ===== Custom cursor ===== */
  function initCursor() {
    if (reduceMotion || !window.matchMedia('(hover: hover) and (pointer: fine)').matches) return;
    const cursor = document.getElementById('cursor');
    if (!cursor) return;
    document.addEventListener('mousemove', e => {
      cursor.style.left = e.clientX + 'px';
      cursor.style.top = e.clientY + 'px';
    });
    document.querySelectorAll('a, button, .chip, input, .pii-badge, .badge').forEach(el => {
      el.addEventListener('mouseenter', () => cursor.classList.add('hover'));
      el.addEventListener('mouseleave', () => cursor.classList.remove('hover'));
    });
  }

  /* ===== Scroll progress ===== */
  function initScrollProgress() {
    const bar = document.getElementById('scrollBar');
    if (!bar) return;
    window.addEventListener('scroll', () => {
      const h = document.documentElement;
      bar.style.transform = `scaleX(${h.scrollTop / (h.scrollHeight - h.clientHeight)})`;
    }, { passive: true });
  }

  /* ===== Nav ===== */
  function initNav() {
    const nav = document.getElementById('nav');
    if (!nav) return;
    window.addEventListener('scroll', () => {
      nav.classList.toggle('nav--scrolled', window.scrollY > 100);
    }, { passive: true });
    document.querySelectorAll('.nav__link').forEach(link => {
      link.addEventListener('click', e => {
        const href = link.getAttribute('href');
        if (href && href.startsWith('#')) {
          e.preventDefault();
          document.querySelector(href)?.scrollIntoView({ behavior: 'smooth' });
        }
      });
    });
  }

  /* ===== Magnetic buttons ===== */
  function initMagnetic() {
    if (reduceMotion || !window.matchMedia('(hover: hover) and (pointer: fine)').matches) return;
    document.querySelectorAll('[data-magnetic]').forEach(el => {
      el.addEventListener('mousemove', e => {
        const rect = el.getBoundingClientRect();
        const x = e.clientX - rect.left - rect.width / 2;
        const y = e.clientY - rect.top - rect.height / 2;
        el.style.transform = `translate(${x * 0.2}px, ${y * 0.2}px)`;
      });
      el.addEventListener('mouseleave', () => {
        el.style.transform = '';
      });
    });
  }

  /* ===== Reveal on scroll ===== */
  function initRevealOnScroll() {
    const items = document.querySelectorAll('[data-reveal], .chip');
    if (reduceMotion) {
      items.forEach(el => { el.style.opacity = '1'; el.style.transform = 'none'; });
      return;
    }
    const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          if (entry.target.classList.contains('chip')) {
            const siblings = Array.from(entry.target.parentElement.children);
            const delay = siblings.indexOf(entry.target) * 50;
            setTimeout(() => entry.target.classList.add('chip--visible'), delay);
          } else {
            entry.target.classList.add('how-step--visible', 'bento-card--visible');
          }
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.15 });
    items.forEach(el => observer.observe(el));
  }

  /* ===== Section titles: word-by-word reveal ===== */
  function initSectionTitles() {
    document.querySelectorAll('[data-words]').forEach(title => {
      const words = title.textContent.trim().split(' ');
      title.innerHTML = words.map(w => `<span class="word">${w}</span>`).join(' ');
      const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            const wordEls = entry.target.querySelectorAll('.word');
            wordEls.forEach((w, i) => {
              setTimeout(() => {
                w.style.opacity = '1';
                w.style.transform = 'translateY(0)';
              }, i * 80);
            });
            observer.unobserve(entry.target);
          }
        });
      }, { threshold: 0.5 });
      observer.observe(title);
    });
  }

  /* ===== Chips ===== */
  function initChips() {
    document.querySelectorAll('.chip').forEach(chip => {
      chip.addEventListener('click', () => {
        const q = chip.getAttribute('data-q');
        if (q) {
          const input = document.getElementById('askInput');
          input.value = q;
          document.getElementById('inputWrap').classList.add('input-wrap--pulse');
          setTimeout(() => document.getElementById('inputWrap').classList.remove('input-wrap--pulse'), 400);
          input.focus();
        }
      });
    });
  }

  /* ===== Input ===== */
  function initInput() {
    const input = document.getElementById('askInput');
    const clearBtn = document.getElementById('clearBtn');
    const form = document.getElementById('askForm');

    if (!reduceMotion) {
      const placeholders = [
        'What is expense ratio?',
        'What does lock-in mean?',
        'How much do I need to start a SIP?',
        'What is a riskometer?',
        'How do I download my statement?'
      ];
      let pIdx = 0, cIdx = 0, typing = true;
      function cycle() {
        const current = placeholders[pIdx];
        if (typing) {
          cIdx++;
          if (cIdx > current.length) { typing = false; setTimeout(cycle, 2000); return; }
        } else {
          cIdx--;
          if (cIdx < 0) { typing = true; pIdx = (pIdx + 1) % placeholders.length; setTimeout(cycle, 500); return; }
        }
        if (!input.value && document.activeElement !== input) {
          input.setAttribute('placeholder', current.substring(0, cIdx));
        }
        setTimeout(cycle, typing ? 50 : 30);
      }
      setTimeout(cycle, 2000);
    }

    input.addEventListener('input', () => {
      clearBtn.classList.toggle('input-clear--visible', input.value.length > 0);
    });
    clearBtn.addEventListener('click', () => {
      input.value = '';
      clearBtn.classList.remove('input-clear--visible');
      input.focus();
    });
    input.addEventListener('keydown', e => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        e.preventDefault();
        form.requestSubmit();
      }
    });
  }

  /* ===== Chat ===== */
  function initChat() {
    const form = document.getElementById('askForm');
    const input = document.getElementById('askInput');
    const submit = document.getElementById('askSubmit');
    const turns = document.getElementById('turns');

    form.addEventListener('submit', async e => {
      e.preventDefault();
      const query = input.value.trim();
      if (!query) return;

      const hero = document.querySelector('.hero');
      const chipsSection = document.querySelector('.chips-section');
      if (hero) hero.style.display = 'none';
      if (chipsSection) chipsSection.style.display = 'none';

      const turn = document.createElement('div');
      turn.className = 'turn';
      turn.innerHTML = `<div class="turn__question">${escapeHtml(query)}</div><div class="loading-state"><span class="loading-dots"><span></span><span></span><span></span></span> Checking the official source...</div>`;
      turns.appendChild(turn);
      turns.style.display = 'block';
      turn.scrollIntoView({ behavior: 'smooth' });

      submit.disabled = true;
      submit.innerHTML = '<span class="loading-dots"><span></span><span></span><span></span></span>';

      try {
        const resp = await fetch('/api/answer', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ query }),
        });
        const result = await resp.json();
        const loading = turn.querySelector('.loading-state');
        if (loading) loading.remove();
        turn.appendChild(renderResult(result));
        turn.scrollIntoView({ behavior: 'smooth' });
      } catch (err) {
        const loading = turn.querySelector('.loading-state');
        if (loading) loading.remove();
        turn.innerHTML += `<div class="boundary"><span class="boundary__label">Error</span>Network error - could not reach the lookup service.</div>`;
      } finally {
        submit.disabled = false;
        submit.innerHTML = '<span>Ask</span>';
        input.value = '';
        document.getElementById('clearBtn').classList.remove('input-clear--visible');
      }
    });
  }

  function renderResult(r) {
    const wrap = document.createElement('div');
    if (r.route === 'refusal' || r.route === 'out_of_scope') {
      wrap.innerHTML = `<div class="boundary"><span class="boundary__label">Outside scope</span>${escapeHtml(r.answer)}</div>`;
      if (r.citation_url) wrap.innerHTML += citationCard(r);
      return wrap;
    }
    if (r.route === 'factual') {
      let body = r.answer || '';
      let lastUpdated = '';
      const m = body.match(/^(.+?)\s*\n+Last updated from sources:\s*(.+)$/s);
      if (m) { body = m[1].trim(); lastUpdated = m[2].trim(); }
      if (body.toLowerCase().includes("couldn't find")) {
        wrap.innerHTML = `<div class="boundary"><span class="boundary__label">Couldn't verify</span>${escapeHtml(body)}</div>`;
        return wrap;
      }
      const isStatement = r.intent === 'factual_statement' && body.length > 80;
      if (isStatement) {
        const sents = body.split(/(?<=[.!?])\s+/).filter(s => s.trim());
        const steps = sents.map(s => `<li class="steps__item">${highlightData(s)}</li>`).join('');
        wrap.innerHTML = `<div class="answer"><div class="answer__direct"><ol class="steps">${steps}</ol></div>${lastUpdated ? `<div class="answer__scope">Last updated: ${escapeHtml(lastUpdated)}</div>` : ''}${citationCard(r)}</div>`;
      } else {
        wrap.innerHTML = `<div class="answer"><div class="answer__direct">${highlightData(body)}</div>${lastUpdated ? `<div class="answer__scope">Last updated: ${escapeHtml(lastUpdated)}</div>` : ''}${citationCard(r)}</div>`;
      }
      return wrap;
    }
    wrap.innerHTML = `<div class="answer"><div class="answer__direct">${escapeHtml(r.answer || '')}</div></div>`;
    return wrap;
  }

  function citationCard(r) {
    if (!r || !r.citation_url) return '';
    return `<div class="citation"><span class="citation__label">Source</span><div class="citation__issuer">${escapeHtml(issuerFromUrl(r.citation_url))}</div><div class="citation__doctype">${escapeHtml(doctypeFromResult(r))}</div><div class="citation__meta">As of ${escapeHtml(r.last_updated || '-')}</div><a class="citation__link" href="${escapeHtml(r.citation_url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(r.citation_url.replace(/^https?:\/\//, '').slice(0, 75))}</a></div>`;
  }

  function issuerFromUrl(url) {
    if (url.includes('growwmf.in')) return 'Groww Asset Management Ltd.';
    if (url.includes('groww.in')) return 'Groww (distributor page)';
    if (url.includes('investor.sebi.gov.in')) return 'SEBI Investor';
    if (url.includes('sebi.gov.in')) return 'Securities and Exchange Board of India';
    if (url.includes('amfiindia.com')) return 'Association of Mutual Funds in India';
    return 'Official source';
  }

  function doctypeFromResult(r) {
    const t = (r.citation_title || '').toLowerCase();
    if (t.includes('scheme information') || t.includes('sid')) return 'Scheme Information Document';
    if (t.includes('key information') || t.includes('kim')) return 'Key Information Memorandum';
    if (t.includes('factsheet')) return 'Monthly Factsheet';
    if (t.includes('faq')) return 'Regulatory FAQ';
    if (t.includes('capital gains') || t.includes('statement')) return 'Help Article - Statements';
    if (t.includes('growth')) return 'Scheme Page';
    return 'Official public source';
  }

  function highlightData(text) {
    let t = escapeHtml(text);
    t = t.replace(/(\d+(?:\.\d+)?%)/g, '<span class="num">$1</span>');
    t = t.replace(/([\u20B9][\d,]+)/g, '<span class="num">$1</span>');
    t = t.replace(/(Rs\.?\s*[\d,]+)/g, '<span class="num">$1</span>');
    t = t.replace(/(\d+\s+(?:year|day|month|week)s?)/gi, '<span class="num">$1</span>');
    t = t.replace(/\b(Nil)\b/g, '<span class="risk-chip">$1</span>');
    t = t.replace(/\b(Very High Risk|High Risk|Moderately High Risk|Moderate Risk|Low to Moderate Risk|Low Risk)\b/g, '<span class="risk-chip">$1</span>');
    return t;
  }

  function escapeHtml(s) {
    return (s || '').replace(/[&<>"']/g, ch => ({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;' }[ch]));
  }
})();
