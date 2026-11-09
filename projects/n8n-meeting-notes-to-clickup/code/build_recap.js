// Build the Slack recap from the notes and the tasks ClickUp created.
const parsed = $('Parse & Map Owners').all().map((i) => i.json);
const notes = parsed[0].notes;
const meeting = $('Validate Input').first().json;
const created = $input.all().map((i) => i.json).filter((t) => t && t.id && t.url);

const lines = [];
lines.push('*:memo: ' + meeting.title + '* (' + meeting.date + ')');
lines.push(notes.summary);

if (notes.decisions.length) {
  lines.push('', '*Decisions*');
  notes.decisions.forEach((d) => lines.push('• ' + d));
}

const tasks = parsed.filter((p) => !p.skip);
if (tasks.length) {
  lines.push('', '*Action items*');
  tasks.forEach((p, i) => {
    const link = created[i] ? '<' + created[i].url + '|' + p.clickup_task.name + '>' : p.clickup_task.name;
    const who = p.owner ? (p.assigned ? p.owner : p.owner + ' :warning: not in ClickUp') : ':warning: no owner';
    const due = p.clickup_task.due_date ? ' · due ' + new Date(p.clickup_task.due_date).toISOString().slice(0, 10) : '';
    lines.push('• ' + link + ' (' + who + due + ')');
  });
} else {
  lines.push('', '_No action items were agreed._');
}

if (notes.risks.length) {
  lines.push('', '*Risks / open questions*');
  notes.risks.forEach((r) => lines.push('• ' + r));
}

return [{ json: { slack_text: lines.join('\n'), tasks_created: created.length } }];
