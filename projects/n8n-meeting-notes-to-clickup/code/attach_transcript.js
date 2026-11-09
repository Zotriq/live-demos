// Whisper returns { text }. Merge it back into the validated meeting.
const meeting = $('Validate Input').first().json;
const text = ($input.first().json.text || '').trim();
if (!text) throw new Error('Transcription returned no text');
return [{ json: { ...meeting, transcript: text } }];
