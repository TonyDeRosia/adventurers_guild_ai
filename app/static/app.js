const chatThread = document.getElementById('chat-thread');
const campaignMeta = document.getElementById('campaign-meta');
const statePanel = document.getElementById('state-panel');
const saveList = document.getElementById('save-list');
const imagePreview = document.getElementById('image-preview');

function escapeHtml(input) {
  return input
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;');
}

function renderMessage(msg) {
  const el = document.createElement('div');
  el.className = `msg msg-${msg.type}`;
  const ts = new Date(msg.timestamp).toLocaleTimeString();
  el.innerHTML = `<small>${msg.type.toUpperCase()} • ${ts}</small>${escapeHtml(msg.text || '')}`;
  if (msg.image && msg.image.result_path) {
    const img = document.createElement('img');
    img.src = msg.image.result_path;
    img.alt = 'generated';
    el.appendChild(img);
  }
  chatThread.appendChild(el);
  chatThread.scrollTop = chatThread.scrollHeight;
}

async function refreshMessages() {
  const data = await fetch('/api/campaign/messages').then((r) => r.json());
  chatThread.innerHTML = '';
  (data.messages || []).forEach(renderMessage);
}

async function refreshState() {
  const data = await fetch('/api/campaign/state').then((r) => r.json());
  const state = data.state;
  campaignMeta.textContent = `${state.campaign_name} • Turn ${state.turn_count} • ${state.current_location_id}`;
  statePanel.textContent = JSON.stringify(state, null, 2);
}

async function refreshSaves() {
  const data = await fetch('/api/campaign/saves').then((r) => r.json());
  saveList.innerHTML = '';
  for (const slot of data.saves || []) {
    const btn = document.createElement('button');
    btn.textContent = slot;
    btn.onclick = async () => {
      await fetch('/api/campaign/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode: 'load', slot }),
      });
      await Promise.all([refreshMessages(), refreshState(), refreshSaves()]);
    };
    saveList.appendChild(btn);
  }
}

async function sendInput() {
  const input = document.getElementById('chat-input');
  const text = input.value.trim();
  if (!text) return;
  await fetch('/api/campaign/input', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
  });
  input.value = '';
  await Promise.all([refreshMessages(), refreshState()]);
}

async function generateImage() {
  const input = document.getElementById('chat-input').value.trim() || 'Fantasy tavern interior';
  const result = await fetch('/api/images/generate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ workflow_id: 'scene_image', prompt: input }),
  }).then((r) => r.json());

  imagePreview.textContent = JSON.stringify(result, null, 2);
  await refreshMessages();
}

document.getElementById('send-btn').onclick = sendInput;
document.getElementById('chat-input').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') sendInput();
});

document.getElementById('load-autosave').onclick = async () => {
  await fetch('/api/campaign/start', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ mode: 'load', slot: 'autosave' }),
  });
  await Promise.all([refreshMessages(), refreshState(), refreshSaves()]);
};

document.getElementById('new-campaign').onclick = async () => {
  await fetch('/api/campaign/start', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ mode: 'new', player_name: 'Aria', char_class: 'Ranger', profile: 'classic_fantasy' }),
  });
  await Promise.all([refreshMessages(), refreshState(), refreshSaves()]);
};

document.getElementById('gen-image-btn').onclick = generateImage;

Promise.all([refreshMessages(), refreshState(), refreshSaves()]);
