const chatThread = document.getElementById('chat-thread');
const campaignMeta = document.getElementById('campaign-meta');
const statePanel = document.getElementById('state-panel');
const saveList = document.getElementById('save-list');
const sceneImageDisplay = document.getElementById('scene-image-display');
const sceneVisualMeta = document.getElementById('scene-visual-meta');
const imagePromptInput = document.getElementById('image-prompt-input');
const imageStatusLine = document.getElementById('image-status-line');
const sceneImageProgressStrip = document.getElementById('scene-image-progress-strip');
const sceneImageProgressText = document.getElementById('scene-image-progress-text');
const statusLine = document.getElementById('status-line');
const readinessPanel = document.getElementById('dependency-readiness');
const setupGuidance = document.getElementById('setup-guidance');
const setupProgress = document.getElementById('setup-progress');
const setupSummary = document.getElementById('setup-summary');
const selectedSaveLabel = document.getElementById('selected-save-label');
const newCampaignModal = document.getElementById('new-campaign-modal');
const setupModal = document.getElementById('setup-modal');
const ollamaPathInput = document.getElementById('ollama-path-input');
const comfyuiPathInput = document.getElementById('comfyui-path-input');
const comfyuiModelsList = document.getElementById('comfyui-models-list');
const checkpointFolderInput = document.getElementById('checkpoint-folder-input');
const checkpointSourceInput = document.getElementById('checkpoint-source');
const preferredCheckpointInput = document.getElementById('preferred-checkpoint');
const preferredLauncherInput = document.getElementById('preferred-launcher');
const manualImageEnabledInput = document.getElementById('manual-image-enabled');
const campaignAutoVisualsEnabledInput = document.getElementById('campaign-auto-visuals-enabled');
const campaignAutoVisualTimingInput = document.getElementById('campaign-auto-visual-timing');
const suggestedMovesToggleInput = document.getElementById('suggested-moves-toggle');
const manualImagePanel = document.getElementById('manual-image-panel');
const supportedModelsList = document.getElementById('supported-models-list');
const activeModelBanner = document.getElementById('active-model-banner');
const campaignSettingsStatus = document.getElementById('campaign-settings-status');
const cancelSettingsButton = document.getElementById('cancel-settings');
const characterSheetsManager = document.getElementById('character-sheets-manager');
const characterSheetsList = document.getElementById('character-sheets-list');
const characterSheetsCount = document.getElementById('character-sheets-count');
const runtimeCharacterSheetsModal = document.getElementById('runtime-character-sheets-modal');
const runtimeCharacterSheetsList = document.getElementById('runtime-character-sheets-list');
const runtimeCharacterSheetDetail = document.getElementById('runtime-character-sheet-detail');

let draftCharacterSheets = [];
let editingSheetIndex = -1;
let runtimeCharacterSheets = [];
let selectedRuntimeSheetId = '';

let currentSceneImage = null;
let currentSceneImagePrompt = '';
let currentSceneImageTurn = null;
let imageHistory = [];
let selectedSlot = 'autosave';
let loadedSlot = 'autosave';
let selectedCampaignName = 'autosave';
let deletingCampaign = false;
let lastCampaigns = [];
let setupRunState = {
  busy: false,
  actionId: '',
  title: '',
  summary: '',
  isError: false,
  steps: [],
  startupStatus: null,
};
let latestDependencyReadiness = null;
let turnRequestInFlight = false;
let modelInventoryState = { active_model_id: '', models: [] };
let modelInstallState = {};
let campaignSettingsPersisted = null;
let campaignSettingsDirty = false;
let campaignSettingsApplying = false;
let campaignSettingsSlot = '';
const imageProgressState = {
  requestId: 0,
  phase: 'idle',
  timeoutId: 0,
};

const readinessLabels = {
  model_provider: 'Text Generation Service',
  selected_model: 'Story Model',
  image_provider: 'Image Generation Service',
};

function toTitle(statusCode) {
  return String(statusCode || '').replaceAll('_', ' ');
}

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

function actionTitle(actionId) {
  return {
    setup_text_ai: 'Set Up Text AI',
    setup_image_ai: 'Set Up Image AI',
    setup_everything: 'Set Up Everything',
    start_ollama: 'Start Ollama',
    install_ollama: 'Install Ollama',
    install_model: 'Install Story Model',
    install_image_engine: 'Install Image Engine',
    start_image_engine: 'Start Image Engine',
    recheck: 'Recheck Dependencies',
  }[actionId] || actionId;
}

function normalizeCampaignAutoVisualTiming(mode) {
  const clean = String(mode || '').trim().toLowerCase();
  if (clean === 'auto_before' || clean === 'auto_before_narration') return 'before_narration';
  if (clean === 'auto_after' || clean === 'auto_after_narration') return 'after_narration';
  if (['off', 'before_narration', 'after_narration'].includes(clean)) return clean;
  return 'off';
}

function campaignSettingsSnapshotFromUi() {
  return {
    image_generation_enabled: !!document.getElementById('image-enabled')?.checked,
    campaign_auto_visuals_enabled: !!campaignAutoVisualsEnabledInput?.checked,
    suggested_moves_enabled: !!suggestedMovesToggleInput?.checked,
    campaign_auto_visual_timing: normalizeCampaignAutoVisualTiming(campaignAutoVisualTimingInput?.value || 'off'),
  };
}

function campaignSettingsEqual(left, right) {
  if (!left || !right) return false;
  return (
    !!left.image_generation_enabled === !!right.image_generation_enabled
    && !!left.campaign_auto_visuals_enabled === !!right.campaign_auto_visuals_enabled
    && !!left.suggested_moves_enabled === !!right.suggested_moves_enabled
    && normalizeCampaignAutoVisualTiming(left.campaign_auto_visual_timing) === normalizeCampaignAutoVisualTiming(right.campaign_auto_visual_timing)
  );
}

function renderCampaignSettingsStatus() {
  if (!campaignSettingsStatus) return;
  campaignSettingsStatus.classList.remove('saved', 'unsaved', 'applying');
  if (campaignSettingsApplying) {
    campaignSettingsStatus.textContent = 'Applying...';
    campaignSettingsStatus.classList.add('applying');
    return;
  }
  if (campaignSettingsDirty) {
    campaignSettingsStatus.textContent = 'Unsaved changes';
    campaignSettingsStatus.classList.add('unsaved');
    return;
  }
  campaignSettingsStatus.textContent = 'Saved';
  campaignSettingsStatus.classList.add('saved');
}

function updateCampaignDirtyState() {
  campaignSettingsDirty = !campaignSettingsEqual(campaignSettingsSnapshotFromUi(), campaignSettingsPersisted);
  renderCampaignSettingsStatus();
  if (cancelSettingsButton) cancelSettingsButton.disabled = !campaignSettingsDirty || campaignSettingsApplying;
}

function applyCampaignSettingsToUi(snapshot) {
  if (!snapshot) return;
  document.getElementById('image-enabled').checked = !!snapshot.image_generation_enabled;
  if (campaignAutoVisualsEnabledInput) {
    campaignAutoVisualsEnabledInput.checked = !!snapshot.campaign_auto_visuals_enabled;
  }
  if (suggestedMovesToggleInput) {
    suggestedMovesToggleInput.checked = !!snapshot.suggested_moves_enabled;
  }
  if (campaignAutoVisualTimingInput) {
    campaignAutoVisualTimingInput.value = normalizeCampaignAutoVisualTiming(snapshot.campaign_auto_visual_timing || 'off');
  }
  syncVisualModeUi({
    manualEnabled: !!(manualImageEnabledInput?.checked),
    autoEnabled: !!(campaignAutoVisualsEnabledInput?.checked),
    autoTiming: campaignAutoVisualTimingInput?.value || 'off',
  });
}

function ingestPersistedCampaignSettings(snapshot, slot, { forceUi = false } = {}) {
  const normalized = {
    image_generation_enabled: !!snapshot.image_generation_enabled,
    campaign_auto_visuals_enabled: !!snapshot.campaign_auto_visuals_enabled,
    suggested_moves_enabled: !!snapshot.suggested_moves_enabled,
    campaign_auto_visual_timing: normalizeCampaignAutoVisualTiming(snapshot.campaign_auto_visual_timing || 'off'),
  };
  const slotChanged = campaignSettingsSlot && slot && campaignSettingsSlot !== slot;
  campaignSettingsPersisted = normalized;
  campaignSettingsSlot = slot || campaignSettingsSlot || loadedSlot || 'autosave';
  if (slotChanged || forceUi || !campaignSettingsDirty) {
    applyCampaignSettingsToUi(normalized);
  }
  updateCampaignDirtyState();
}

function syncVisualModeUi({ manualEnabled, autoEnabled, autoTiming }) {
  if (manualImagePanel) {
    manualImagePanel.style.display = manualEnabled ? 'grid' : 'none';
  }
  if (campaignAutoVisualTimingInput) campaignAutoVisualTimingInput.disabled = !autoEnabled;
}

function installTypeLabel(installType) {
  return {
    ollama_pull: 'One-click Ollama pull',
    guided_or_ollama_pull: 'Try pull, fallback to guided import',
    guided_import: 'Guided custom import',
  }[installType] || installType || 'Unknown';
}

function isModelInstalling(modelId) {
  const key = String(modelId || '').toLowerCase();
  return ['started', 'installing'].includes(modelInstallState[key]?.status || '');
}

function setModelInstallState(modelId, payload) {
  const key = String(modelId || '').toLowerCase();
  modelInstallState[key] = payload || {};
}

