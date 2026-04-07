const chatThread = document.getElementById('chat-thread');
const campaignMeta = document.getElementById('campaign-meta');
const statePanel = document.getElementById('state-panel');
const saveList = document.getElementById('save-list');
const imagePreview = document.getElementById('image-preview');
const statusLine = document.getElementById('status-line');
const readinessPanel = document.getElementById('dependency-readiness');
const setupGuidance = document.getElementById('setup-guidance');
const selectedSaveLabel = document.getElementById('selected-save-label');
const newCampaignModal = document.getElementById('new-campaign-modal');

let selectedImageUrl = '';
let selectedSlot = 'autosave';
let loadedSlot = 'autosave';
let selectedCampaignName = 'autosave';
let deletingCampaign = false;
let lastCampaigns = [];

const readinessLabels = {
  model_provider: 'Text Generation Service',
  selected_model: 'Story Model',
  image_provider: 'Image Generation Service',
};

function commandFromAction(actionText) {
  const clean = String(actionText || '').trim();
  if (clean.startsWith('Run: ')) return clean.slice(5).trim();
  if (clean.includes('ollama serve')) return 'ollama serve';
  if (clean.includes('ollama pull')) {
    const match = clean.match(/ollama pull\s+([\w.:-]+)/);
    return match ? `ollama pull ${match[1]}` : 'ollama pull llama3';
  }
  return '';
}

async function runReadinessAction(actionId, item) {
  try {
    if (actionId === 'recheck') {
      await refreshDependencyReadiness();
      setStatus('Dependency readiness refreshed.');
      return;
    }
    if (actionId === 'start_ollama') {
      setStatus('Starting Ollama...');
      console.log('[setup-action] start-ollama requested');
      const result = await api('/api/setup/start-ollama', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({}),
      });
      console.log(`[setup-action] start-ollama ${result.ok ? 'success' : 'failure'} reason=${result.message || 'unknown'}`);
      await refreshDependencyReadiness();
      console.log('[setup-action] readiness refresh triggered');
      setStatus(result.ok ? (result.message || 'Ollama start request sent.') : (result.next_step ? `${result.message} ${result.next_step}` : result.message), !result.ok);
      return;
    }
    if (actionId === 'install_ollama') {
      setStatus('Installing Ollama... This can take a few minutes.');
      console.log('[setup-action] install-ollama requested');
      const result = await api('/api/setup/install-ollama', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({}),
      });
      console.log(`[setup-action] install-ollama ${result.ok ? 'success' : 'failure'} reason=${result.message || 'unknown'}`);
      await refreshDependencyReadiness();
      console.log('[setup-action] readiness refresh triggered');
      setStatus(result.ok ? (result.message || 'Ollama installed.') : (result.next_step ? `${result.message} ${result.next_step}` : result.message), !result.ok);
      return;
    }
    if (actionId === 'install_model') {
      const modelName = item.selected_model || document.getElementById('model-name').value.trim() || 'llama3';
      setStatus(`Installing model ${modelName}... This can take a while.`);
      console.log(`[setup-action] install-model requested model=${modelName}`);
      const result = await api('/api/setup/install-model', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ model: modelName }),
      });
      console.log(`[setup-action] install-model ${result.ok ? 'success' : 'failure'} reason=${result.message || 'unknown'} model=${modelName}`);
      await refreshDependencyReadiness();
      console.log('[setup-action] readiness refresh triggered');
      setStatus(result.ok ? (result.message || `Installed ${modelName}.`) : (result.next_step ? `${result.message} ${result.next_step}` : result.message), !result.ok);
    }
  } catch (error) {
    setStatus(error.message, true);
  }
}

async function copyCommand(command) {
  try {
    await navigator.clipboard.writeText(command);
    setStatus(`Copied command: ${command}`);
  } catch (error) {
    setStatus(`Copy failed. Command: ${command}`, true);
  }
}

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

function updateSelectedSaveLabel() {
  if (!selectedSlot) {
    selectedSaveLabel.textContent = 'Selected save: none';
    return;
  }
  selectedSaveLabel.textContent = `Selected save: ${selectedSlot}${selectedCampaignName ? ` • ${selectedCampaignName}` : ''}`;
}

