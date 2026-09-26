const state = { busy: false };
const $ = (selector) => document.querySelector(selector);
const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[char]));

async function jsonRequest(path, options = {}) {
  const response = await fetch(path, { headers: {'Content-Type':'application/json'}, ...options });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
  return data;
}

function renderTimeline(data) {
  $('#stream-name').textContent = data.stream_id;
  $('#event-count').textContent = data.event_count;
  $('#delivery-count').textContent = data.deliveries.length;
  $('#replay-count').textContent = data.replay.count || 0;
  const timeline = $('#timeline');
  if (!data.events.length) {
    timeline.className = 'timeline empty-timeline';
    timeline.innerHTML = '<div class="empty-state"><span class="empty-icon">⌁</span><b>No events yet</b><span>Publish an action above to start the stream.</span></div>';
  } else {
    timeline.className = 'timeline';
    timeline.innerHTML = [...data.events].reverse().map((event) => `
      <div class="event-row">
        <span class="event-dot ${event.action === 'fail' ? 'fail' : ''}"></span>
        <div class="event-main"><strong>${esc(event.label)}</strong><small>${esc(event.actor_id)} · ${esc(event.note || 'no note')} · ${esc(event.event_id).slice(0, 8)}</small></div>
        <div class="event-meta"><code>#${esc(event.sequence_number ?? '?')} · v${esc(event.version)}</code><small>${esc(event.delivery_status)}</small></div>
      </div>`).join('');
  }
  const deliveries = $('#deliveries');
  deliveries.innerHTML = data.deliveries.length ? [...data.deliveries].reverse().map((item) => `
    <div class="log-item"><i class="tiny-dot"></i><div><b>${esc(item.action)} → projection</b><span>sequence #${esc(item.sequence_number)} · ${esc(item.event_id).slice(0, 8)}</span></div></div>`).join('') : '<div class="muted">No deliveries yet.</div>';
  const failures = $('#failures');
  failures.innerHTML = data.handler_failures.length ? [...data.handler_failures].reverse().map((item) => `
    <div class="log-item fail"><i class="tiny-dot"></i><div><b>failure probe · ${esc(item.attempts)} attempts</b><span>${esc(item.message)} · ${esc(item.event_id).slice(0, 8)}</span></div></div>`).join('') : '<div class="muted">No handler failures. Try “Simulate failure”.</div>';
  $('#last-replay').textContent = data.replay.count ? `${data.replay.count} events · ${data.replay.order.join(' → ')}` : 'No replay yet';
}

async function refresh() {
  try {
    renderTimeline(await jsonRequest('api/events'));
    await health();
  } catch (error) { showResult(`Could not read timeline: ${error.message}`, true); }
}

function showResult(message, warning = false) {
  const node = $('#publish-result');
  node.className = `result ${warning ? 'warning' : 'success'}`;
  node.textContent = message;
}

async function publish(action) {
  if (state.busy) return;
  state.busy = true;
  document.querySelectorAll('.action').forEach((button) => { button.disabled = true; });
  try {
    const data = await jsonRequest('api/events/publish', { method:'POST', body:JSON.stringify({ action, actor:$('#actor').value, note:$('#note').value }) });
    if (!data.ok) throw new Error(data.error || 'The event was rejected');
    const failure = data.handler_failures.length ? ` Handler probe reported ${data.handler_failures[0].attempts} attempts.` : '';
    showResult(`✓ ${data.result.status} · sequence #${data.event.sequence_number} · stream version ${data.stream_version}.${failure}`, Boolean(failure));
    $('#note').value = '';
    renderTimeline(await jsonRequest('api/events'));
    await health();
  } catch (error) { showResult(`Could not publish: ${error.message}`, true); }
  state.busy = false;
  document.querySelectorAll('.action').forEach((button) => { button.disabled = false; });
}

async function replay() {
  const button = $('#replay-button');
  button.disabled = true;
  try {
    const data = await jsonRequest('api/events/replay', { method:'POST' });
    renderTimeline(data);
    showResult(`↺ Replayed ${data.replay.count} stored event${data.replay.count === 1 ? '' : 's'} in package-defined order.`);
  } catch (error) { showResult(`Could not replay: ${error.message}`, true); }
  button.disabled = false;
}

async function health() {
  try {
    const data = await jsonRequest('api/events/health');
    const healthy = data.status === 'ok';
    const dispatchErrors = data.components?.event_bus?.details?.dispatch_error_count ?? 0;
    $('#health-status').textContent = data.status;
    $('#health-status').style.color = healthy ? 'var(--green)' : 'var(--red)';
    $('#health-backend').textContent = `${data.event_store} · ${dispatchErrors} dispatch error${dispatchErrors === 1 ? '' : 's'} · offline`;
  } catch (_) {
    $('#health-status').textContent = 'unhealthy';
    $('#health-status').style.color = 'var(--red)';
  }
}

document.querySelectorAll('.action').forEach((button) => button.addEventListener('click', () => publish(button.dataset.action)));
$('#replay-button').addEventListener('click', replay);
$('#refresh-button').addEventListener('click', refresh);
refresh();