async function pollModelInstallStatus(modelName, modelId = '') {
  const key = String(modelId || modelName || '').toLowerCase();
  for (let attempt = 0; attempt < 360; attempt += 1) {
    await new Promise((resolve) => setTimeout(resolve, 1000));
    const status = await api(`/api/models/install-status?model=${encodeURIComponent(modelName)}`);
    console.log(`[model-install] poll model=${modelName} status=${status.status || 'unknown'} message=${status.message || ''}`);
    setModelInstallState(key, status);
    if (status.status === 'installed' || status.status === 'failed') {
      return status;
    }
    if (attempt % 3 === 0 && status.message) {
      setStatus(status.message, false);
    }
  }
  return { ok: false, status: 'failed', message: `Install polling timed out for ${modelName}.`, model: modelName };
}

async function startModelInstallFlow({ modelId = '', modelName = '', source = 'settings' }) {
  const key = String(modelId || modelName).toLowerCase();
  if (isModelInstalling(key)) {
    setStatus(`Install already in progress for ${modelId || modelName}.`);
    return { ok: true, status: 'started', message: 'Install already running.' };
  }
  const payload = modelId ? { model_id: modelId } : { model: modelName };
  const endpoint = modelId ? '/api/models/install' : '/api/setup/install-model';
  console.log(`[setup-ui] install click source=${source} endpoint=${endpoint} payload=${JSON.stringify(payload)}`);
  setStatus(`Installing ${modelName || modelId}...`);
  setModelInstallState(key, { status: 'started', message: `Install started for ${modelName || modelId}.` });
  await refreshSupportedModels(false);
  const startResult = await api(endpoint, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
  console.log(`[setup-ui] install response source=${source} status=${startResult.status || 'unknown'} ok=${!!startResult.ok} message=${startResult.message || ''}`);
  const pollTarget = startResult.model || modelName || modelId;
  const finalResult = await pollModelInstallStatus(pollTarget, key);
  setModelInstallState(key, finalResult);
  await refreshSupportedModels(false);
  await refreshDependencyReadiness();
  await loadSettings();
  const message = finalResult.ok ? (finalResult.message || `Installed ${pollTarget}.`) : (finalResult.next_step ? `${finalResult.message} ${finalResult.next_step}` : (finalResult.message || `Failed to install ${pollTarget}.`));
  setStatus(message, !finalResult.ok);
  return finalResult;
}

async function refreshSupportedModels(showStatus = false) {
  const payload = await api('/api/models/supported');
  modelInventoryState = payload || { active_model_id: '', models: [] };
  renderSupportedModels(modelInventoryState);
  if (showStatus) setStatus('Model inventory refreshed.');
}

function renderSupportedModels(payload) {
  if (!supportedModelsList || !activeModelBanner) return;
  const models = Array.isArray(payload?.models) ? payload.models : [];
  const active = models.find((model) => model.active) || null;
  activeModelBanner.textContent = `Active model: ${active?.display_name || payload?.active_model_id || 'none'}`;
  if (!models.length) {
    supportedModelsList.textContent = 'No supported models configured.';
    return;
  }
  supportedModelsList.innerHTML = models.map((model) => {
    const installLabel = installTypeLabel(model.install_type);
    const badge = model.active ? '<span class="ready-badge">Active</span>' : model.installed ? '<span class="ready-badge">Installed</span>' : model.install_type === 'guided_import' ? '<span class="not-ready-badge">Needs import</span>' : '<span class="not-ready-badge">Not installed</span>';
    const installBusy = isModelInstalling(model.id);
    const installBtn = model.install_supported
      ? `<button class="model-action-btn" data-model-action="install" data-model-id="${escapeHtml(model.id)}" ${installBusy ? 'disabled' : ''}>${installBusy ? 'Installing...' : (model.installed ? 'Reinstall' : 'Install')}</button>`
      : `<button class="model-action-btn" data-model-action="guide" data-model-id="${escapeHtml(model.id)}">Import guide</button>`;
    const activateBtn = model.activate_supported && (model.installed || model.active)
      ? `<button class="model-action-btn" data-model-action="activate" data-model-id="${escapeHtml(model.id)}" ${model.active ? 'disabled' : ''}>${model.active ? 'Active' : 'Activate'}</button>`
      : '';
    const notes = model.mature_or_roleplay_note ? `<div class="model-meta"><strong>Notes:</strong> ${escapeHtml(model.mature_or_roleplay_note)}</div>` : '';
    return `
      <div class="supported-model-card">
        <div class="panel-title-row"><strong>${escapeHtml(model.display_name)}</strong>${badge}</div>
        <div class="model-meta"><code>${escapeHtml(model.id)}</code> · ${escapeHtml(installLabel)}</div>
        <div class="model-meta">${escapeHtml(model.description || '')}</div>
        ${notes}
        <div class="readiness-action-row">${installBtn}${activateBtn}</div>
      </div>
    `;
  }).join('');
  supportedModelsList.querySelectorAll('.model-action-btn').forEach((button) => {
    button.onclick = async () => {
      const modelId = button.dataset.modelId || '';
      const action = button.dataset.modelAction || '';
      if (action === 'install') {
        const model = (modelInventoryState.models || []).find((entry) => entry.id === modelId);
        const targetName = model?.ollama_name || model?.id || modelId;
        const result = await startModelInstallFlow({ modelId, modelName: targetName, source: 'supported-models' });
        const guided = Array.isArray(result.guided_install_steps) ? ` ${result.guided_install_steps.join(' ')}` : '';
        setStatus(result.ok ? (result.message || 'Model installed.') : `${result.message || 'Install failed.'}${guided}`, !result.ok);
      } else if (action === 'activate') {
        const result = await api('/api/models/activate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ model_id: modelId }) });
        setStatus(result.ok ? (result.message || 'Model activated.') : (result.message || 'Activation failed.'), !result.ok);
      } else {
        const result = await api('/api/models/install', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ model_id: modelId }) });
        const guided = Array.isArray(result.guided_install_steps) ? result.guided_install_steps.join(' ') : 'Guided import required.';
        setStatus(guided, true);
      }
      await refreshSupportedModels(false);
      await loadSettings();
    };
  });
}

function updateSetupButtonsBusyState() {
  const managedButtons = document.querySelectorAll('#setup-text-ai, #setup-image-ai, #setup-everything, #recheck-readiness, .readiness-action-btn');
  managedButtons.forEach((button) => {
    const actionId = button.dataset.action || (button.id === 'setup-text-ai' ? 'setup_text_ai'
      : button.id === 'setup-image-ai' ? 'setup_image_ai'
      : button.id === 'setup-everything' ? 'setup_everything'
      : button.id === 'recheck-readiness' ? 'recheck'
      : '');
    if (!actionId) return;
    if (!setupRunState.busy) {
      button.disabled = false;
      return;
    }
    if (actionId === 'recheck') {
      button.disabled = true;
      return;
    }
    button.disabled = true;
  });
}

function renderSetupProgress() {
  if (!setupProgress) return;
  const hasState = setupRunState.busy || setupRunState.summary || setupRunState.steps.length;
  if (!hasState) {
    setupProgress.classList.add('hidden');
    setupProgress.innerHTML = '';
    return;
  }
  setupProgress.classList.remove('hidden');
  const stepRows = setupRunState.steps.map((step) => `<li class="setup-step ${escapeHtml(step.state || '')}">${escapeHtml(step.label || step.step || 'step')}: ${escapeHtml(step.message || '')}</li>`).join('');
  const summaryClass = setupRunState.isError ? 'error' : 'success';
  const startupStatus = setupRunState.startupStatus || null;
  const startupLog = startupStatus?.log_text
    ? `<details class="startup-log"><summary>Image engine startup details</summary><pre>${escapeHtml(startupStatus.log_text)}</pre></details>`
    : '';
  setupProgress.innerHTML = `
    <div class="setup-progress-head">
      ${setupRunState.busy ? '<span class="spinner" aria-hidden="true"></span>' : ''}
      <strong>${escapeHtml(setupRunState.title || 'Setup status')}</strong>
    </div>
    <div class="setup-progress-summary ${summaryClass}">${escapeHtml(setupRunState.summary || (setupRunState.busy ? 'Working...' : ''))}</div>
    ${stepRows ? `<ol class="setup-steps">${stepRows}</ol>` : ''}
    ${startupLog}
  `;
  updateSetupButtonsBusyState();
}

function startSetupRun(actionId, initialSummary, steps = []) {
  setupRunState = {
    busy: true,
    actionId,
    title: actionTitle(actionId),
    summary: initialSummary,
    isError: false,
    steps,
    startupStatus: null,
  };
  renderSetupProgress();
}

function updateSetupRun(update) {
  setupRunState = { ...setupRunState, ...update };
  renderSetupProgress();
}

function finishSetupRun({ summary, isError = false, steps = [] }) {
  setupRunState = {
    ...setupRunState,
    busy: false,
    summary: summary || setupRunState.summary,
    isError,
    steps: steps.length ? steps : setupRunState.steps,
  };
  renderSetupProgress();
}

function normalizeSetupSteps(steps = []) {
  return (steps || []).map((step) => ({
    step: step.step || 'step',
    label: toTitle(step.step || 'step'),
    state: step.state || 'ready',
    message: step.message || '',
  }));
}

