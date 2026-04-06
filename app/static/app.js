const chatThread = document.getElementById('chat-thread');
const campaignMeta = document.getElementById('campaign-meta');
const statePanel = document.getElementById('state-panel');
const saveList = document.getElementById('save-list');
const imagePreview = document.getElementById('image-preview');
let selectedImageUrl = '';

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
  el.innerHTML = `<small>${labelForType(msg.type)} • ${ts}</small>${escapeHtml(msg.text || '')}`;
  if (msg.image && msg.image.url) {
    const img = document.createElement('img');
    img.src = msg.image.url;
    img.alt = 'generated';
    img.onclick = () => setImagePreview(msg.image.url, msg.text || 'Generated image');
    el.appendChild(img);
  }
  chatThread.appendChild(el);
  chatThread.scrollTop = chatThread.scrollHeight;
}

function labelForType(type) {
  const labels = {
    player: 'PLAYER',
    narrator: 'NARRATOR',
    npc: 'NPC',
    quest: 'QUEST',
    image: 'IMAGE',
    system: 'SYSTEM',
  };
  return labels[type] || 'SYSTEM';
}

function setImagePreview(url, caption = '') {
  selectedImageUrl = url;
  imagePreview.innerHTML = '';
  const img = document.createElement('img');
  img.src = url;
  img.alt = caption || 'Generated image preview';
  const text = document.createElement('div');
  text.textContent = caption || 'Generated image preview';
  imagePreview.appendChild(img);
  imagePreview.appendChild(text);
}

async function refreshMessages() {
  const data = await fetch('/api/campaign/messages').then((r) => r.json());
  chatThread.innerHTML = '';
  const messages = data.messages || [];
  messages.forEach(renderMessage);
  const lastImage = [...messages].reverse().find((message) => message.image && message.image.url);
  if (lastImage && !selectedImageUrl) {
    setImagePreview(lastImage.image.url, lastImage.text || 'Generated image');
  }
}

async function refreshState() {
  const data = await fetch('/api/campaign/state').then((r) => r.json());
  const state = data.state;
  campaignMeta.textContent = `${state.campaign_name} • Turn ${state.turn_count} • ${state.current_location_id}`;
  statePanel.textContent = [
    `Character: ${state.player.name} (${state.player.class})`,
    `HP: ${state.player.hp}/${state.player.max_hp}`,
    `Active enemy: ${state.active_enemy_id || 'none'}`,
    '',
    `Quest status: ${JSON.stringify(state.quest_status, null, 2)}`,
    '',
    `Inventory/Progress details and richer summaries can be expanded here.`,
  ].join('\n');
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
  const response = await fetch('/api/images/generate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ workflow_id: 'scene_image', prompt: input }),
  });
  const result = await response.json();

  if (response.ok && result.result_path) {
    selectedImageUrl = '';
  } else {
    imagePreview.textContent = result.error || 'Image generation failed.';
  }
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
  selectedImageUrl = '';
  imagePreview.textContent = 'Click an inline image to preview it here.';
  await Promise.all([refreshMessages(), refreshState(), refreshSaves()]);
};

document.getElementById('new-campaign').onclick = async () => {
  await fetch('/api/campaign/start', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ mode: 'new', player_name: 'Aria', char_class: 'Ranger', profile: 'classic_fantasy' }),
  });
  selectedImageUrl = '';
  imagePreview.textContent = 'Click an inline image to preview it here.';
  await Promise.all([refreshMessages(), refreshState(), refreshSaves()]);
};

document.getElementById('gen-image-btn').onclick = generateImage;

Promise.all([refreshMessages(), refreshState(), refreshSaves()]);
