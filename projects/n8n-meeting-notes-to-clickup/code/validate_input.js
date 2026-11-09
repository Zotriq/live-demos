// Validate the webhook body and normalise it.
// Accepts: { title, date?, attendees: [{ name, email? } | "Name"], transcript? , audio_url?, clickup_list_id? }
const body = $input.first().json.body || $input.first().json;
const str = (v) => (typeof v === 'string' ? v.trim() : '');

const attendees = (Array.isArray(body.attendees) ? body.attendees : [])
  .map((a) => (typeof a === 'string' ? { name: a.trim() } : { name: str(a.name), email: str(a.email).toLowerCase() }))
  .filter((a) => a.name);

const meeting = {
  title: str(body.title) || 'Untitled meeting',
  date: /^\d{4}-\d{2}-\d{2}$/.test(str(body.date)) ? str(body.date) : $now.toISODate(),
  attendees,
  transcript: str(body.transcript),
  audio_url: str(body.audio_url),
  clickup_list_id: str(body.clickup_list_id),
};

const errors = [];
if (!meeting.transcript && !/^https:\/\//.test(meeting.audio_url)) errors.push('send a transcript or an https audio_url');
if (meeting.transcript && meeting.transcript.length < 50) errors.push('transcript is too short');
if (attendees.length === 0) errors.push('attendees are required so tasks can be assigned');
if (errors.length) throw new Error('Invalid meeting payload: ' + errors.join('; '));

return [{ json: meeting }];