async function runReadinessAction(actionId, item) {
  if (setupRunState.busy) {
    setStatus('Another setup action is still running. Please wait.');
    return;
  }
  try {
    if (actionId === 'setup_text_ai') {
      const modelName = document.getElementById('model-name').value.trim() || item.selected_model || 'llama3';
      startSetupRun(actionId, `Preparing Text AI setup for model ${modelName}...`, [
        { step: 'provider-check', label: 'Provider check', state: 'running', message: 'Verifying model provider and model target...' },
      ]);
      setStatus('Set Up Text AI: installing / starting / waiting for readiness...');
      const result = await api('/api/setup/orchestrate-text', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ model: modelName }),
      });
      updateSetupRun({
        steps: normalizeSetupSteps(result.steps),
        summary: result.summary || result.message || (result.ok ? 'Text AI is ready.' : 'Text AI setup failed.'),
      });
      await refreshDependencyReadiness();
      console.log('[setup-action] readiness refresh triggered');
      setStatus(result.summary || result.message || (result.ok ? 'Text AI ready.' : 'Text AI setup failed.'), !result.ok);
      finishSetupRun({
        summary: result.summary || result.message || (result.ok ? 'Text AI is ready.' : 'Text AI setup failed.'),
        isError: !result.ok,
        steps: normalizeSetupSteps(result.steps),
      });
      return;
    }
    if (actionId === 'setup_image_ai') {
      startSetupRun(actionId, 'Starting Image AI setup...', [
        { step: 'detect-install-path', label: 'Detect install path', state: 'running', message: 'Checking ComfyUI install path...' },
      ]);
      setStatus('Set Up Image AI: installing / starting / waiting for readiness...');
      const result = await api('/api/setup/orchestrate-image', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({}),
      });
      updateSetupRun({
        steps: normalizeSetupSteps(result.steps),
        summary: result.summary || result.message || (result.ok ? 'Image AI is ready.' : 'Image AI setup failed.'),
      });
      await refreshDependencyReadiness();
      console.log('[setup-action] readiness refresh triggered');
      setStatus(result.summary || result.message || (result.ok ? 'Image AI ready.' : 'Image AI setup failed.'), !result.ok);
      finishSetupRun({
        summary: result.summary || result.message || (result.ok ? 'Image AI is ready.' : 'Image AI setup failed.'),
        isError: !result.ok,
        steps: normalizeSetupSteps(result.steps),
      });
      return;
    }
    if (actionId === 'setup_everything') {
      const modelName = document.getElementById('model-name').value.trim() || item.selected_model || 'llama3';
      startSetupRun(actionId, 'Starting full setup (Text AI + Image AI)...', [
        { step: 'setup-text-ai', label: 'Text AI setup', state: 'running', message: `Preparing model ${modelName}...` },
      ]);
      setStatus('Set Up Everything: installing, starting, waiting for readiness...');
      const result = await api('/api/setup/orchestrate-everything', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ model: modelName }),
      });
      const combinedSteps = [...normalizeSetupSteps(result.text?.steps), ...normalizeSetupSteps(result.image?.steps)];
      updateSetupRun({
        steps: combinedSteps,
        summary: result.summary || result.message || (result.ok ? 'Text AI ready. Image AI ready.' : 'Setup Everything failed.'),
      });
      await refreshDependencyReadiness();
      console.log('[setup-action] readiness refresh triggered');
      setStatus(result.summary || result.message || (result.ok ? 'Text AI ready. Image AI ready.' : 'Setup Everything failed.'), !result.ok);
      finishSetupRun({
        summary: result.summary || result.message || (result.ok ? 'Text AI ready. Image AI ready.' : 'Setup Everything failed.'),
        isError: !result.ok,
        steps: combinedSteps,
      });
      return;
    }
    if (actionId === 'recheck') {
      startSetupRun(actionId, 'Refreshing dependency readiness...', [
        { step: 'recheck', label: 'Recheck dependencies', state: 'running', message: 'Requesting latest dependency state...' },
      ]);
      await refreshDependencyReadiness();
      setStatus('Dependency readiness refreshed.');
      finishSetupRun({ summary: 'Dependency readiness refreshed.', isError: false, steps: [{ step: 'recheck', label: 'Recheck dependencies', state: 'ready', message: 'Latest readiness loaded.' }] });
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
      console.log(`[setup-ui] install-model click model=${modelName}`);
      await startModelInstallFlow({ modelName, source: 'setup-panel' });
      console.log('[setup-ui] install-model flow completed');
      return;
    }
    if (actionId === 'install_image_engine') {
      setStatus('Installing ComfyUI bootstrap files...');
      console.log('[setup-action] install-image-engine requested');
      const result = await api('/api/setup/install-image-engine', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({}),
      });
      console.log(`[setup-action] install-image-engine ${result.ok ? 'success' : 'failure'} reason=${result.message || 'unknown'}`);
      await refreshDependencyReadiness();
      console.log('[setup-action] readiness refresh triggered');
      setStatus(result.ok ? (result.message || 'Image engine setup ready for next step.') : (result.next_step ? `${result.message} ${result.next_step}` : result.message), !result.ok);
      return;
    }
    if (actionId === 'start_image_engine') {
      startSetupRun(actionId, 'Starting Image AI...', [
        { step: 'detect-install-path', label: 'Check install path', state: 'running', message: 'Checking install path...' },
        { step: 'verify-install', label: 'Verifying install', state: 'pending', message: 'Checking required ComfyUI files...' },
        { step: 'repair-launcher', label: 'Repairing launcher', state: 'pending', message: 'Repairing missing launcher if required...' },
        { step: 'launch-engine', label: 'Starting engine', state: 'pending', message: 'Waiting to launch engine...' },
        { step: 'wait-for-readiness', label: 'Wait for response', state: 'pending', message: 'Waiting for engine response...' },
      ]);
      updateSetupRun({
        summary: 'Starting Image AI... Checking install path...',
        steps: [
          { step: 'detect-install-path', label: 'Check install path', state: 'running', message: 'Checking install path...' },
          { step: 'verify-install', label: 'Verifying install', state: 'pending', message: 'Checking required ComfyUI files...' },
          { step: 'repair-launcher', label: 'Repairing launcher', state: 'pending', message: 'Repairing missing launcher if required...' },
          { step: 'launch-engine', label: 'Starting engine', state: 'pending', message: 'Waiting to launch engine...' },
          { step: 'wait-for-readiness', label: 'Wait for response', state: 'pending', message: 'Waiting for engine response...' },
        ],
      });
      setStatus('Starting ComfyUI...');
      console.log('[setup-action] start-image-engine requested');
      const result = await api('/api/setup/start-image-engine', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({}),
      });
      console.log(`[setup-action] start-image-engine ${result.ok ? 'success' : 'failure'} reason=${result.message || 'unknown'}`);
      updateSetupRun({
        steps: normalizeSetupSteps(result.steps),
        summary: result.ok
          ? 'Image AI is ready.'
          : `Image AI failed to start: ${result.failure_stage_message || result.message || 'unknown failure'}`,
        startupStatus: result.startup_status || null,
      });
      await refreshDependencyReadiness();
      console.log('[setup-action] readiness refresh triggered');
      setStatus(result.ok ? (result.message || 'ComfyUI started.') : (result.next_step ? `${result.message} ${result.next_step}` : result.message), !result.ok);
      finishSetupRun({
        summary: result.ok
          ? 'Image AI is ready.'
          : `Image AI failed to start: ${result.failure_stage_message || result.message || 'unknown failure'}`,
        isError: !result.ok,
        steps: normalizeSetupSteps(result.steps),
        startupStatus: result.startup_status || null,
      });
      return;
    }
  } catch (error) {
    setStatus(error.message, true);
    finishSetupRun({ summary: `Setup failed: ${error.message}`, isError: true });
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

function setImageStatus(message, isError = false) {
  if (!imageStatusLine) return;
  imageStatusLine.textContent = message;
  imageStatusLine.style.color = isError ? '#fca5a5' : '#cbd5e1';
}

const imageProgressMessages = {
  submitting: 'Submitting image request...',
  accepted: 'Generating scene image...',
  generating: 'Generating scene image...',
  finalizing: 'Finalizing visual...',
  success: 'Scene visual updated',
  error: 'Image generation failed',
};

function clearImageProgressTimer() {
  if (imageProgressState.timeoutId) {
    window.clearTimeout(imageProgressState.timeoutId);
    imageProgressState.timeoutId = 0;
  }
}

function setImageProgressPhase(phase, message = '') {
  if (!sceneImageProgressStrip || !sceneImageProgressText) return;
  clearImageProgressTimer();
  imageProgressState.phase = phase;
  if (phase === 'idle') {
    sceneImageProgressStrip.classList.add('hidden');
    sceneImageProgressStrip.removeAttribute('data-phase');
    sceneImageProgressText.textContent = '';
    return;
  }
  sceneImageProgressStrip.classList.remove('hidden');
  sceneImageProgressStrip.dataset.phase = phase;
  sceneImageProgressText.textContent = message || imageProgressMessages[phase] || 'Generating scene image...';
}

function beginImageProgress(phase = 'submitting', message = '') {
  imageProgressState.requestId += 1;
  setImageProgressPhase(phase, message);
  return imageProgressState.requestId;
}

function updateImageProgress(requestId, phase, message = '') {
  if (requestId !== imageProgressState.requestId) return;
  setImageProgressPhase(phase, message);
}

function settleImageProgress(requestId, ok, message = '') {
  if (requestId !== imageProgressState.requestId) return;
  const phase = ok ? 'success' : 'error';
  setImageProgressPhase(phase, message || imageProgressMessages[phase]);
  imageProgressState.timeoutId = window.setTimeout(
    () => setImageProgressPhase('idle'),
    ok ? 1800 : 4200,
  );
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
  draftCharacterSheets = [];
  editingSheetIndex = -1;
  renderCharacterSheetList();
  document.getElementById('character-sheets-manager')?.classList.add('hidden');
  document.getElementById('character-sheet-editor')?.classList.add('hidden');
  newCampaignModal.classList.remove('hidden');
}

function closeNewCampaignModal() {
  newCampaignModal.classList.add('hidden');
}

function openSetupModal() {
  setupModal.classList.remove('hidden');
}

function closeSetupModal() {
  setupModal.classList.add('hidden');
}

function parseCsv(input) {
  return String(input || '').split(',').map((v) => v.trim()).filter(Boolean);
}

function renderCharacterSheetList() {
  if (!characterSheetsList || !characterSheetsCount) return;
  if (!draftCharacterSheets.length) {
    characterSheetsList.textContent = 'No sheets yet.';
    characterSheetsCount.textContent = 'No sheets attached';
    return;
  }
  characterSheetsCount.textContent = `${draftCharacterSheets.length} sheet(s) attached`;
  characterSheetsList.innerHTML = draftCharacterSheets.map((sheet, index) => `
    <div class="character-sheet-item">
      <span><strong>${escapeHtml(sheet.name || 'Unnamed')}</strong> • ${escapeHtml(sheet.sheet_type)}</span>
      <span>
        <button type="button" data-sheet-edit="${index}">Edit</button>
        <button type="button" data-sheet-delete="${index}">Delete</button>
      </span>
    </div>
  `).join('');
  characterSheetsList.querySelectorAll('button[data-sheet-edit]').forEach((btn) => {
    btn.onclick = () => openSheetEditor(Number(btn.dataset.sheetEdit || -1));
  });
  characterSheetsList.querySelectorAll('button[data-sheet-delete]').forEach((btn) => {
    btn.onclick = () => {
      const idx = Number(btn.dataset.sheetDelete || -1);
      if (idx >= 0) {
        draftCharacterSheets.splice(idx, 1);
        renderCharacterSheetList();
      }
    };
  });
}

function renderRuntimeCharacterSheets() {
  if (!runtimeCharacterSheetsList || !runtimeCharacterSheetDetail) return;
  if (!runtimeCharacterSheets.length) {
    runtimeCharacterSheetsList.textContent = 'No sheets attached to this campaign.';
    runtimeCharacterSheetDetail.textContent = 'No character sheet data is attached to this campaign yet.';
    selectedRuntimeSheetId = '';
    return;
  }
  const hasSelection = runtimeCharacterSheets.some((sheet) => sheet.id === selectedRuntimeSheetId);
  if (!hasSelection) {
    selectedRuntimeSheetId = runtimeCharacterSheets[0].id || '';
  }
  runtimeCharacterSheetsList.innerHTML = runtimeCharacterSheets.map((sheet) => {
    const selectedClass = sheet.id === selectedRuntimeSheetId ? 'selected' : '';
    const stats = sheet.stats || {};
    return `
      <button type="button" class="runtime-sheet-list-item ${selectedClass}" data-sheet-id="${escapeHtml(sheet.id || '')}">
        <strong>${escapeHtml(sheet.name || 'Unnamed')}</strong>
        <span>${escapeHtml(sheet.sheet_type || 'unknown')}</span>
        <small>HP ${Number(stats.health ?? 0)} • Energy ${Number(stats.energy_or_mana ?? 0)}</small>
      </button>
    `;
  }).join('');
  runtimeCharacterSheetsList.querySelectorAll('button[data-sheet-id]').forEach((button) => {
    button.onclick = () => {
      selectedRuntimeSheetId = button.dataset.sheetId || '';
      renderRuntimeCharacterSheets();
    };
  });
  const selectedSheet = runtimeCharacterSheets.find((sheet) => sheet.id === selectedRuntimeSheetId) || runtimeCharacterSheets[0];
  renderRuntimeCharacterSheetDetail(selectedSheet);
}

function renderRuntimeCharacterSheetDetail(sheet) {
  if (!runtimeCharacterSheetDetail || !sheet) return;
  const stats = sheet.stats || {};
  const classic = sheet.classic_attributes || {};
  runtimeCharacterSheetDetail.innerHTML = `
    <article class="runtime-sheet-card">
      <h4>${escapeHtml(sheet.name || 'Unnamed')} • ${escapeHtml(sheet.sheet_type || 'unknown')}</h4>
      <dl>
        <dt>Role / Archetype</dt><dd>${escapeHtml(sheet.role || 'n/a')} / ${escapeHtml(sheet.archetype || 'n/a')}</dd>
        <dt>Faction</dt><dd>${escapeHtml(sheet.faction || 'n/a')}</dd>
        <dt>Description</dt><dd>${escapeHtml(sheet.description || 'n/a')}</dd>
        <dt>Stats</dt><dd>HP ${Number(stats.health ?? 0)} • Energy ${Number(stats.energy_or_mana ?? 0)} • Atk ${Number(stats.attack ?? 0)} • Def ${Number(stats.defense ?? 0)} • Spd ${Number(stats.speed ?? 0)} • Mag ${Number(stats.magic ?? 0)} • Will ${Number(stats.willpower ?? 0)} • Presence ${Number(stats.presence ?? 0)}</dd>
        <dt>Classic Attributes</dt><dd>STR ${classic.strength ?? 'n/a'} • DEX ${classic.dexterity ?? 'n/a'} • CON ${classic.constitution ?? 'n/a'} • INT ${classic.intelligence ?? 'n/a'} • WIS ${classic.wisdom ?? 'n/a'} • CHA ${classic.charisma ?? 'n/a'}</dd>
        <dt>Traits</dt><dd>${escapeHtml((sheet.traits || []).join(', ') || 'n/a')}</dd>
        <dt>Abilities</dt><dd>${escapeHtml((sheet.abilities || []).join(', ') || 'n/a')}</dd>
        <dt>Equipment</dt><dd>${escapeHtml((sheet.equipment || []).join(', ') || 'n/a')}</dd>
        <dt>Weaknesses</dt><dd>${escapeHtml((sheet.weaknesses || []).join(', ') || 'n/a')}</dd>
        <dt>Notes</dt><dd>${escapeHtml(sheet.notes || 'n/a')}</dd>
      </dl>
    </article>
  `;
}

function openSheetEditor(index = -1) {
  const editor = document.getElementById('character-sheet-editor');
  const title = document.getElementById('character-sheet-editor-title');
  if (!editor || !title) return;
  editingSheetIndex = index;
  const existing = index >= 0 ? draftCharacterSheets[index] : null;
  title.textContent = existing ? 'Edit Sheet' : 'New Sheet';
  document.getElementById('sheet-name').value = existing?.name || '';
  document.getElementById('sheet-type').value = existing?.sheet_type || 'main_character';
  document.getElementById('sheet-role').value = existing?.role || '';
  document.getElementById('sheet-archetype').value = existing?.archetype || '';
  document.getElementById('sheet-level-rank').value = existing?.level_or_rank || '';
  document.getElementById('sheet-faction').value = existing?.faction || '';
  document.getElementById('sheet-description').value = existing?.description || '';
  document.getElementById('sheet-traits').value = (existing?.traits || []).join(', ');
  document.getElementById('sheet-temperament').value = existing?.temperament || '';
  document.getElementById('sheet-loyalty').value = existing?.loyalty || '';
  document.getElementById('sheet-fear').value = existing?.fear || '';
  document.getElementById('sheet-desire').value = existing?.desire || '';
  document.getElementById('sheet-social-style').value = existing?.social_style || '';
  document.getElementById('sheet-speech-style').value = existing?.speech_style || '';
  document.getElementById('sheet-abilities').value = (existing?.abilities || []).join(', ');
  document.getElementById('sheet-equipment').value = (existing?.equipment || []).join(', ');
  document.getElementById('sheet-weaknesses').value = (existing?.weaknesses || []).join(', ');
  document.getElementById('sheet-health').value = existing?.stats?.health ?? 10;
  document.getElementById('sheet-energy').value = existing?.stats?.energy_or_mana ?? 10;
  document.getElementById('sheet-attack').value = existing?.stats?.attack ?? 10;
  document.getElementById('sheet-defense').value = existing?.stats?.defense ?? 10;
  document.getElementById('sheet-speed').value = existing?.stats?.speed ?? 10;
  document.getElementById('sheet-magic').value = existing?.stats?.magic ?? 10;
  document.getElementById('sheet-willpower').value = existing?.stats?.willpower ?? 10;
  document.getElementById('sheet-presence').value = existing?.stats?.presence ?? 10;
  document.getElementById('sheet-notes').value = existing?.notes || '';
  document.getElementById('sheet-current-condition').value = existing?.state?.current_condition || '';
  document.getElementById('sheet-trust').value = existing?.state?.trust ?? '';
  document.getElementById('sheet-suspicion').value = existing?.state?.suspicion ?? '';
  document.getElementById('sheet-anger').value = existing?.state?.anger ?? '';
  document.getElementById('sheet-fear-state').value = existing?.state?.fear_state ?? '';
  document.getElementById('sheet-morale').value = existing?.state?.morale ?? '';
  document.getElementById('sheet-bond').value = existing?.state?.bond_to_player ?? '';
  document.getElementById('sheet-guidance-strength').value = existing?.guidance_strength || 'light';
  editor.classList.remove('hidden');
}

function buildSheetFromEditor() {
  const sheetId = `sheet_${Date.now()}_${Math.floor(Math.random() * 1000)}`;
  const numberOrNull = (id) => {
    const value = document.getElementById(id).value;
    if (value === '') return null;
    return Number(value);
  };
  return {
    id: editingSheetIndex >= 0 ? draftCharacterSheets[editingSheetIndex].id : sheetId,
    name: document.getElementById('sheet-name').value.trim() || 'Unnamed',
    sheet_type: document.getElementById('sheet-type').value,
    role: document.getElementById('sheet-role').value.trim(),
    archetype: document.getElementById('sheet-archetype').value.trim(),
    level_or_rank: document.getElementById('sheet-level-rank').value.trim(),
    faction: document.getElementById('sheet-faction').value.trim(),
    description: document.getElementById('sheet-description').value.trim(),
    stats: {
      health: Number(document.getElementById('sheet-health').value || 10),
      energy_or_mana: Number(document.getElementById('sheet-energy').value || 10),
      attack: Number(document.getElementById('sheet-attack').value || 10),
      defense: Number(document.getElementById('sheet-defense').value || 10),
      speed: Number(document.getElementById('sheet-speed').value || 10),
      magic: Number(document.getElementById('sheet-magic').value || 10),
      willpower: Number(document.getElementById('sheet-willpower').value || 10),
      presence: Number(document.getElementById('sheet-presence').value || 10),
    },
    classic_attributes: {},
    traits: parseCsv(document.getElementById('sheet-traits').value),
    abilities: parseCsv(document.getElementById('sheet-abilities').value),
    equipment: parseCsv(document.getElementById('sheet-equipment').value),
    weaknesses: parseCsv(document.getElementById('sheet-weaknesses').value),
    temperament: document.getElementById('sheet-temperament').value.trim(),
    loyalty: document.getElementById('sheet-loyalty').value.trim(),
    fear: document.getElementById('sheet-fear').value.trim(),
    desire: document.getElementById('sheet-desire').value.trim(),
    social_style: document.getElementById('sheet-social-style').value.trim(),
    speech_style: document.getElementById('sheet-speech-style').value.trim(),
    notes: document.getElementById('sheet-notes').value.trim(),
    state: {
      trust: numberOrNull('sheet-trust'),
      suspicion: numberOrNull('sheet-suspicion'),
      anger: numberOrNull('sheet-anger'),
      fear_state: numberOrNull('sheet-fear-state'),
      morale: numberOrNull('sheet-morale'),
      bond_to_player: numberOrNull('sheet-bond'),
      current_condition: document.getElementById('sheet-current-condition').value.trim(),
    },
    guidance_strength: document.getElementById('sheet-guidance-strength').value || 'light',
  };
}

async function api(path, options = {}) {
  const response = await fetch(path, options);
  const data = await response.json().catch(() => ({ error: 'Invalid server response' }));
  if (!response.ok) {
    const detail = data.error || data.message || data.detail || data.reason || '';
    const nested = data.metadata?.error_body || '';
    const composed = [detail, nested].filter(Boolean).join(' ').trim();
    throw new Error(composed || `Request failed for ${path}`);
  }
  return data;
}

function renderMessage(msg) {
  if (msg.type === 'image') {
    msg = { ...msg, type: 'system', text: msg.text || 'Scene visual updated.' };
  }
  const el = document.createElement('div');
  el.className = `msg msg-${msg.type}`;
  const ts = new Date(msg.timestamp).toLocaleTimeString();
  el.innerHTML = `<small>${labelForType(msg.type)} • ${ts}</small>${escapeHtml(msg.text || '')}`;
  chatThread.appendChild(el);
  chatThread.scrollTop = chatThread.scrollHeight;
}

function labelForType(type) {
  return ({ player: 'PLAYER', narrator: 'NARRATOR', npc: 'NPC', quest: 'QUEST', image: 'IMAGE', system: 'SYSTEM', error: 'ERROR' })[type] || 'SYSTEM';
}

function setSceneImage(url, caption = '', turn = null) {
  currentSceneImage = url;
  currentSceneImagePrompt = caption || '';
  currentSceneImageTurn = turn;
  imageHistory = [{ url, caption, turn }, ...imageHistory.filter((entry) => entry.url !== url)].slice(0, 30);
  sceneImageDisplay.innerHTML = '';
  const img = document.createElement('img');
  img.src = url;
  img.alt = caption || 'Generated scene image';
  const text = document.createElement('div');
  text.textContent = caption || 'Generated scene image';
  sceneImageDisplay.appendChild(img);
  sceneImageDisplay.appendChild(text);
  if (sceneVisualMeta) {
    const turnLabel = turn ? `Turn ${turn}` : 'Scene visual updated';
    sceneVisualMeta.textContent = `${turnLabel} • ${caption || 'Generated image'}`;
  }
  setImageStatus('Latest generated image loaded in Scene Visual.');
  if (imageProgressState.phase !== 'idle') {
    settleImageProgress(imageProgressState.requestId, true, 'Scene visual updated');
  }
}

function clearSceneImage(message = 'Scene image will appear here.') {
  currentSceneImage = null;
  currentSceneImagePrompt = '';
  currentSceneImageTurn = null;
  if (sceneImageDisplay) sceneImageDisplay.textContent = message;
  if (sceneVisualMeta) sceneVisualMeta.textContent = 'Generate an image to view the current scene.';
}

async function refreshMessages() {
  const data = await api('/api/campaign/messages');
  chatThread.innerHTML = '';
  const messages = data.messages || [];
  messages.forEach(renderMessage);
}

async function refreshSceneVisual() {
  const data = await api('/api/campaign/scene-visual');
  const sceneVisual = data.scene_visual;
  if (sceneVisual?.image_url) {
    setSceneImage(sceneVisual.image_url, sceneVisual.prompt || 'Generated scene image', sceneVisual.turn || null);
    return sceneVisual;
  }
  clearSceneImage();
  return null;
}

async function waitForSceneVisualUpdate(previousUpdatedAt = '') {
  const progressId = beginImageProgress('accepted', 'Generating scene image...');
  const started = Date.now();
  const timeoutMs = 45000;
  let pollCount = 0;
  while (Date.now() - started < timeoutMs) {
    await new Promise((resolve) => setTimeout(resolve, 1500));
    pollCount += 1;
    updateImageProgress(progressId, 'generating', pollCount > 1 ? 'Generating scene image...' : 'Submitting image request...');
    const sceneVisual = await refreshSceneVisual().catch(() => null);
    if (sceneVisual?.updated_at && sceneVisual.updated_at !== previousUpdatedAt) {
      setImageStatus('Scene visual updated.');
      updateImageProgress(progressId, 'finalizing', 'Finalizing visual...');
      return true;
    }
  }
  setImageStatus('Scene visual generation is taking longer than expected.');
  settleImageProgress(progressId, false, 'Image generation failed');
  return false;
}

const PANEL_PLACEHOLDER_VALUES = new Set([
  'untitled world',
  'starting area',
  'classic fantasy',
  'heroic',
  'standard',
  'not specified',
]);

function hasMeaningfulText(value) {
  if (typeof value !== 'string') return false;
  const normalized = value.trim();
  if (!normalized) return false;
  return !PANEL_PLACEHOLDER_VALUES.has(normalized.toLowerCase());
}

function hasMeaningfulCharacter(player = {}) {
  const name = (player.name || '').trim().toLowerCase();
  const charClass = (player.class || '').trim().toLowerCase();
  if (!name || !charClass) return false;
  return !(name === 'aria' && charClass === 'ranger');
}

function formatQuestStatus(questStatus) {
  if (!questStatus || typeof questStatus !== 'object') return null;
  const entries = Object.entries(questStatus).filter(([questId, status]) => {
    if (!questId || typeof status !== 'string') return false;
    return status.trim().length > 0;
  });
  if (!entries.length) return 'No active quests';

  const activeEntries = entries.filter(([, status]) => status.toLowerCase() === 'active');
  if (!activeEntries.length) return 'No active quests';

  return `Active quests: ${activeEntries.map(([questId]) => questId).join(', ')}`;
}

async function refreshState() {
  const data = await api('/api/campaign/state');
  const state = data.state;
  const incomingSlot = state.active_slot || loadedSlot;
  loadedSlot = state.active_slot || loadedSlot;
  selectedSlot = state.active_slot || selectedSlot;
  selectedCampaignName = state.campaign_name;
  const world = state.world_meta || {};
  runtimeCharacterSheets = Array.isArray(state.character_sheets) ? state.character_sheets : [];
  renderRuntimeCharacterSheets();
  campaignMeta.textContent = `${state.campaign_name || 'Campaign'} · Turn ${state.turn_count || 0}`;

  const panelLines = [];
  const playerClass = state.player.class || state.player.role || 'Adventurer';
  const hasCharacter = hasMeaningfulCharacter({ name: state.player.name, class: playerClass });
  if (hasCharacter) {
    panelLines.push(`Character: ${state.player.name} (${playerClass})`);
  }

  if (hasCharacter && Number.isFinite(state.player.hp) && Number.isFinite(state.player.max_hp)) {
    panelLines.push(`HP: ${state.player.hp}/${state.player.max_hp}`);
  }

  const hasWorldName = hasMeaningfulText(world.world_name);
  const hasWorldTheme = hasMeaningfulText(world.world_theme);
  if (hasWorldName || hasWorldTheme) {
    const worldNameLabel = hasWorldName ? world.world_name.trim() : '';
    const worldThemeLabel = hasWorldTheme ? world.world_theme.trim() : '';
    const worldSummary = [worldNameLabel, worldThemeLabel ? `(${worldThemeLabel})` : ''].filter(Boolean).join(' ');
    if (worldSummary) panelLines.push(`World: ${worldSummary}`);
  }

  if (hasMeaningfulText(world.starting_location_name)) {
    panelLines.push(`Starting location: ${world.starting_location_name.trim()}`);
  }
  if (state.current_location_id) {
    panelLines.push(`Current location: ${state.current_location_id}`);
  }

  const tone = hasMeaningfulText(world.tone) ? world.tone.trim() : null;
  const maturityLevel = hasMeaningfulText(state.settings?.content_settings?.maturity_level)
    ? state.settings.content_settings.maturity_level.trim()
    : null;
  if (tone || maturityLevel) {
    const toneParts = [];
    if (tone) toneParts.push(`Tone: ${tone}`);
    if (maturityLevel) toneParts.push(`Maturity: ${maturityLevel}`);
    panelLines.push(toneParts.join(' | '));
  }

  if (hasMeaningfulText(world.premise)) {
    panelLines.push(`Premise: ${world.premise.trim()}`);
  }
  if (hasMeaningfulText(world.player_concept)) {
    panelLines.push(`Player concept: ${world.player_concept.trim()}`);
  }

  const questSummary = formatQuestStatus(state.quest_status);
  if (questSummary) {
    panelLines.push('', questSummary);
  }

  statePanel.textContent = panelLines.join('\n');
  ingestPersistedCampaignSettings(
    {
      image_generation_enabled: !!state.settings.image_generation_enabled,
      campaign_auto_visuals_enabled: !!state.settings.campaign_auto_visuals_enabled,
      suggested_moves_enabled: !!state.settings.effective_suggested_moves_enabled,
      campaign_auto_visual_timing: campaignSettingsPersisted?.campaign_auto_visual_timing || campaignAutoVisualTimingInput?.value || 'off',
    },
    incomingSlot,
  );
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
    clearSceneImage();
    await Promise.all([refreshMessages(), refreshState(), refreshSaves(), refreshSceneVisual()]);
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

async function pickFolder(title, inputElement) {
  try {
    const result = await api('/api/setup/pick-folder', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title, initial_path: inputElement.value.trim() }),
    });
    if (!result.ok) {
      setStatus(result.message || 'Folder selection failed.', true);
      return;
    }
    inputElement.value = result.path || '';
    setStatus(`Selected folder: ${result.path}`);
  } catch (error) {
    setStatus(error.message, true);
  }
}