function openNewCampaignModal() {
  newCampaignModal.classList.remove('hidden');
}

function closeNewCampaignModal() {
  newCampaignModal.classList.add('hidden');
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
  loadedSlot = state.active_slot || loadedSlot;
  selectedSlot = state.active_slot || selectedSlot;
  selectedCampaignName = state.campaign_name;
  const world = state.world_meta || {};
  campaignMeta.textContent = `${state.campaign_name} • ${world.world_name || 'Moonfall'} • Slot ${loadedSlot} • Turn ${state.turn_count} • ${state.current_location_id}`;
  statePanel.textContent = [
    `Character: ${state.player.name} (${state.player.class})`,
    `HP: ${state.player.hp}/${state.player.max_hp}`,
    `World: ${world.world_name || 'Moonfall'} (${world.world_theme || 'classic fantasy'})`,
    `Starting location: ${world.starting_location_name || state.current_location_id}`,
    `Tone: ${world.tone || state.settings.narration_tone} | Maturity: ${state.settings.content_settings.maturity_level}`,
    `Premise: ${world.premise || 'not specified'}`,
    `Player concept: ${world.player_concept || 'not specified'}`,
    '',
    `Quest status: ${JSON.stringify(state.quest_status, null, 2)}`,
  ].join('\n');
  document.getElementById('image-enabled').checked = !!state.settings.image_generation_enabled;
  updateSelectedSaveLabel();
}

async function loadSelectedCampaign() {
  if (!selectedSlot) {
    setStatus('Select a save before loading.', true);
    return;
  }
  try {
    await api('/api/campaign/start', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ mode: 'load', slot: selectedSlot }),
    });
    selectedImageUrl = '';
    await Promise.all([refreshMessages(), refreshState(), refreshSaves()]);
    setStatus(`Loaded ${selectedSlot}.`);
  } catch (error) {
    setStatus(error.message, true);
  }
}

async function refreshSaves() {
  const data = await api('/api/campaigns');
  saveList.innerHTML = '';
  const campaigns = data.campaigns || [];
  lastCampaigns = campaigns;
  if (!campaigns.length) {
    selectedSlot = '';
    selectedCampaignName = '';
    updateSelectedSaveLabel();
    saveList.textContent = 'No saves found yet.';
    return;
  }
  if (!campaigns.some((campaign) => campaign.slot === selectedSlot)) {
    selectedSlot = loadedSlot;
  }
  campaigns.forEach((campaign) => {
    const btn = document.createElement('button');
    btn.className = `save-item ${campaign.slot === selectedSlot ? 'selected' : ''}`;
    btn.innerHTML = `${escapeHtml(campaign.slot)} • ${escapeHtml(campaign.campaign_name)}<small>${escapeHtml(campaign.world_name || 'Unknown world')} • Turn ${campaign.turn_count}</small>`;
    btn.onclick = () => {
      selectedSlot = campaign.slot;
      selectedCampaignName = campaign.campaign_name;
      updateSelectedSaveLabel();
      refreshSaves();
    };
    btn.ondblclick = () => {
      selectedSlot = campaign.slot;
      selectedCampaignName = campaign.campaign_name;
      loadSelectedCampaign();
    };
    saveList.appendChild(btn);
  });
  updateSelectedSaveLabel();
}

