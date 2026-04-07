const chatThread = document.getElementById('chat-thread');
const campaignMeta = document.getElementById('campaign-meta');
const statePanel = document.getElementById('state-panel');
const saveList = document.getElementById('save-list');
const imagePreview = document.getElementById('image-preview');
const statusLine = document.getElementById('status-line');
let selectedImageUrl = '';
let selectedSlot = 'autosave';

function setStatus(message, isError = false) {
  statusLine.textContent = message;
  statusLine.style.color = isError ? '#fca5a5' : '#cbd5e1';
}

function escapeHtml(input) {
  return String(input || '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;');
}

async function api(path, options = {}) {
  const response = await fetch(path, options);
  const data = await response.json().catch(() => ({ error: 'Invalid server response' }));
  if (!response.ok) throw new Error(data.error || `Request failed for ${path}`);
  return data;
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
  return ({ player: 'PLAYER', narrator: 'NARRATOR', npc: 'NPC', quest: 'QUEST', image: 'IMAGE', system: 'SYSTEM', error: 'ERROR' })[type] || 'SYSTEM';
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
  const data = await api('/api/campaign/messages');
  chatThread.innerHTML = '';
  const messages = data.messages || [];
  messages.forEach(renderMessage);
  const lastImage = [...messages].reverse().find((message) => message.image && message.image.url);
  if (lastImage && !selectedImageUrl) setImagePreview(lastImage.image.url, lastImage.text || 'Generated image');
}

async function refreshState() {
  const data = await api('/api/campaign/state');
  const state = data.state;
  selectedSlot = state.active_slot || selectedSlot;
  campaignMeta.textContent = `${state.campaign_name} • Slot ${selectedSlot} • Turn ${state.turn_count} • ${state.current_location_id}`;
  statePanel.textContent = [
    `Character: ${state.player.name} (${state.player.class})`,
    `HP: ${state.player.hp}/${state.player.max_hp}`,
    `Active enemy: ${state.active_enemy_id || 'none'}`,
    `Tone: ${state.settings.narration_tone} | Maturity: ${state.settings.content_settings.maturity_level}`,
    '',
    `Quest status: ${JSON.stringify(state.quest_status, null, 2)}`,
  ].join('\n');
  document.getElementById('image-enabled').checked = !!state.settings.image_generation_enabled;
}

async function refreshSaves() {
  const data = await api('/api/campaigns');
  saveList.innerHTML = '';
  for (const campaign of data.campaigns || []) {
    const btn = document.createElement('button');
    btn.textContent = `${campaign.slot} • ${campaign.campaign_name}`;
    btn.onclick = async () => {
      await api('/api/campaign/start', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ mode: 'load', slot: campaign.slot }) });
      selectedSlot = campaign.slot;
      selectedImageUrl = '';
      await Promise.all([refreshMessages(), refreshState(), refreshSaves()]);
      setStatus(`Loaded ${campaign.slot}`);
    };
    if (campaign.slot === selectedSlot) btn.style.borderColor = '#38bdf8';
    saveList.appendChild(btn);
  }
}

async function sendInput() {
  try {
    const input = document.getElementById('chat-input');
    const text = input.value.trim();
    if (!text) return;
    const turn = await api('/api/campaign/input', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text }) });
    input.value = '';
    await Promise.all([refreshMessages(), refreshState(), refreshSaves()]);
    const modelStatus = turn.metadata?.model_status;
    if (modelStatus && modelStatus.provider === 'ollama' && !modelStatus.ready) {
      setStatus(modelStatus.user_message || 'Ollama provider is unavailable.', true);
    } else {
      setStatus('Turn processed.');
    }
  } catch (error) {
    setStatus(error.message, true);
  }
}

async function generateImage() {
  try {
    const input = document.getElementById('chat-input').value.trim() || 'Fantasy tavern interior';
    const result = await api('/api/images/generate', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ workflow_id: 'scene_image', prompt: input }),
    });
    if (result.result_path) selectedImageUrl = '';
    await refreshMessages();
    setStatus(result.metadata?.fallback_reason ? `Image generated via fallback (${result.metadata.fallback_reason}).` : 'Image generated.');
  } catch (error) {
    imagePreview.textContent = error.message;
    setStatus(error.message, true);
  }
}

