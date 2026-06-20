/* Body Measurements Module */
const MeasurementsModule = (() => {
  const CATS = {
    core:    { label: 'Core body metrics',          color: '#185FA5', bg: '#E6F1FB' },
    upper:   { label: 'Upper body',                 color: '#3B6D11', bg: '#EAF3DE' },
    lower:   { label: 'Lower body',                 color: '#854F0B', bg: '#FAEEDA' },
    waist:   { label: 'Waist & core composition',   color: '#0F6E56', bg: '#E1F5EE' },
    face:    { label: 'Facial measurements',         color: '#993556', bg: '#FBEAF0' },
    posture: { label: 'Posture',                     color: '#534AB7', bg: '#EEEDFE' },
    health:  { label: 'Health & performance',        color: '#5F5E5A', bg: '#F1EFE8' },
    skin:    { label: 'Skin & aesthetics (AI)',      color: '#993C1D', bg: '#FAECE7' },
  };

  // [cat, label, unit, freq, sides?, ai?]
  const DEFS = {
    height:              ['core',    'Height',                  'cm',         'once'],
    body_weight:         ['core',    'Body weight',             'kg',         'daily'],
    body_fat:            ['core',    'Body fat %',              '%',          'monthly'],
    wrist:               ['core',    'Wrist',                   'cm',         'once'],
    ankle_bone:          ['core',    'Ankle',                   'cm',         'once'],

    chest_full:          ['upper',   'Chest (full)',            'cm',         'weekly'],
    shoulders_width:     ['upper',   'Shoulders width',         'cm',         'weekly'],
    bicep_flexed:        ['upper',   'Bicep (flexed)',          'cm',         'weekly',  true],
    bicep_relaxed:       ['upper',   'Bicep (relaxed)',         'cm',         'weekly',  true],
    forearm:             ['upper',   'Forearm',                 'cm',         'weekly',  true],
    neck:                ['upper',   'Neck',                    'cm',         'weekly'],
    tricep:              ['upper',   'Tricep',                  'cm',         'weekly',  true],
    upper_back_width:    ['upper',   'Upper back width',        'cm',         'monthly'],
    traps:               ['upper',   'Traps / upper back',      'cm',         'monthly'],
    chest_upper:         ['upper',   'Chest (upper)',           'cm',         'monthly'],
    shoulder_each:       ['upper',   'Shoulder (each)',         'cm',         'monthly', true],

    thigh_upper:         ['lower',   'Thigh (upper)',           'cm',         'weekly',  true],
    thigh_mid:           ['lower',   'Thigh (mid)',             'cm',         'weekly',  true],
    calf:                ['lower',   'Calf',                    'cm',         'weekly',  true],
    glutes_hips:         ['lower',   'Glutes / hips',           'cm',         'weekly'],
    knee:                ['lower',   'Knee',                    'cm',         'once'],
    hip_bones:           ['lower',   'Hip bones (iliac)',       'cm',         'once'],
    hamstring_upper:     ['lower',   'Hamstring (upper)',       'cm',         'monthly', true],

    waist_navel:         ['waist',   'Waist (navel)',           'cm',         'weekly'],
    waist_narrowest:     ['waist',   'Waist (narrowest)',       'cm',         'weekly'],
    lower_abdomen:       ['waist',   'Lower abdomen',           'cm',         'weekly'],
    lower_back_fat:      ['waist',   'Lower back / love handles','cm',        'weekly'],
    abdominal_depth:     ['waist',   'Abdominal depth',         'cm',         'monthly'],

    face_length:         ['face',    'Face length',             'mm',         'monthly', false, true],
    cheekbone_width:     ['face',    'Cheekbone width',         'mm',         'monthly', false, true],
    jawline_width:       ['face',    'Jawline width',           'mm',         'monthly', false, true],
    jaw_angle:           ['face',    'Jaw angle',               'mm',         'monthly', false, true],
    forehead_width:      ['face',    'Forehead width',          'mm',         'monthly', false, true],
    neck_circumference:  ['face',    'Neck circumference',      'cm',         'weekly'],
    mid_face_height:     ['face',    'Mid-face height',         'mm',         'monthly', false, true],
    undereye_puffiness:  ['face',    'Under-eye puffiness',     '/10',        'weekly',  false, true],
    facial_fat_score:    ['face',    'Facial fat score',        '/10',        'weekly',  false, true],
    facial_symmetry:     ['face',    'Facial symmetry',         '/10',        'monthly', false, true],

    forward_head:        ['posture', 'Forward head distance',   'cm',         'monthly', false, true],
    shoulder_height_diff:['posture', 'Shoulder height diff',    'mm',         'monthly', false, true],
    hip_tilt_apt:        ['posture', 'Hip tilt (APT)',          '°',          'monthly', false, true],
    thoracic_kyphosis:   ['posture', 'Thoracic kyphosis',       '°',          'monthly', false, true],
    shoulder_rounding:   ['posture', 'Shoulder rounding',       'cm',         'monthly', false, true],
    knee_alignment:      ['posture', 'Knee alignment (valgus)', 'score',      'monthly', false, true],

    resting_hr:          ['health',  'Resting heart rate',      'bpm',        'daily'],
    blood_pressure_sys:  ['health',  'Blood pressure (sys)',    'mmHg',       'monthly'],
    blood_pressure_dia:  ['health',  'Blood pressure (dia)',    'mmHg',       'monthly'],
    grip_strength:       ['health',  'Grip strength',           'kg',         'monthly'],
    vo2max:              ['health',  'VO2 max (estimated)',     'ml/kg/min',  'monthly'],
    flexibility:         ['health',  'Flexibility score',       'cm',         'monthly'],

    skin_clarity:        ['skin',    'Skin clarity',            '/10',        'weekly',  false, true],
    dark_circles:        ['skin',    'Dark circles',            '/10',        'weekly',  false, true],
    muscle_vascularity:  ['skin',    'Muscle vascularity',      '/10',        'monthly', false, true],
    muscle_definition:   ['skin',    'Muscle definition',       '/10',        'monthly', false, true],
  };

  let _latest = {};
  let _activeMeasKey = null;
  let _activeSide = null;  // 'left' | 'right' | null

  function _def(key) {
    // key might be "bicep_flexed_left" — strip side suffix for base lookup
    const base = key.replace(/_left$|_right$/, '');
    return DEFS[base] ? { base, ...parseArr(DEFS[base]) } : null;
  }

  function parseArr([cat, label, unit, freq, sides = false, ai = false]) {
    return { cat, label, unit, freq, sides, ai };
  }

  // ── Sparkline SVG ──────────────────────────────────────────────────────────
  function _sparkline(values, width = 120, height = 32) {
    if (!values || values.length < 2) return '';
    const min = Math.min(...values), max = Math.max(...values);
    const range = max - min || 1;
    const pts = values.map((v, i) => {
      const x = (i / (values.length - 1)) * width;
      const y = height - ((v - min) / range) * (height - 4) - 2;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(' ');
    const lastX = width, lastY = height - ((values[values.length - 1] - min) / range) * (height - 4) - 2;
    return `<svg width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" style="overflow:visible">
      <polyline points="${pts}" fill="none" stroke="var(--color-accent,#3b82f6)" stroke-width="1.5" stroke-linejoin="round"/>
      <circle cx="${lastX.toFixed(1)}" cy="${lastY.toFixed(1)}" r="2.5" fill="var(--color-accent,#3b82f6)"/>
    </svg>`;
  }

  // ── Render full page ───────────────────────────────────────────────────────
  function render() {
    const container = document.getElementById('measurementsSections');
    if (!container) return;

    const byCat = {};
    for (const [key, arr] of Object.entries(DEFS)) {
      const d = parseArr(arr);
      if (!byCat[d.cat]) byCat[d.cat] = [];
      byCat[d.cat].push({ key, ...d });
    }

    let html = '';
    for (const [catKey, cat] of Object.entries(CATS)) {
      const items = byCat[catKey] || [];
      if (!items.length) continue;

      const count = items.reduce((n, m) => n + (m.sides ? 2 : 1), 0);
      const logged = items.reduce((n, m) => {
        if (m.sides) {
          return n + ((_latest[m.key + '_left'] != null) ? 1 : 0) + ((_latest[m.key + '_right'] != null) ? 1 : 0);
        }
        return n + (_latest[m.key] != null ? 1 : 0);
      }, 0);

      html += `<div class="meas-section" style="margin-bottom:16px">
        <div class="meas-section-header" style="background:${cat.bg};border-radius:10px;padding:10px 14px;display:flex;align-items:center;gap:10px;margin-bottom:8px;cursor:pointer" onclick="this.parentNode.querySelector('.meas-grid').toggleAttribute('hidden')">
          <span style="font-size:14px;font-weight:600;color:${cat.color};flex:1">${cat.label}</span>
          <span style="font-size:11px;color:${cat.color};opacity:.8">${logged}/${count} logged</span>
          <span style="font-size:11px;color:${cat.color}">▾</span>
        </div>
        <div class="meas-grid" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:8px">`;

      for (const m of items) {
        if (m.sides) {
          html += _card(m.key + '_left',  m, 'L', cat.color);
          html += _card(m.key + '_right', m, 'R', cat.color);
        } else {
          html += _card(m.key, m, null, cat.color);
        }
      }

      html += `</div></div>`;
    }

    container.innerHTML = html;
  }

  function _card(fullKey, m, side, color) {
    const entry = _latest[fullKey];
    const val = entry ? `<span style="font-size:18px;font-weight:700;color:${color}">${entry.value}</span><span style="font-size:11px;color:#888;margin-left:3px">${m.unit}</span>` : `<span style="font-size:16px;color:#555">—</span>`;
    const date = entry ? `<div style="font-size:10px;color:#666;margin-top:2px">${entry.date}</div>` : '';
    const sideLabel = side ? `<span style="font-size:10px;background:rgba(0,0,0,.12);border-radius:4px;padding:1px 5px;margin-left:4px">${side}</span>` : '';
    const ai = m.ai ? `<span style="font-size:9px;color:#aaa;margin-left:4px">AI</span>` : '';
    return `<div class="meas-card" onclick="MeasurementsModule.openLog('${fullKey}')" style="background:var(--card-bg,#1a1a1a);border:1px solid var(--border,#2a2a2a);border-radius:10px;padding:12px;cursor:pointer;active:opacity(.7)">
      <div style="font-size:12px;font-weight:500;margin-bottom:6px">${m.label}${sideLabel}${ai}</div>
      ${val}${date}
    </div>`;
  }

  // ── Log modal ──────────────────────────────────────────────────────────────
  async function openLog(fullKey) {
    _activeMeasKey = fullKey;
    const def = _def(fullKey);
    if (!def) return;

    const side = fullKey.endsWith('_left') ? 'Left' : fullKey.endsWith('_right') ? 'Right' : null;
    const label = def.label + (side ? ` (${side})` : '');
    const existing = _latest[fullKey];

    document.getElementById('measModalTitle').textContent = label;
    document.getElementById('measModalUnit').textContent = def.unit;
    document.getElementById('measModalInput').value = existing ? existing.value : '';
    document.getElementById('measModalDate').value = new Date().toISOString().slice(0, 10);

    // Load and render history
    const histContainer = document.getElementById('measModalHistory');
    histContainer.innerHTML = '<div style="color:#666;font-size:12px">Loading…</div>';
    _showSheet('measLogSheet');

    try {
      const hist = await API.getMeasurementHistory(fullKey);
      _renderHistory(histContainer, hist, def.unit);
    } catch (e) {
      histContainer.innerHTML = '';
    }
    document.getElementById('measModalInput').focus();
  }

  function _renderHistory(container, hist, unit) {
    if (!hist.length) { container.innerHTML = '<div style="color:#666;font-size:12px;padding:8px 0">No history yet</div>'; return; }
    const vals = hist.map(h => h.value);
    const svg = _sparkline(vals, 220, 40);
    const rows = hist.slice(-6).reverse().map(h =>
      `<div style="display:flex;justify-content:space-between;font-size:12px;padding:4px 0;border-bottom:1px solid #222">
        <span style="color:#aaa">${h.date}</span>
        <span style="font-weight:600">${h.value} <span style="color:#666;font-weight:400">${unit}</span></span>
      </div>`
    ).join('');
    container.innerHTML = `<div style="margin:8px 0 4px">${svg}</div><div>${rows}</div>`;
  }

  async function saveLog() {
    const val = parseFloat(document.getElementById('measModalInput').value);
    const date = document.getElementById('measModalDate').value;
    if (isNaN(val) || !_activeMeasKey) return;
    try {
      await API.logMeasurements([{ key: _activeMeasKey, value: val, date }]);
      _latest[_activeMeasKey] = { value: val, date };
      _hideSheet('measLogSheet');
      render();
    } catch (e) {
      alert('Save failed: ' + e.message);
    }
  }

  function _showSheet(id) {
    const el = document.getElementById(id);
    if (el) { el.style.display = 'flex'; requestAnimationFrame(() => el.classList.add('open')); }
  }
  function _hideSheet(id) {
    const el = document.getElementById(id);
    if (!el) return;
    el.classList.remove('open');
    setTimeout(() => { el.style.display = 'none'; }, 250);
  }

  async function load() {
    try {
      _latest = await API.getLatestMeasurements();
    } catch (e) {
      _latest = {};
    }
    render();
  }

  // Weekly log — batch input for all weekly measurements
  function openWeeklyLog() {
    const weekly = Object.entries(DEFS)
      .filter(([, arr]) => arr[3] === 'weekly')
      .map(([key, arr]) => ({ key, ...parseArr(arr) }));

    const rows = weekly.map(m => {
      if (m.sides) {
        return _weeklyRow(m.key + '_left', m, 'Left') + _weeklyRow(m.key + '_right', m, 'Right');
      }
      return _weeklyRow(m.key, m, null);
    }).join('');

    document.getElementById('measWeeklyBody').innerHTML = rows;
    _showSheet('measWeeklySheet');
  }

  function _weeklyRow(fullKey, m, side) {
    const v = _latest[fullKey];
    const label = m.label + (side ? ` (${side})` : '');
    return `<div style="display:flex;align-items:center;gap:10px;padding:8px 0;border-bottom:1px solid #222">
      <span style="flex:1;font-size:13px">${label}</span>
      <input type="number" step="0.1" class="meas-weekly-input" data-key="${fullKey}" placeholder="${v ? v.value : m.unit}"
        style="width:80px;padding:6px 8px;border-radius:8px;border:1px solid #444;background:#111;color:#fff;font-size:13px;text-align:right">
    </div>`;
  }

  async function saveWeekly() {
    const date = new Date().toISOString().slice(0, 10);
    const entries = [];
    document.querySelectorAll('.meas-weekly-input').forEach(inp => {
      const v = parseFloat(inp.value);
      if (!isNaN(v) && inp.dataset.key) {
        entries.push({ key: inp.dataset.key, value: v, date });
      }
    });
    if (!entries.length) { _hideSheet('measWeeklySheet'); return; }
    try {
      await API.logMeasurements(entries);
      entries.forEach(e => { _latest[e.key] = { value: e.value, date: e.date }; });
      _hideSheet('measWeeklySheet');
      render();
    } catch (e) {
      alert('Save failed: ' + e.message);
    }
  }

  return { load, openLog, saveLog, openWeeklyLog, saveWeekly };
})();