async function connectOllamaFolder() {
  try {
    const path = ollamaPathInput.value.trim();
    if (!path) {
      setStatus('Pick or enter an Ollama folder path first.', true);
      return;
    }
    const result = await api('/api/setup/connect-ollama-path', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path }),
    });
    setStatus(result.message || 'Ollama folder connected.', !result.ok);
    await Promise.all([loadSettings(), refreshDependencyReadiness()]);
  } catch (error) {
    setStatus(error.message, true);
  }
}

async function connectComfyuiFolder() {
  try {
    const path = comfyuiPathInput.value.trim();
    if (!path) {
      setStatus('Pick or enter a ComfyUI folder path first.', true);
      return;
    }
    const result = await api('/api/setup/connect-comfyui-path', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path }),
    });
    setStatus(result.message || 'ComfyUI folder connected.', !result.ok);
    await Promise.all([loadSettings(), refreshDependencyReadiness(), refreshComfyuiModelList()]);
  } catch (error) {
    setStatus(error.message, true);
  }
}

function openOfficialDownload(url) {
  window.open(url, '_blank', 'noopener,noreferrer');
}

async function refreshComfyuiModelList() {
  if (!comfyuiModelsList) return;
  try {
    const payload = await api('/api/setup/comfyui-models');
    const items = payload.items || [];
    if (!items.length) {
      comfyuiModelsList.textContent = 'No curated ComfyUI models configured yet.';
      return;
    }
    const rows = items.map((item) => `
      <div class="model-row">
        <strong>${escapeHtml(item.label)}</strong>
        <div>Status: <span class="${item.present ? 'ready-badge' : 'not-ready-badge'}">${item.present ? 'Installed' : 'Not installed'}</span></div>
        <div>Target folder: <code>${escapeHtml(item.target_path || '(connect ComfyUI first)')}</code></div>
        <div><a href="${escapeHtml(item.download_url)}" target="_blank" rel="noopener noreferrer">Open download page</a></div>
      </div>
    `).join('');
    const launcher = payload.launcher_mode ? `<div class="model-row"><strong>Launcher mode</strong><div><code>${escapeHtml(payload.launcher_mode)}</code> (GPU-first preferred)</div></div>` : '';
    comfyuiModelsList.innerHTML = `${launcher}${rows}`;
  } catch (error) {
    comfyuiModelsList.textContent = `Could not load model guidance: ${error.message}`;
  }
}