async function saveCampaign() {
  try {
    const slot = prompt('Save slot name:', selectedSlot) || selectedSlot;
    await api('/api/campaign/save', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ slot }) });
    selectedSlot = slot;
    await refreshSaves();
    setStatus(`Saved to ${slot}`);
  } catch (error) {
    setStatus(error.message, true);
  }
}

async function renameCampaign() {
  try {
    const newName = prompt('New campaign display name:');
    if (!newName) return;
    await api('/api/campaign/rename', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ slot: selectedSlot, new_name: newName }) });
    await Promise.all([refreshState(), refreshSaves()]);
    setStatus('Campaign renamed.');
  } catch (error) {
    setStatus(error.message, true);
  }
}

async function deleteCampaign() {
  try {
    const slot = prompt('Delete slot (must not be active):');
    if (!slot) return;
    await api('/api/campaign/delete', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ slot }) });
    await refreshSaves();
    setStatus(`Deleted ${slot}`);
  } catch (error) {
    setStatus(error.message, true);
  }
}

async function applySettings() {
  try {
    const modelProvider = document.getElementById('model-provider').value;
    const modelName = document.getElementById('model-name').value.trim() || 'llama3';
    const imageProvider = document.getElementById('image-provider').value;
    const campaignImageEnabled = document.getElementById('image-enabled').checked;
    const settings = await api('/api/settings/global', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model: { provider: modelProvider, model_name: modelName }, image: { provider: imageProvider } }),
    });
    await api('/api/settings/campaign', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ image_generation_enabled: campaignImageEnabled }),
    });
    const modelStatus = settings.settings?.model_status;
    if (modelStatus && modelStatus.provider === 'ollama' && !modelStatus.ready) {
      setStatus(modelStatus.user_message || 'Ollama provider is unavailable.', true);
    } else {
      setStatus('Settings applied.');
    }
  } catch (error) {
    setStatus(error.message, true);
  }
}

async function loadSettings() {
  const data = await api('/api/settings/global');
  document.getElementById('model-provider').value = data.settings.model.provider;
  document.getElementById('model-name').value = data.settings.model.model_name;
  document.getElementById('image-provider').value = data.settings.image.provider;
  const modelStatus = data.settings.model_status;
  if (modelStatus && modelStatus.provider === 'ollama' && !modelStatus.ready) {
    setStatus(modelStatus.user_message || 'Ollama provider is unavailable.', true);
  }
}

document.getElementById('send-btn').onclick = sendInput;
document.getElementById('chat-input').addEventListener('keydown', (e) => { if (e.key === 'Enter') sendInput(); });
document.getElementById('load-autosave').onclick = async () => {
  try {
    await api('/api/campaign/start', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ mode: 'load', slot: 'autosave' }) });
    selectedImageUrl = '';
    imagePreview.textContent = 'Click an inline image to preview it here.';
    await Promise.all([refreshMessages(), refreshState(), refreshSaves()]);
    setStatus('Autosave loaded.');
  } catch (error) { setStatus(error.message, true); }
};
document.getElementById('new-campaign').onclick = async () => {
  try {
    await api('/api/campaign/start', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode: 'new', player_name: 'Aria', char_class: 'Ranger', profile: 'classic_fantasy' }),
    });
    selectedImageUrl = '';
    imagePreview.textContent = 'Click an inline image to preview it here.';
    await Promise.all([refreshMessages(), refreshState(), refreshSaves()]);
    setStatus('New campaign started.');
  } catch (error) { setStatus(error.message, true); }
};
document.getElementById('gen-image-btn').onclick = generateImage;
document.getElementById('save-campaign').onclick = saveCampaign;
document.getElementById('rename-campaign').onclick = renameCampaign;
document.getElementById('delete-campaign').onclick = deleteCampaign;
document.getElementById('save-settings').onclick = applySettings;

Promise.all([refreshMessages(), refreshState(), refreshSaves(), loadSettings()]).catch((error) => setStatus(error.message, true));
