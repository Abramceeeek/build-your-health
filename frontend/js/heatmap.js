const MUSCLE_SVG_CLASSES = {
  chest:      ['.muscle-chest-l', '.muscle-chest-r'],
  shoulders:  ['.muscle-shoulders-l', '.muscle-shoulders-r'],
  back:       ['.muscle-back-l', '.muscle-back-r'],
  biceps:     ['.muscle-biceps-l', '.muscle-biceps-r'],
  triceps:    ['.muscle-triceps-l', '.muscle-triceps-r'],
  forearms:   ['.muscle-forearms-l', '.muscle-forearms-r'],
  core:       ['.muscle-core'],
  quads:      ['.muscle-quads-l', '.muscle-quads-r'],
  hamstrings: ['.muscle-hamstrings-l', '.muscle-hamstrings-r'],
  glutes:     ['.muscle-glutes'],
  calves:     ['.muscle-calves-l', '.muscle-calves-r'],
};

// H4 — when no workouts logged yet, faint outline reads as "unlocked later",
// not "broken image".
const EMPTY_FILL = '#1A1A1C';

function isAllZero(muscleData) {
  if (!muscleData) return true;
  return Object.values(muscleData).every(v => !v);
}

function intensityColor(value) {
  if (value <= 0) return EMPTY_FILL;
  if (value < 0.25) return '#1B3A1B';
  if (value < 0.5) return '#2D6A2D';
  if (value < 0.75) return '#34C759';
  return '#30D158';
}

function applyHeatmap(svgContainer, muscleData) {
  if (!svgContainer || !muscleData) return;

  const svgDoc = svgContainer.contentDocument || svgContainer.getSVGDocument();
  if (!svgDoc) return;

  for (const [muscle, selectors] of Object.entries(MUSCLE_SVG_CLASSES)) {
    const intensity = muscleData[muscle] || 0;
    const color = intensityColor(intensity);

    for (const selector of selectors) {
      const el = svgDoc.querySelector(selector);
      if (el) {
        el.style.fill = color;
        el.style.transition = 'fill 0.5s ease';
      }
    }
  }
}

function applyHeatmapToInlineSVG(svgElement, muscleData) {
  if (!svgElement || !muscleData) return;

  for (const [muscle, selectors] of Object.entries(MUSCLE_SVG_CLASSES)) {
    const intensity = muscleData[muscle] || 0;
    const color = intensityColor(intensity);

    for (const selector of selectors) {
      const el = svgElement.querySelector(selector);
      if (el) {
        el.style.fill = color;
        el.style.transition = 'fill 0.5s ease';
      }
    }
  }
}

async function loadSVGInline(container, svgUrl) {
  try {
    const res = await fetch(svgUrl);
    const text = await res.text();
    container.innerHTML = text;
    return container.querySelector('svg');
  } catch (e) {
    return null;
  }
}