function renderDependencyReadiness(payload) {
  latestDependencyReadiness = payload;
  readinessPanel.innerHTML = '';
  const byType = Object.fromEntries((payload.items || []).map((item) => [item.provider_type, item]));
  const primaryActions = payload.primary_actions || [
    { id: 'setup_text_ai', label: 'Set Up Text AI' },
    { id: 'setup_image_ai', label: 'Set Up Image AI' },
    { id: 'setup_everything', label: 'Set Up Everything' },
  ];
  const summary = document.createElement('div');
  summary.className = 'readiness-summary';
  const textReady = byType.model_provider?.status_level === 'ready' && byType.selected_model?.status_level === 'ready';
  const imageReady = byType.image_provider?.status_level === 'ready';
  summary.innerHTML = `
    <div><strong>Text AI Setup:</strong> ${textReady ? 'Ready' : 'Needs setup'}</div>
    <div><strong>Image AI Setup:</strong> ${imageReady ? 'Ready' : 'Needs setup'}</div>
    <div>Fallback story mode: available</div>
    <div>Fallback image mode: local placeholder available</div>
    <div class="readiness-action-row">
      ${primaryActions.map((action) => `<button class="readiness-action-btn primary-action-btn" data-action="${escapeHtml(action.id)}">${escapeHtml(action.label)}</button>`).join('')}
    </div>
  `;
  summary.querySelectorAll('.primary-action-btn').forEach((button) => {
    button.onclick = () => runReadinessAction(button.dataset.action, byType.selected_model || {});
  });
  updateSetupButtonsBusyState();
  readinessPanel.appendChild(summary);
  if (setupSummary) {
    setupSummary.innerHTML = `
      <div>Text AI: <span class="${textReady ? 'ready-badge' : 'not-ready-badge'}">${textReady ? 'Ready' : 'Not ready'}</span></div>
      <div>Image AI: <span class="${imageReady ? 'ready-badge' : 'not-ready-badge'}">${imageReady ? 'Ready' : 'Not ready'}</span></div>
      <div>Use <strong>AI Setup</strong> to install/connect dependencies.</div>
    `;
  }

  const sections = [
    { id: 'text', title: 'Text AI Setup', types: ['model_provider', 'selected_model'] },
    { id: 'image', title: 'Image AI Setup', types: ['image_provider'] },
  ];
  for (const sectionDef of sections) {
    const section = document.createElement('div');
    section.className = 'readiness-section';
    const sectionItems = sectionDef.types.map((type) => byType[type]).filter(Boolean);
    const overallReady = sectionItems.every((item) => item.status_level === 'ready');
    section.innerHTML = `<h4>${sectionDef.title}</h4><div class="${overallReady ? 'ready-badge' : 'not-ready-badge'}">Overall: ${overallReady ? 'Ready' : 'Needs setup'}</div>`;
    for (const item of sectionItems) {
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
    const statusCode = item.status_code ? `<div>Status: <code>${escapeHtml(toTitle(item.status_code))}</code></div>` : '<div>Status: <code>connected</code></div>';
    const fallbackInfo = item.fallback_available ? '<div>Fallback: available</div>' : '';
    const startupInfo = item.startup_status?.summary
      ? `<div>Latest startup result: ${escapeHtml(item.startup_status.summary)}</div>`
      : '';
    const startupLog = item.startup_status?.log_text
      ? `<details class="startup-log"><summary>Startup log details</summary><pre>${escapeHtml(item.startup_status.log_text)}</pre></details>`
      : '';
    el.innerHTML = `
      <strong>${escapeHtml(title)}</strong>
      <div>Provider: <code>${escapeHtml(item.provider)}</code></div>
      <div class="${badgeClass}">${ready ? 'Ready' : 'Not ready'}</div>
      ${statusCode}
      ${selectedModel}
      <div>${escapeHtml(item.user_message || '')}</div>
      ${startupInfo}
      <div>Next step: ${escapeHtml(item.next_action || 'No action needed.')}</div>
      ${fallbackInfo}
      ${startupLog}
      <div class="readiness-action-row">${actionButtons}${copyButton}</div>
    `;
    const btn = el.querySelector('.copy-cmd-btn');
    if (btn && command) {
      btn.onclick = () => copyCommand(command);
    }
    el.querySelectorAll('.readiness-action-btn').forEach((button) => {
      button.onclick = () => runReadinessAction(button.dataset.action, item);
    });
    updateSetupButtonsBusyState();
      section.appendChild(el);
    }
    readinessPanel.appendChild(section);
  }

  setupGuidance.innerHTML = '';
  const setupLines = payload.setup_checklist || payload.setup_guidance || [];
  for (const line of setupLines) {
    const li = document.createElement('li');
    li.textContent = line;
    setupGuidance.appendChild(li);
  }
  const imageProviderItem = (payload.items || []).find((item) => item.provider_type === 'image_provider');
  if (!imageProviderItem) {
    setImageStatus('Image provider status is unavailable. Click Recheck dependencies.', true);
    return;
  }
  if (imageProviderItem.status_level === 'ready') {
    setImageStatus(imageProviderItem.user_message || 'Image generation service is ready.');
  } else {
    setImageStatus(
      `${imageProviderItem.user_message || 'Image generation service is not ready.'} ${imageProviderItem.next_action || ''}`.trim(),
      true,
    );
  }
}

