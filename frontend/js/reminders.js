// ─── REMINDERS (Settings) ─────────────────────────────────────────────────────
// Frontend for backend/routers/reminders.py. The backend keeps at most ONE row per
// type per user; GET /api/reminders/ returns EVERY known type pre-filled with the
// user's current settings (id=null, is_active=false when never configured), so the
// whole list renders from a single call. Activating a reminder is an upsert (POST)
// and deactivating deletes the row. We always send the *device* timezone offset so
// the scheduler (deliver_due_reminders) fires each reminder at the user's local
// time — matching the offset convention used for setTimezone() in core.js.

// Minutes EAST of UTC. JS getTimezoneOffset() is minutes BEHIND UTC, so negate.
function _reminderTzOffset() {
  return -new Date().getTimezoneOffset();
}

// Labels come from the server's fixed REMINDER_TYPES, but escape defensively.
function _escReminder(s) {
  return String(s ?? '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function _reminderRow(type) {
  return document.querySelector(`.reminder-row[data-type="${type}"]`);
}

async function loadReminders() {
  const listEl = document.getElementById('remindersList');
  if (!listEl) return;
  try {
    const reminders = await API.getReminders();
    _renderReminders(reminders);
  } catch (e) {
    listEl.innerHTML = '<div class="reminders-empty">Couldn\'t load reminders.</div>';
  }
}

function _renderReminders(reminders) {
  const listEl = document.getElementById('remindersList');
  if (!listEl) return;
  if (!Array.isArray(reminders) || reminders.length === 0) {
    listEl.innerHTML = '<div class="reminders-empty">No reminders available.</div>';
    return;
  }
  listEl.innerHTML = reminders.map(r => {
    const type = _escReminder(r.reminder_type);
    return `
    <div class="reminder-row" data-type="${type}" data-id="${r.id ?? ''}">
      <span class="reminder-emoji">${_escReminder(r.emoji)}</span>
      <span class="reminder-label">${_escReminder(r.label)}</span>
      <input type="time" class="reminder-time" value="${_escReminder(r.time_hhmm)}"
             onchange="onReminderTimeChange('${type}', this.value)">
      <label class="reminder-toggle">
        <input type="checkbox" ${r.is_active ? 'checked' : ''}
               onchange="onReminderToggle('${type}', this.checked)">
        <span class="reminder-track"></span>
      </label>
    </div>`;
  }).join('');
}

// Activate (POST upsert) or deactivate (DELETE) the reminder for this type.
async function onReminderToggle(type, isActive) {
  const row = _reminderRow(type);
  if (!row) return;
  const time = row.querySelector('.reminder-time')?.value || '08:00';
  try {
    if (isActive) {
      const res = await createReminder(type, time);
      if (res && res.id) row.dataset.id = res.id;
      showToast('Reminder on');
    } else {
      await deleteReminder(type);
      row.dataset.id = '';
      showToast('Reminder off');
    }
    haptic('selection');
  } catch (e) {
    showToast('Could not update reminder');
    // Revert the toggle so the UI reflects the server's truth.
    const cb = row.querySelector('.reminder-toggle input');
    if (cb) cb.checked = !isActive;
  }
}

// Changing the time only persists when the reminder is already active; otherwise
// it's saved when the user toggles it on.
async function onReminderTimeChange(type, time) {
  const row = _reminderRow(type);
  if (!row) return;
  const active = row.querySelector('.reminder-toggle input')?.checked;
  if (!active) return;
  try {
    const res = await createReminder(type, time);
    if (res && res.id) row.dataset.id = res.id;
    showToast('Reminder updated');
  } catch (e) {
    showToast('Could not update reminder');
  }
}

// Upsert — POST creates or updates the single row for this type, always with the
// device timezone offset so it fires at the user's local time.
function createReminder(type, time) {
  return API.createReminder({
    reminder_type: type,
    time_hhmm: time,
    timezone_offset: _reminderTzOffset(),
  });
}

async function deleteReminder(type) {
  const row = _reminderRow(type);
  const id = row?.dataset.id;
  if (!id) return; // nothing persisted yet
  await API.deleteReminder(id);
}