function renderDependencyReadiness(payload) {
  readinessPanel.innerHTML = '';
  const summary = document.createElement('div');
  summary.className = 'readiness-summary';
  const byType = Object.fromEntries((payload.items || []).map((item) => [item.provider_type, item]));
  summary.innerHTML = `
    <div>Text generation: ${byType.model_provider?.status_level === 'ready' ? 'ready' : 'not ready'}</div>
    <div>Story model: ${byType.selected_model?.status_level === 'ready' ? 'installed' : 'not installed'}</div>
    <div>Image generation: ${byType.image_provider?.status_level === 'ready' ? 'ready' : 'not ready'}</div>
    <div>Fallback story mode: available</div>
  `;
  readinessPanel.appendChild(summary);

  for (const item of payload.items || []) {
    const el = document.createElement('div');
    el.className = 'readiness-item';
    const ready = item.status_level === 'ready';
    const badgeClass = ready ? 'ready-badge' : 'not-ready-badge';
    const title = readinessLabels[item.provider_type] || item.provider_type;
    const selectedModel = item.selected_model ? `<div>Selected model: <code>${escapeHtml(item.selected_model)}</code></div>` : '';
    const command = commandFromAction(item.next_action);
    const copyButton = command ? `<button class="copy-cmd-btn" data-command="${escapeHtml(command)}">Copy command</button>` : '';
    const actionButtons = (item.actions || [])
      .map((action) => `<button class="readiness-action-btn" data-action="${escapeHtml(action.id)}">${escapeHtml(action.label)}</button>`)
      .join('');
    el.innerHTML = `
      <strong>${escapeHtml(title)}</strong>
      <div>Provider: <code>${escapeHtml(item.provider)}</code></div>
      <div class="${badgeClass}">${ready ? 'Ready' : 'Not ready'}</div>
      ${selectedModel}
      <div>${escapeHtml(item.user_message || '')}</div>
      <div>Next step: ${escapeHtml(item.next_action || 'No action needed.')}</div>
      <div class="readiness-action-row">${actionButtons}${copyButton}</div>
    `;
    const btn = el.querySelector('.copy-cmd-btn');
    if (btn && command) {
      btn.onclick = () => copyCommand(command);
    }
    el.querySelectorAll('.readiness-action-btn').forEach((button) => {
      button.onclick = () => runReadinessAction(button.dataset.action, item);
    });
    readinessPanel.appendChild(el);
  }

  setupGuidance.innerHTML = '';
  const setupLines = payload.setup_checklist || payload.setup_guidance || [];
  for (const line of setupLines) {
    const li = document.createElement('li');
    li.textContent = line;
    setupGuidance.appendChild(li);
  }
}

async function refreshDependencyReadiness() {
  const payload = await api('/api/providers/readiness');
  renderDependencyReadiness(payload);
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
    const slot = (prompt('Save slot name:', selectedSlot) || selectedSlot || '').trim();
    if (!slot) {
      setStatus('Save cancelled: slot is required.', true);
      return;
    }
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
    if (!selectedSlot) {
      setStatus('Select a save before renaming.', true);
      return;
    }
    const newName = prompt(`New campaign name for ${selectedSlot}:`);
    if (!newName) return;
    await api('/api/campaign/rename', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ slot: selectedSlot, new_name: newName }) });
    await Promise.all([refreshState(), refreshSaves()]);
    setStatus(`Renamed ${selectedSlot}.`);
  } catch (error) {
    setStatus(error.message, true);
  }
}

async function deleteCampaign() {
  try {
    if (deletingCampaign) {
      setStatus('Delete already in progress.');
      return;
    }
    if (!selectedSlot) {
      setStatus('No save is selected for deletion.', true);
      return;
    }
    const selectedCampaign = lastCampaigns.find((campaign) => campaign.slot === selectedSlot);
    if (!selectedCampaign) {
      selectedSlot = '';
      selectedCampaignName = '';
      updateSelectedSaveLabel();
      setStatus('No valid selected save to delete.', true);
      await refreshSaves();
      return;
    }
    if (selectedSlot === loadedSlot) {
      setStatus('Cannot delete the active save. Load another save first.', true);
      return;
    }
    const confirmation = prompt(`Type DELETE to remove '${selectedCampaign.campaign_name}' (${selectedSlot}). This cannot be undone.`);
    if (confirmation !== 'DELETE') {
      setStatus('Delete cancelled.');
      return;
    }
    deletingCampaign = true;
    const deletedSlot = selectedSlot;
    const deletedName = selectedCampaign.campaign_name;
    selectedSlot = '';
    selectedCampaignName = '';
    updateSelectedSaveLabel();
    await api('/api/campaign/delete', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ slot: deletedSlot }) });
    const remaining = lastCampaigns.filter((campaign) => campaign.slot !== deletedSlot);
    lastCampaigns = remaining;
    const nextChoice = remaining.find((campaign) => campaign.slot === loadedSlot) || remaining[0] || null;
    selectedSlot = nextChoice ? nextChoice.slot : '';
    selectedCampaignName = nextChoice ? nextChoice.campaign_name : '';
    updateSelectedSaveLabel();
    await refreshSaves();
    setStatus(`Deleted ${deletedName} (${deletedSlot}).`);
  } catch (error) {
    setStatus(error.message, true);
  } finally {
    deletingCampaign = false;
  }
}