async function refreshDependencyReadiness() {
  const payload = await api('/api/providers/readiness');
  renderDependencyReadiness(payload);
}

async function sendInput() {
  if (turnRequestInFlight) return;
  try {
    const input = document.getElementById('chat-input');
    const sendButton = document.getElementById('send-btn');
    const text = input.value.trim();
    if (!text) return;
    const submittedAt = performance.now();
    turnRequestInFlight = true;
    input.disabled = true;
    sendButton.disabled = true;
    renderMessage({ type: 'player', text, timestamp: new Date().toISOString() });
    renderMessage({ type: 'system', text: 'Resolving turn…', timestamp: new Date().toISOString() });
    setStatus('Processing action...');
    input.value = '';
    console.log(`[turn-timing] frontend_submit_ms=0.00 submitted_at=${new Date().toISOString()}`);
    const turn = await api('/api/campaign/input', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text }) });
    const responseAt = performance.now();
    const roundTripMs = responseAt - submittedAt;
    const backendTiming = turn.metadata?.timing || {};
    const firstVisibleMs = roundTripMs - (backendTiming.save_ms || 0);
    console.log(`[turn-timing] frontend_round_trip_ms=${roundTripMs.toFixed(2)} first_visible_estimate_ms=${Math.max(firstVisibleMs, 0).toFixed(2)}`);
    input.value = '';
    const previousVisual = await refreshSceneVisual().catch(() => null);
    await Promise.all([refreshMessages(), refreshState()]);
    if (backendTiming.auto_after_image_queued) {
      setImageStatus('Generating scene image...');
      waitForSceneVisualUpdate(previousVisual?.updated_at || '').catch(() => {});
    }
    refreshSaves().catch((error) => console.warn('save list refresh failed', error));
    const modelStatus = turn.metadata?.model_status;
    if (modelStatus && modelStatus.provider === 'ollama' && !modelStatus.ready) {
      setStatus(modelStatus.user_message || 'Ollama provider is unavailable.', true);
    } else {
      setStatus('Turn processed.');
    }
  } catch (error) {
    setStatus(error.message, true);
  } finally {
    const input = document.getElementById('chat-input');
    const sendButton = document.getElementById('send-btn');
    input.disabled = false;
    sendButton.disabled = false;
    turnRequestInFlight = false;
    input.focus();
  }
}

