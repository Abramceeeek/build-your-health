const API_BASE = window.location.origin;

function getAuthHeader() {
  const tg = window.Telegram && window.Telegram.WebApp;
  if (tg && tg.initData) {
    return `tma ${tg.initData}`;
  }
  // Dev fallback only when running locally — production opens via Telegram only.
  const isLocal = ['localhost', '127.0.0.1'].includes(location.hostname);
  if (isLocal) {
    return 'dev {"id":12345,"first_name":"Dev","last_name":"User","username":"devuser"}';
  }
  return '';
}

async function api(path, options = {}) {
  const url = `${API_BASE}${path}`;
  const headers = {
    Authorization: getAuthHeader(),
    ...options.headers,
  };

  if (options.body && !(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json';
  }

  const timeoutMs = options._timeout ?? 10000;
  const signal = options._timeout === 0 ? options.signal
    : AbortSignal.timeout ? AbortSignal.timeout(timeoutMs)
    : options.signal;

  const res = await fetch(url, { ...options, headers, signal });

  if (!res.ok) {
    if (res.status === 402) {
      if (typeof PaywallModule !== 'undefined') PaywallModule.showUpgradeSheet();
      throw new Error('pro_required');
    }
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    const detail = err.detail;
    const msg = typeof detail === 'object' ? (detail.message || detail.error || 'API Error') : (detail || err.error || 'API Error');
    throw new Error(msg);
  }

  return res.json();
}

const API = {
  getMe: () => api('/api/users/me'),
  getMyStats: () => api('/api/users/me/stats'),
  getDashboard: () => api('/api/progress/dashboard'),
  getRegistrationStatus: () => api('/api/users/me/registration-status'),
  // offset_minutes = minutes EAST of UTC. JS getTimezoneOffset() is minutes BEHIND UTC, so negate.
  setTimezone: (offsetMinutes) => api('/api/users/me/timezone', {
    method: 'PUT', body: JSON.stringify({ offset_minutes: offsetMinutes }),
  }),
  register: (data) => api('/api/users/register', { method: 'POST', body: JSON.stringify(data) }),
  confirmTruth: () => api('/api/users/confirm-truth', { method: 'POST' }),

  getTodayTasks: () => api('/api/tasks/today'),
  getDayTasks: (date) => api(`/api/tasks/day/${date}`),
  // Default to 5 days before + today + 5 days after (11 total) for the
  // horizontal day scroller. Pass (0, 0) if you need legacy Mon-Sun.
  getWeekTasks: (daysBefore = 5, daysAfter = 5) =>
    api(`/api/tasks/week?days_before=${daysBefore}&days_after=${daysAfter}`),
  toggleTask: (taskId, payload) => api(`/api/tasks/toggle/${taskId}`, {
    method: 'POST',
    ...(payload ? { body: JSON.stringify(payload) } : {}),
  }),

  updateStreak: () => api('/api/progress/update-streak', { method: 'POST' }),
  getAchievements: () => api('/api/progress/achievements'),

  getBadges: () => api('/api/progress/badges'),
  getHabits: () => api('/api/progress/habits'),
  createHabit: (data) => api('/api/progress/habits', { method: 'POST', body: JSON.stringify(data) }),
  deleteHabit: (id) => api(`/api/progress/habits/${id}`, { method: 'DELETE' }),

  getCurrentPlan: () => api('/api/plans/current'),
  generatePlan: (data) => api('/api/plans/generate', { method: 'POST', body: JSON.stringify(data) }),
  analyzePhotos: () => api('/api/plans/analyze-photos', { method: 'POST' }),

  uploadPhoto: (photoType, file) => {
    const form = new FormData();
    form.append('file', file);
    return api(`/api/users/me/photos?photo_type=${photoType}`, { method: 'POST', body: form });
  },
  getMyPhotos: () => api('/api/users/me/photos'),

  getMyCompetitions: () => api('/api/competitions/my'),
  createCompetition: (data) => api('/api/competitions/create', { method: 'POST', body: JSON.stringify(data) }),
  joinCompetition: (code) => api('/api/competitions/join', { method: 'POST', body: JSON.stringify({ invite_code: code }) }),
  getLeaderboard: (compId) => api(`/api/competitions/${compId}/leaderboard`),

  getWeeklyHeatmap: () => api('/api/heatmap/week'),
  getProgressTimeline: () => api('/api/heatmap/progress'),
  getCalendarData: (months = 6) => api(`/api/heatmap/calendar?months=${months}`),

  saveMetrics: (data) => api('/api/heatmap/metrics', { method: 'POST', body: JSON.stringify(data) }),
  getMetricsHistory: () => api('/api/heatmap/metrics'),
  getLatestMetrics: () => api('/api/heatmap/metrics/latest'),

  searchFood: (q) => api(`/api/nutrition/search?q=${encodeURIComponent(q)}`),
  logFood: (data) => api('/api/nutrition/log', { method: 'POST', body: JSON.stringify(data) }),
  deleteNutritionLog: (id) => api(`/api/nutrition/log/${id}`, { method: 'DELETE' }),
  getDailyNutrition: (date) => api(`/api/nutrition/daily/${date}`),
  getNutritionTargets: () => api('/api/nutrition/targets'),

  getExercise: (id) => api(`/api/exercises/${id}`),
  getExerciseByName: (name) => api(`/api/exercises/by-name/${encodeURIComponent(name)}`),
  logWeight: (data) => api('/api/exercises/log-weight', { method: 'POST', body: JSON.stringify(data) }),
  getWeightHistory: (name) => api(`/api/exercises/weight-history/${encodeURIComponent(name)}`),

  swapExercise: (taskId) => api(`/api/tasks/swap/${taskId}`, { method: 'POST' }),
  addCustomFood: (data) => api('/api/nutrition/custom-food', { method: 'POST', body: JSON.stringify(data) }),
  getHighlights: (compId) => api(`/api/competitions/${compId}/highlights`),

  getHealthToday: () => api('/api/health/today'),
  updateHealth: (data) => api('/api/health/update', { method: 'POST', body: JSON.stringify(data) }),
  patchWearable: (data) => api('/api/health/today', { method: 'PATCH', body: JSON.stringify(data) }),
  getHealthHistory: (days = 7) => api(`/api/health/history?days=${days}`),
  getReadiness: (date) => api(`/api/health/readiness/${date}`),
  getReadinessHistory: (days = 7) => api(`/api/health/readiness-history?days=${days}`),

  identifyFoodPhoto: (file) => {
    const form = new FormData();
    form.append('file', file);
    return api('/api/nutrition/identify-photo', { method: 'POST', body: form });
  },

  // Settings / Registration
  getRegistration: () => api('/api/users/registration'),
  updateRegistration: (data) => api('/api/users/registration', { method: 'PUT', body: JSON.stringify(data) }),
  regenerateWeek: () => api('/api/tasks/regenerate-week', { method: 'POST' }),

  // Subscription
  getSubStatus: () => api('/api/subscriptions/status'),
  startTrial: () => api('/api/subscriptions/start-trial', { method: 'POST' }),
  createStarsInvoice: () => api('/api/subscriptions/create-stars-invoice', { method: 'POST' }),

  // Feedback
  submitFeedback: (data) => api('/api/feedback', { method: 'POST', body: JSON.stringify(data) }),

  // Coach
  getCoachToday: () => api('/api/coach/today'),
  getCoachMessages: (limit = 50) => api(`/api/coach/messages?limit=${limit}`),
  sendCoachMessage: (body) => api('/api/coach/message', { method: 'POST', body: JSON.stringify({ body }) }),

  // Biological age
  getBioAge: () => api('/api/users/me/bio-age'),

  // Weekly AI review (Pro)
  getWeeklyReview: () => api('/api/coach/weekly-review'),

  // Apple Watch / wearable sync
  getShortcutToken: () => api('/api/users/me/shortcut-token'),
  wearableSync: (data) => api('/api/health/wearable-sync', { method: 'POST', body: JSON.stringify(data) }),

  // Barcode lookup
  lookupBarcode: (barcode) => api(`/api/nutrition/barcode/${encodeURIComponent(barcode)}`),

  // Body measurements
  logMeasurements: (entries) => api('/api/measurements/log', { method: 'POST', body: JSON.stringify({ entries }) }),
  getLatestMeasurements: () => api('/api/measurements/latest'),
  getMeasurementHistory: (key) => api(`/api/measurements/history/${encodeURIComponent(key)}`),
  deleteMeasurement: (id) => api(`/api/measurements/${id}`, { method: 'DELETE' }),

  // Account
  resetAccount: () => api('/api/users/reset-account', { method: 'POST' }),

  // Cycle tracking
  logPeriod: (data) => api('/api/health/cycle/log-period', { method: 'POST', body: JSON.stringify(data) }),
  getCyclePhase: () => api('/api/health/cycle/phase'),
};