async function createCampaignFromForm() {
  try {
    const tone = document.getElementById('form-tone').value.trim() || 'heroic';
    const playerName = document.getElementById('form-player-name').value.trim() || 'Aria';
    const playerClass = document.getElementById('form-player-class').value.trim() || 'Ranger';
    const worldTheme = document.getElementById('form-world-theme').value.trim() || 'classic fantasy';
    const payload = {
      mode: 'new',
      campaign_name: document.getElementById('form-campaign-name').value.trim() || `${playerName}'s Campaign`,
      world_name: document.getElementById('form-world-name').value.trim() || 'Moonfall',
      world_theme: worldTheme,
      starting_location_name: document.getElementById('form-starting-location').value.trim() || 'Moonfall Town',
      campaign_tone: tone,
      premise: document.getElementById('form-premise').value.trim(),
      player_concept: document.getElementById('form-player-concept').value.trim(),
      player_name: playerName,
      char_class: playerClass,
      profile: worldTheme.toLowerCase().includes('dark') ? 'dark_fantasy' : 'classic_fantasy',
      thematic_flags: worldTheme ? [worldTheme.toLowerCase().replaceAll(' ', '_'), 'adventure'] : ['adventure', 'mystery'],
    };
    await api('/api/campaign/start', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
    });
    selectedImageUrl = '';
    imagePreview.textContent = 'Click an inline image to preview it here.';
    closeNewCampaignModal();
    await Promise.all([refreshMessages(), refreshState(), refreshSaves()]);
    setStatus('New campaign started.');
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
    await refreshDependencyReadiness();
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
  renderDependencyReadiness(data.settings?.dependency_readiness || { items: [], setup_guidance: [] });
}

document.getElementById('send-btn').onclick = sendInput;
document.getElementById('chat-input').addEventListener('keydown', (e) => { if (e.key === 'Enter') sendInput(); });
document.getElementById('load-selected').onclick = loadSelectedCampaign;
document.getElementById('load-autosave').onclick = async () => {
  try {
    await api('/api/campaign/start', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ mode: 'load', slot: 'autosave' }) });
    selectedSlot = 'autosave';
    selectedCampaignName = 'autosave';
    selectedImageUrl = '';
    imagePreview.textContent = 'Click an inline image to preview it here.';
    await Promise.all([refreshMessages(), refreshState(), refreshSaves()]);
    setStatus('Autosave loaded.');
  } catch (error) { setStatus(error.message, true); }
};
document.getElementById('new-campaign').onclick = openNewCampaignModal;
document.getElementById('create-campaign-cancel').onclick = closeNewCampaignModal;
document.getElementById('create-campaign-confirm').onclick = createCampaignFromForm;
document.getElementById('gen-image-btn').onclick = generateImage;
document.getElementById('save-campaign').onclick = saveCampaign;
document.getElementById('rename-campaign').onclick = renameCampaign;
document.getElementById('delete-campaign').onclick = deleteCampaign;
document.getElementById('save-settings').onclick = applySettings;
document.getElementById('recheck-readiness').onclick = async () => {
  try {
    await refreshDependencyReadiness();
    setStatus('Dependency readiness refreshed.');
  } catch (error) {
    setStatus(error.message, true);
  }
};

Promise.all([refreshMessages(), refreshState(), refreshSaves(), loadSettings(), refreshDependencyReadiness()]).catch((error) => setStatus(error.message, true));