function currentImageProviderStatus() {
  if (!latestDependencyReadiness?.items) return null;
  return latestDependencyReadiness.items.find((item) => item.provider_type === 'image_provider') || null;
}

async function generateImage() {
  let progressId = 0;
  try {
    if (manualImageEnabledInput && !manualImageEnabledInput.checked) {
      setImageStatus('Manual image generation is disabled in settings.', true);
      return;
    }
    const prompt = imagePromptInput.value.trim();
    if (!prompt) {
      setImageStatus('Enter an image prompt first.');
      return;
    }
    progressId = beginImageProgress('submitting', 'Submitting image request...');
    await refreshDependencyReadiness();
    const imageProviderStatus = currentImageProviderStatus();
    if (!imageProviderStatus || imageProviderStatus.status_level !== 'ready') {
      const detail = imageProviderStatus?.user_message || 'Image generation service is not ready.';
      const next = imageProviderStatus?.next_action ? ` ${imageProviderStatus.next_action}` : '';
      setImageStatus(`${detail}${next}`, true);
      setStatus('Image generation blocked until ComfyUI is ready.', true);
      settleImageProgress(progressId, false, 'Image generation failed');
      return;
    }
    updateImageProgress(progressId, 'accepted', 'Generating scene image...');
    const result = await api('/api/images/generate', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ workflow_id: 'scene_image', prompt }),
    });
    updateImageProgress(progressId, 'finalizing', 'Finalizing visual...');
    if (result.scene_visual?.image_url) {
      setSceneImage(result.scene_visual.image_url, result.scene_visual.prompt || prompt, result.scene_visual.turn || null);
    } else if (result.image?.url) {
      setSceneImage(result.image.url, prompt);
    }
    setImageStatus('Image generated successfully via ComfyUI.');
    setStatus('Image generated.');
  } catch (error) {
    const detail = String(error.message || 'Image generation failed.').slice(0, 700);
    setImageStatus(detail, true);
    setStatus(error.message, true);
    if (progressId) settleImageProgress(progressId, false, 'Image generation failed');
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
      world_name: document.getElementById('form-world-name').value.trim() || 'Untitled World',
      world_theme: worldTheme,
      starting_location_name: document.getElementById('form-starting-location').value.trim() || 'Starting Area',
      campaign_tone: tone,
      premise: document.getElementById('form-premise').value.trim(),
      player_concept: document.getElementById('form-player-concept').value.trim(),
      player_name: playerName,
      char_class: playerClass,
      profile: worldTheme.toLowerCase().includes('dark') ? 'dark_fantasy' : 'classic_fantasy',
      thematic_flags: worldTheme ? [worldTheme.toLowerCase().replaceAll(' ', '_'), 'adventure'] : ['adventure', 'mystery'],
      suggested_moves_enabled: !!document.getElementById('form-suggested-moves-enabled')?.checked,
      character_sheets: draftCharacterSheets,
      character_sheet_guidance_strength: document.getElementById('form-character-sheet-guidance-strength')?.value || 'light',
    };
    await api('/api/campaign/start', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
    });
    clearSceneImage();
    closeNewCampaignModal();
    await Promise.all([refreshMessages(), refreshState(), refreshSaves(), refreshSceneVisual()]);
    setStatus('New campaign started.');
  } catch (error) {
    setStatus(error.message, true);
  }
}

async function applySettings() {
  try {
    campaignSettingsApplying = true;
    renderCampaignSettingsStatus();
    if (cancelSettingsButton) cancelSettingsButton.disabled = true;
    const applyButton = document.getElementById('apply-settings');
    if (applyButton) applyButton.disabled = true;
    const modelProvider = document.getElementById('model-provider').value;
    const modelName = document.getElementById('model-name').value.trim() || 'llama3';
    const imageProvider = document.getElementById('image-provider').value;
    const campaignImageEnabled = document.getElementById('image-enabled').checked;
    const suggestedMovesEnabled = !!suggestedMovesToggleInput?.checked;
    const manualImageEnabled = !!manualImageEnabledInput?.checked;
    const campaignAutoVisualsEnabled = !!campaignAutoVisualsEnabledInput?.checked;
    const campaignAutoVisualTiming = normalizeCampaignAutoVisualTiming(campaignAutoVisualTimingInput?.value || 'off');
    const settings = await api('/api/settings/global', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model: { provider: modelProvider, model_name: modelName, ollama_path: ollamaPathInput?.value.trim() || '' },
        image: {
          provider: imageProvider,
          comfyui_path: comfyuiPathInput?.value.trim() || '',
          manual_image_generation_enabled: manualImageEnabled,
          campaign_auto_visual_timing: campaignAutoVisualTiming,
          checkpoint_source: checkpointSourceInput?.value || 'local',
          checkpoint_folder: checkpointFolderInput?.value.trim() || '',
          preferred_checkpoint: preferredCheckpointInput?.value.trim() || 'DreamShaper',
          preferred_launcher: preferredLauncherInput?.value || 'auto',
        },
      }),
    });
    const campaignSettings = await api('/api/settings/campaign', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        image_generation_enabled: campaignImageEnabled,
        campaign_auto_visuals_enabled: campaignAutoVisualsEnabled,
        player_suggested_moves_override: suggestedMovesEnabled,
      }),
    });
    await refreshDependencyReadiness();
    await refreshSupportedModels(false);
    await refreshComfyuiModelList();
    syncVisualModeUi({ manualEnabled: manualImageEnabled, autoEnabled: campaignAutoVisualsEnabled, autoTiming: campaignAutoVisualTiming });
    ingestPersistedCampaignSettings(
      {
        image_generation_enabled: !!campaignSettings.settings?.image_generation_enabled,
        campaign_auto_visuals_enabled: !!campaignSettings.settings?.campaign_auto_visuals_enabled,
        suggested_moves_enabled: !!campaignSettings.settings?.effective_suggested_moves_enabled,
        campaign_auto_visual_timing: campaignAutoVisualTiming,
      },
      loadedSlot,
      { forceUi: true },
    );
    const modelStatus = settings.settings?.model_status;
    if (modelStatus && modelStatus.provider === 'ollama' && !modelStatus.ready) {
      setStatus(modelStatus.user_message || 'Ollama provider is unavailable.', true);
    } else {
      setStatus('Settings applied.');
    }
  } catch (error) {
    setStatus(error.message, true);
  } finally {
    campaignSettingsApplying = false;
    renderCampaignSettingsStatus();
    updateCampaignDirtyState();
    const applyButton = document.getElementById('apply-settings');
    if (applyButton) applyButton.disabled = false;
  }
}

