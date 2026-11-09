// Parse GPT's JSON, then turn each action item into a ClickUp task payload.
// ---- Configure for your workspace ----
const DEFAULT_LIST_ID = 'REPLACE_WITH_CLICKUP_LIST_ID';
// Attendee name (lower case) -> ClickUp user id. Find ids via GET /api/v2/team.
const TEAM = {
  'sara malik': 81234567,
  'omar farooq': 81234568,
  'liam smith': 81234569,
};
// --------------------------------------

const meeting = $('Validate Input').first().json;
const raw = $input.first().json.choices?.[0]?.message?.content;
let notes;
try {
  notes = JSON.parse(raw);
} catch (e) {
  throw new Error('Model did not return valid JSON: ' + String(raw).slice(0, 200));
}
for (const key of ['summary', 'decisions', 'action_items', 'risks']) {
  if (!(key in notes)) throw new Error('Model JSON is missing "' + key + '"');
}

const PRIORITY = { urgent: 1, high: 2, normal: 3, low: 4 };

// Match an owner to the team by full name, then by unique first name.
function clickupUser(owner) {
  if (!owner) return null;
  const name = owner.trim().toLowerCase();
  if (TEAM[name]) return TEAM[name];
  const first = name.split(/\s+/)[0];
  const matches = Object.keys(TEAM).filter((k) => k.split(/\s+/)[0] === first);
  return matches.length === 1 ? TEAM[matches[0]] : null;
}

function dueMs(date) {
  if (!date || !/^\d{4}-\d{2}-\d{2}$/.test(date)) return null;
  return Date.parse(date + 'T17:00:00Z');
}

const listId = meeting.clickup_list_id || DEFAULT_LIST_ID;
const items = notes.action_items
  .filter((a) => a && typeof a.task === 'string' && a.task.trim())
  .map((a) => {
    const assignee = clickupUser(a.owner);
    const due = dueMs(a.due_date);
    const task = {
      name: a.task.trim().slice(0, 200),
      description: 'From meeting "' + meeting.title + '" on ' + meeting.date + '.\n\n' +
        'Owner mentioned: ' + (a.owner || 'not assigned in the meeting') + '\n\nMeeting summary:\n' + notes.summary,
      priority: PRIORITY[a.priority] || 3,
      assignees: assignee ? [assignee] : [],
      tags: ['meeting-action'],
    };
    if (due) {
      task.due_date = due;
      task.due_date_time = false;
    }
    return { json: { list_id: listId, clickup_task: task, owner: a.owner || null, assigned: Boolean(assignee), notes } };
  });

if (items.length === 0) return [{ json: { skip: true, notes } }];
return items;