async function loadSettings() {
  const data = await api('/api/settings/global');
  document.getElementById('model-provider').value = data.settings.model.provider;
  document.getElementById('model-name').value = data.settings.model.model_name;
  document.getElementById('image-provider').value = data.settings.image.provider;
  if (manualImageEnabledInput) manualImageEnabledInput.checked = !!data.settings.image.manual_image_generation_enabled;
  const loadedTiming = normalizeCampaignAutoVisualTiming(data.settings.image.campaign_auto_visual_timing || 'off');
  if (campaignAutoVisualTimingInput) {
    campaignAutoVisualTimingInput.value = loadedTiming;
  }
  if (ollamaPathInput) ollamaPathInput.value = data.settings.model.ollama_path || '';
  if (comfyuiPathInput) comfyuiPathInput.value = data.settings.image.comfyui_path || '';
  if (checkpointFolderInput) checkpointFolderInput.value = data.settings.image.checkpoint_folder || '';
  if (checkpointSourceInput) checkpointSourceInput.value = data.settings.image.checkpoint_source || 'local';
  if (preferredCheckpointInput) preferredCheckpointInput.value = data.settings.image.preferred_checkpoint || 'DreamShaper';
  if (preferredLauncherInput) preferredLauncherInput.value = data.settings.image.preferred_launcher || 'auto';
  ingestPersistedCampaignSettings(
    {
      image_generation_enabled: campaignSettingsPersisted?.image_generation_enabled ?? document.getElementById('image-enabled').checked,
      campaign_auto_visuals_enabled: campaignSettingsPersisted?.campaign_auto_visuals_enabled ?? !!campaignAutoVisualsEnabledInput?.checked,
      suggested_moves_enabled: campaignSettingsPersisted?.suggested_moves_enabled ?? !!suggestedMovesToggleInput?.checked,
      campaign_auto_visual_timing: loadedTiming,
    },
    loadedSlot,
  );
  syncVisualModeUi({
    manualEnabled: !!(manualImageEnabledInput?.checked),
    autoEnabled: !!(campaignAutoVisualsEnabledInput?.checked),
    autoTiming: campaignAutoVisualTimingInput?.value || 'off',
  });
  const modelStatus = data.settings.model_status;
  if (modelStatus && modelStatus.provider === 'ollama' && !modelStatus.ready) {
    setStatus(modelStatus.user_message || 'Ollama provider is unavailable.', true);
  }
  renderDependencyReadiness(data.settings?.dependency_readiness || { items: [], setup_guidance: [] });
  if (data.settings?.supported_models) {
    modelInventoryState = data.settings.supported_models;
    renderSupportedModels(modelInventoryState);
  } else {
    await refreshSupportedModels(false);
  }
  await refreshComfyuiModelList();
}

document.getElementById('send-btn').onclick = sendInput;
document.getElementById('chat-input').addEventListener('keydown', (e) => { if (e.key === 'Enter') sendInput(); });
document.getElementById('load-selected').onclick = loadSelectedCampaign;
document.getElementById('load-autosave').onclick = async () => {
  try {
    await api('/api/campaign/start', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ mode: 'load', slot: 'autosave' }) });
    selectedSlot = 'autosave';
    selectedCampaignName = 'autosave';
    clearSceneImage();
    await Promise.all([refreshMessages(), refreshState(), refreshSaves(), refreshSceneVisual()]);
    setStatus('Autosave loaded.');
  } catch (error) { setStatus(error.message, true); }
};
document.getElementById('new-campaign').onclick = openNewCampaignModal;
document.getElementById('create-campaign-cancel').onclick = closeNewCampaignModal;
document.getElementById('create-campaign-confirm').onclick = createCampaignFromForm;
document.getElementById('image-generate-submit').onclick = generateImage;
document.getElementById('save-campaign').onclick = saveCampaign;
document.getElementById('rename-campaign').onclick = renameCampaign;
document.getElementById('delete-campaign').onclick = deleteCampaign;
document.getElementById('apply-settings').onclick = applySettings;
document.getElementById('open-setup-modal').onclick = openSetupModal;
document.getElementById('close-setup-modal').onclick = closeSetupModal;
document.getElementById('setup-text-ai').onclick = () => runReadinessAction('setup_text_ai', {});
document.getElementById('setup-image-ai').onclick = () => runReadinessAction('setup_image_ai', {});
document.getElementById('setup-everything').onclick = () => runReadinessAction('setup_everything', {});
document.getElementById('download-ollama').onclick = () => openOfficialDownload('https://ollama.com/download');
document.getElementById('download-comfyui').onclick = () => openOfficialDownload('https://github.com/comfyanonymous/ComfyUI');
document.getElementById('open-checkpoint-page').onclick = () => openOfficialDownload('https://civitai.com/models/4384/dreamshaper');
document.getElementById('pick-ollama-folder').onclick = () => pickFolder('Select Ollama install folder', ollamaPathInput);
document.getElementById('pick-comfyui-folder').onclick = () => pickFolder('Select ComfyUI folder', comfyuiPathInput);
document.getElementById('connect-ollama-folder').onclick = connectOllamaFolder;
document.getElementById('connect-comfyui-folder').onclick = connectComfyuiFolder;
document.getElementById('install-story-model').onclick = () => runReadinessAction('install_model', { selected_model: document.getElementById('model-name').value.trim() || 'llama3' });
document.getElementById('refresh-supported-models').onclick = async () => {
  try {
    await api('/api/models/refresh', { method: 'POST' });
    await refreshSupportedModels(true);
  } catch (error) {
    setStatus(error.message, true);
  }
};
document.getElementById('start-image-engine-from-setup').onclick = () => runReadinessAction('start_image_engine', {});
document.getElementById('recheck-readiness').onclick = async () => {
  try {
    await runReadinessAction('recheck', {});
  } catch (error) {
    setStatus(error.message, true);
  }
};
if (manualImageEnabledInput) {
  manualImageEnabledInput.onchange = () => syncVisualModeUi({
    manualEnabled: !!manualImageEnabledInput.checked,
    autoEnabled: !!(campaignAutoVisualsEnabledInput?.checked),
    autoTiming: campaignAutoVisualTimingInput?.value || 'off',
  });
}
if (campaignAutoVisualsEnabledInput) {
  campaignAutoVisualsEnabledInput.onchange = () => {
    syncVisualModeUi({
      manualEnabled: !!(manualImageEnabledInput?.checked),
      autoEnabled: !!campaignAutoVisualsEnabledInput.checked,
      autoTiming: campaignAutoVisualTimingInput?.value || 'off',
    });
    updateCampaignDirtyState();
  };
}
if (campaignAutoVisualTimingInput) {
  campaignAutoVisualTimingInput.onchange = () => {
    syncVisualModeUi({
      manualEnabled: !!(manualImageEnabledInput?.checked),
      autoEnabled: !!(campaignAutoVisualsEnabledInput?.checked),
      autoTiming: campaignAutoVisualTimingInput.value,
    });
    updateCampaignDirtyState();
  };
}
if (suggestedMovesToggleInput) {
  suggestedMovesToggleInput.onchange = () => updateCampaignDirtyState();
}
const campaignImageEnabledInput = document.getElementById('image-enabled');
if (campaignImageEnabledInput) {
  campaignImageEnabledInput.onchange = () => updateCampaignDirtyState();
}
if (cancelSettingsButton) {
  cancelSettingsButton.onclick = () => {
    applyCampaignSettingsToUi(campaignSettingsPersisted);
    updateCampaignDirtyState();
    setStatus('Reverted unsaved campaign settings.');
  };
}

document.getElementById('open-character-sheets').onclick = () => {
  characterSheetsManager?.classList.remove('hidden');
  renderCharacterSheetList();
};
document.getElementById('open-runtime-character-sheets').onclick = () => {
  console.log(`[character-sheets] viewer_opened campaign=${selectedCampaignName || loadedSlot || 'unknown'}`);
  renderRuntimeCharacterSheets();
  runtimeCharacterSheetsModal?.classList.remove('hidden');
};
document.getElementById('close-runtime-character-sheets').onclick = () => {
  runtimeCharacterSheetsModal?.classList.add('hidden');
};
document.getElementById('character-sheet-close').onclick = () => {
  characterSheetsManager?.classList.add('hidden');
};
document.getElementById('character-sheet-create').onclick = () => openSheetEditor(-1);
document.getElementById('character-sheet-cancel').onclick = () => {
  editingSheetIndex = -1;
  document.getElementById('character-sheet-editor')?.classList.add('hidden');
};
document.getElementById('character-sheet-save').onclick = () => {
  const built = buildSheetFromEditor();
  if (editingSheetIndex >= 0) draftCharacterSheets[editingSheetIndex] = built;
  else draftCharacterSheets.push(built);
  editingSheetIndex = -1;
  document.getElementById('character-sheet-editor')?.classList.add('hidden');
  renderCharacterSheetList();
};

Promise.all([refreshMessages(), refreshState(), refreshSaves(), loadSettings(), refreshDependencyReadiness(), refreshSceneVisual()]).catch((error) => setStatus(error.message, true));

console.log('[character-sheets] runtime_button_rendered=true');
console.log('[ui] left_panel_resized=true');
console.log('[ui] header_simplified=true');
console.log('[ui] turn_visuals_removed=true');
