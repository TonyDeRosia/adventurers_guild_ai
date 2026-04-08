const chatThread = document.getElementById('chat-thread');
const campaignMeta = document.getElementById('campaign-meta');
const campaignDisplayModeIndicator = document.getElementById('campaign-display-mode-indicator');
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
const selectedCampaignSummary = document.getElementById('selected-campaign-summary');
const newCampaignModal = document.getElementById('new-campaign-modal');
const campaignBrowserModal = document.getElementById('campaign-browser-modal');
const setupModal = document.getElementById('setup-modal');
const ollamaPathInput = document.getElementById('ollama-path-input');
const comfyuiPathInput = document.getElementById('comfyui-path-input');
const comfyuiWorkflowPathInput = document.getElementById('comfyui-workflow-path-input');
const comfyuiOutputDirInput = document.getElementById('comfyui-output-dir-input');
const comfyuiModelsList = document.getElementById('comfyui-models-list');
const pathConfigStatus = document.getElementById('path-config-status');
const comfyuiPathValidation = document.getElementById('comfyui-path-validation');
const workflowPathValidation = document.getElementById('comfyui-workflow-validation');
const outputPathValidation = document.getElementById('comfyui-output-validation');
const checkpointPathValidation = document.getElementById('checkpoint-folder-validation');
const checkpointFolderInput = document.getElementById('checkpoint-folder-input');
const checkpointSourceInput = document.getElementById('checkpoint-source');
const preferredCheckpointInput = document.getElementById('preferred-checkpoint');
const preferredLauncherInput = document.getElementById('preferred-launcher');
const manualImageEnabledInput = document.getElementById('manual-image-enabled');
const suggestedMovesToggleInput = document.getElementById('suggested-moves-toggle');
const allowFreeformPowersInput = document.getElementById('allow-freeform-powers');
const autoUpdateSheetFromActionsInput = document.getElementById('auto-update-sheet-from-actions');
const strictSheetEnforcementInput = document.getElementById('strict-sheet-enforcement');
const autoSyncPlayerIdentityInput = document.getElementById('auto-sync-player-identity');
const autoGenerateNpcPersonalitiesInput = document.getElementById('auto-generate-npc-personalities');
const autoEvolveNpcPersonalitiesInput = document.getElementById('auto-evolve-npc-personalities');
const reactiveWorldPersistenceInput = document.getElementById('reactive-world-persistence');
const narrationFormatModeInput = document.getElementById('narration-format-mode');
const sceneVisualModeInput = document.getElementById('scene-visual-mode');
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
const runtimeCharacterSheetCreateToggle = document.getElementById('runtime-character-sheet-create-toggle');
const runtimeCharacterSheetCreateModal = document.getElementById('runtime-character-sheet-create-modal');
const closeRuntimeCharacterSheetCreate = document.getElementById('close-runtime-character-sheet-create');
const runtimeSheetCreateName = document.getElementById('runtime-sheet-create-name');
const runtimeSheetCreateType = document.getElementById('runtime-sheet-create-type');
const runtimeSheetCreateRole = document.getElementById('runtime-sheet-create-role');
const runtimeSheetCreateCustomRoleWrap = document.getElementById('runtime-sheet-create-custom-role-wrap');
const runtimeSheetCreateCustomRole = document.getElementById('runtime-sheet-create-custom-role');
const runtimeSheetCreateArchetype = document.getElementById('runtime-sheet-create-archetype');
const runtimeSheetCreateLevelRank = document.getElementById('runtime-sheet-create-level-rank');
const runtimeSheetCreateFaction = document.getElementById('runtime-sheet-create-faction');
const runtimeSheetCreateDescription = document.getElementById('runtime-sheet-create-description');
const runtimeSheetCreateTraits = document.getElementById('runtime-sheet-create-traits');
const runtimeSheetCreateTemperament = document.getElementById('runtime-sheet-create-temperament');
const runtimeSheetCreateLoyalty = document.getElementById('runtime-sheet-create-loyalty');
const runtimeSheetCreateFear = document.getElementById('runtime-sheet-create-fear');
const runtimeSheetCreateDesire = document.getElementById('runtime-sheet-create-desire');
const runtimeSheetCreateSocialStyle = document.getElementById('runtime-sheet-create-social-style');
const runtimeSheetCreateSpeechStyle = document.getElementById('runtime-sheet-create-speech-style');
const runtimeSheetCreateAbilities = document.getElementById('runtime-sheet-create-abilities');
const runtimeSheetCreateEquipment = document.getElementById('runtime-sheet-create-equipment');
const runtimeSheetCreateWeaknesses = document.getElementById('runtime-sheet-create-weaknesses');
const runtimeSheetCreateHealth = document.getElementById('runtime-sheet-create-health');
const runtimeSheetCreateEnergy = document.getElementById('runtime-sheet-create-energy');
const runtimeSheetCreateAttack = document.getElementById('runtime-sheet-create-attack');
const runtimeSheetCreateDefense = document.getElementById('runtime-sheet-create-defense');
const runtimeSheetCreateSpeed = document.getElementById('runtime-sheet-create-speed');
const runtimeSheetCreateMagic = document.getElementById('runtime-sheet-create-magic');
const runtimeSheetCreateWillpower = document.getElementById('runtime-sheet-create-willpower');
const runtimeSheetCreatePresence = document.getElementById('runtime-sheet-create-presence');
const runtimeSheetCreateNotes = document.getElementById('runtime-sheet-create-notes');
const runtimeSheetCreateCurrentCondition = document.getElementById('runtime-sheet-create-current-condition');
const runtimeSheetCreateTrust = document.getElementById('runtime-sheet-create-trust');
const runtimeSheetCreateSuspicion = document.getElementById('runtime-sheet-create-suspicion');
const runtimeSheetCreateAnger = document.getElementById('runtime-sheet-create-anger');
const runtimeSheetCreateFearState = document.getElementById('runtime-sheet-create-fear-state');
const runtimeSheetCreateMorale = document.getElementById('runtime-sheet-create-morale');
const runtimeSheetCreateBond = document.getElementById('runtime-sheet-create-bond');
const runtimeSheetCreateGuidanceStrength = document.getElementById('runtime-sheet-create-guidance-strength');
const runtimeSheetAddGuaranteedAbility = document.getElementById('runtime-sheet-add-guaranteed-ability');
const runtimeCharacterSheetCreateSave = document.getElementById('runtime-character-sheet-create-save');
const runtimeCharacterSheetCreateCancel = document.getElementById('runtime-character-sheet-create-cancel');
const runtimeInventoryModal = document.getElementById('runtime-inventory-modal');
const runtimeInventoryDetail = document.getElementById('runtime-inventory-detail');
const runtimeSpellbookModal = document.getElementById('runtime-spellbook-modal');
const runtimeSpellbookList = document.getElementById('runtime-spellbook-list');
const narratorRulesModal = document.getElementById('narrator-rules-modal');
const narratorRulesList = document.getElementById('narrator-rules-list');
const worldBuildingModal = document.getElementById('world-building-modal');
const worldBuildingNpcList = document.getElementById('world-building-npc-list');
const worldBuildingDesignList = document.getElementById('world-building-design-list');
const worldBuildingReactiveList = document.getElementById('world-building-reactive-list');
const recalibrateWorldBuildingButton = document.getElementById('recalibrate-world-building');

let draftCharacterSheets = [];
let editingSheetIndex = -1;
let runtimeCharacterSheets = [];
let selectedRuntimeSheetId = '';
let runtimeInventoryState = {};
let runtimeSpellbookEntries = [];
let customNarratorRules = [];
let worldBuildingState = { npc_personalities: [], world_design: [], reactive_world_changes: [] };

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
let appliedVisualPipelinePaths = {
  comfyui_path: '',
  comfyui_workflow_path: '',
  comfyui_output_dir: '',
  checkpoint_folder: '',
};
let campaignSettingsPersisted = null;
let campaignSettingsDirty = false;
let campaignSettingsApplying = false;
let campaignSettingsSlot = '';
let campaignSettingsApplyTimeoutId = 0;
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
    test_image_pipeline: 'Test Image Pipeline',
  }[actionId] || actionId;
}

function normalizeNarrationFormatMode(mode) {
  const clean = String(mode || '').trim().toLowerCase();
  return ['book', 'compact', 'dialogue_focused'].includes(clean) ? clean : 'book';
}

function normalizeSceneVisualMode(mode) {
  const clean = String(mode || '').trim().toLowerCase();
  return ['off', 'manual', 'before_narration', 'after_narration'].includes(clean) ? clean : 'after_narration';
}

function playStyleSnapshotFromUi() {
  return {
    allow_freeform_powers: !!allowFreeformPowersInput?.checked,
    auto_update_character_sheet_from_actions: !!autoUpdateSheetFromActionsInput?.checked,
    strict_sheet_enforcement: !!strictSheetEnforcementInput?.checked,
    auto_sync_player_declared_identity: !!autoSyncPlayerIdentityInput?.checked,
    auto_generate_npc_personalities: !!autoGenerateNpcPersonalitiesInput?.checked,
    auto_evolve_npc_personalities: !!autoEvolveNpcPersonalitiesInput?.checked,
    reactive_world_persistence: !!reactiveWorldPersistenceInput?.checked,
    narration_format_mode: normalizeNarrationFormatMode(narrationFormatModeInput?.value || 'book'),
    scene_visual_mode: normalizeSceneVisualMode(sceneVisualModeInput?.value || 'after_narration'),
  };
}

function campaignSettingsSnapshotFromUi() {
  const playStyle = playStyleSnapshotFromUi();
  return {
    image_generation_enabled: !!document.getElementById('image-enabled')?.checked,
    suggested_moves_enabled: !!suggestedMovesToggleInput?.checked,
    play_style: playStyle,
  };
}

function campaignSettingsEqual(left, right) {
  if (!left || !right) return false;
  return (
    !!left.image_generation_enabled === !!right.image_generation_enabled
    && !!left.suggested_moves_enabled === !!right.suggested_moves_enabled
    && normalizeNarrationFormatMode(left.play_style?.narration_format_mode) === normalizeNarrationFormatMode(right.play_style?.narration_format_mode)
    && normalizeSceneVisualMode(left.play_style?.scene_visual_mode) === normalizeSceneVisualMode(right.play_style?.scene_visual_mode)
    && !!left.play_style?.allow_freeform_powers === !!right.play_style?.allow_freeform_powers
    && !!left.play_style?.auto_update_character_sheet_from_actions === !!right.play_style?.auto_update_character_sheet_from_actions
    && !!left.play_style?.strict_sheet_enforcement === !!right.play_style?.strict_sheet_enforcement
    && !!left.play_style?.auto_sync_player_declared_identity === !!right.play_style?.auto_sync_player_declared_identity
    && !!left.play_style?.auto_generate_npc_personalities === !!right.play_style?.auto_generate_npc_personalities
    && !!left.play_style?.auto_evolve_npc_personalities === !!right.play_style?.auto_evolve_npc_personalities
    && !!left.play_style?.reactive_world_persistence === !!right.play_style?.reactive_world_persistence
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

function queueAutoApplyCampaignSettings() {
  if (campaignSettingsApplyTimeoutId) {
    clearTimeout(campaignSettingsApplyTimeoutId);
  }
  campaignSettingsApplyTimeoutId = window.setTimeout(async () => {
    campaignSettingsApplyTimeoutId = 0;
    if (!campaignSettingsDirty || campaignSettingsApplying) return;
    try {
      await applySettings();
    } catch (error) {
      console.warn('auto-apply settings failed', error);
    }
  }, 150);
}

function applyCampaignSettingsToUi(snapshot) {
  if (!snapshot) return;
  document.getElementById('image-enabled').checked = !!snapshot.image_generation_enabled;
  if (suggestedMovesToggleInput) {
    suggestedMovesToggleInput.checked = !!snapshot.suggested_moves_enabled;
  }
  if (allowFreeformPowersInput) allowFreeformPowersInput.checked = !!snapshot.play_style?.allow_freeform_powers;
  if (autoUpdateSheetFromActionsInput) {
    autoUpdateSheetFromActionsInput.checked = !!snapshot.play_style?.auto_update_character_sheet_from_actions;
  }
  if (strictSheetEnforcementInput) strictSheetEnforcementInput.checked = !!snapshot.play_style?.strict_sheet_enforcement;
  if (autoSyncPlayerIdentityInput) autoSyncPlayerIdentityInput.checked = !!snapshot.play_style?.auto_sync_player_declared_identity;
  if (autoGenerateNpcPersonalitiesInput) {
    autoGenerateNpcPersonalitiesInput.checked = !!snapshot.play_style?.auto_generate_npc_personalities;
  }
  if (autoEvolveNpcPersonalitiesInput) {
    autoEvolveNpcPersonalitiesInput.checked = !!snapshot.play_style?.auto_evolve_npc_personalities;
  }
  if (reactiveWorldPersistenceInput) reactiveWorldPersistenceInput.checked = !!snapshot.play_style?.reactive_world_persistence;
  if (narrationFormatModeInput) narrationFormatModeInput.value = normalizeNarrationFormatMode(snapshot.play_style?.narration_format_mode);
  if (sceneVisualModeInput) sceneVisualModeInput.value = normalizeSceneVisualMode(snapshot.play_style?.scene_visual_mode);
  syncVisualModeUi({ manualEnabled: !!(manualImageEnabledInput?.checked) });
}

function ingestPersistedCampaignSettings(snapshot, slot, { forceUi = false } = {}) {
  const normalized = {
    image_generation_enabled: !!snapshot.image_generation_enabled,
    suggested_moves_enabled: !!snapshot.suggested_moves_enabled,
    display_mode: normalizeDisplayMode(snapshot.display_mode || 'story'),
    play_style: {
      allow_freeform_powers: !!snapshot.play_style?.allow_freeform_powers,
      auto_update_character_sheet_from_actions: !!snapshot.play_style?.auto_update_character_sheet_from_actions,
      strict_sheet_enforcement: !!snapshot.play_style?.strict_sheet_enforcement,
      auto_sync_player_declared_identity: !!snapshot.play_style?.auto_sync_player_declared_identity,
      auto_generate_npc_personalities: !!snapshot.play_style?.auto_generate_npc_personalities,
      auto_evolve_npc_personalities: !!snapshot.play_style?.auto_evolve_npc_personalities,
      reactive_world_persistence: !!snapshot.play_style?.reactive_world_persistence,
      narration_format_mode: normalizeNarrationFormatMode(snapshot.play_style?.narration_format_mode || 'book'),
      scene_visual_mode: normalizeSceneVisualMode(snapshot.play_style?.scene_visual_mode || 'after_narration'),
    },
  };
  const slotChanged = campaignSettingsSlot && slot && campaignSettingsSlot !== slot;
  campaignSettingsPersisted = normalized;
  campaignSettingsSlot = slot || campaignSettingsSlot || loadedSlot || 'autosave';
  if (slotChanged || forceUi || !campaignSettingsDirty) {
    applyCampaignSettingsToUi(normalized);
  }
  updateCampaignDirtyState();
}

function syncVisualModeUi({ manualEnabled }) {
  if (manualImagePanel) {
    manualImagePanel.style.display = manualEnabled ? 'grid' : 'none';
  }
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
  const managedButtons = document.querySelectorAll('#setup-text-ai, #setup-image-ai, #setup-everything, #recheck-readiness, #test-image-pipeline-from-setup, .readiness-action-btn');
  managedButtons.forEach((button) => {
    const actionId = button.dataset.action || (button.id === 'setup-text-ai' ? 'setup_text_ai'
      : button.id === 'setup-image-ai' ? 'setup_image_ai'
      : button.id === 'setup-everything' ? 'setup_everything'
      : button.id === 'recheck-readiness' ? 'recheck'
      : button.id === 'test-image-pipeline-from-setup' ? 'test_image_pipeline'
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

    if (actionId === 'test_image_pipeline') {
      startSetupRun(actionId, 'Running end-to-end image pipeline test...', [
        { step: 'comfyui_reachable', label: 'ComfyUI reachable', state: 'running', message: 'Checking ComfyUI endpoint...' },
        { step: 'workflow_load', label: 'Workflow load', state: 'pending', message: 'Validating workflow JSON...' },
        { step: 'checkpoint_available', label: 'Checkpoint check', state: 'pending', message: 'Checking available checkpoints...' },
        { step: 'prompt_submission', label: 'Prompt submit', state: 'pending', message: 'Submitting test prompt...' },
        { step: 'history_output', label: 'History output', state: 'pending', message: 'Waiting for generated image...' },
      ]);
      setStatus('Testing image pipeline...');
      const result = await api('/api/setup/test-image-pipeline', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ prompt: 'test fantasy portrait' }),
      });
      const finalSteps = normalizeSetupSteps(setupRunState.steps.map((step) => ({
        ...step,
        state: result.success ? 'ready' : (step.step === result.failing_step ? 'error' : (step.state === 'running' ? 'pending' : step.state)),
        message: result.success ? 'Passed' : (step.step === result.failing_step ? (result.message || 'Failed') : step.message),
      })));
      finishSetupRun({
        summary: result.message || (result.success ? 'Image pipeline test passed.' : 'Image pipeline test failed.'),
        isError: !result.success,
        steps: finalSteps,
      });
      setStatus(result.message || (result.success ? 'Image pipeline test passed.' : 'Image pipeline test failed.'), !result.success);
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

function renderSelectedCampaignSummary() {
  if (!selectedCampaignSummary) return;
  const selectedCampaign = lastCampaigns.find((campaign) => campaign.slot === selectedSlot);
  if (!selectedCampaign) {
    selectedCampaignSummary.innerHTML = '<strong>No save selected</strong><small>Select a campaign to view details.</small>';
    return;
  }
  const mode = normalizeDisplayMode(
    selectedCampaign.display_mode
    || (selectedCampaign.slot === loadedSlot ? campaignSettingsPersisted?.display_mode : 'story'),
  );
  selectedCampaignSummary.innerHTML = `
    <strong>${escapeHtml(selectedCampaign.campaign_name || selectedCampaign.slot)}</strong>
    <small>${escapeHtml(selectedCampaign.world_name || 'Unknown world')} · Turn ${Number(selectedCampaign.turn_count || 0)}</small>
    <small>Display Mode: ${displayModeLabel(mode)}</small>
  `;
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

function openCampaignBrowser() {
  campaignBrowserModal?.classList.remove('hidden');
}

function closeCampaignBrowser() {
  campaignBrowserModal?.classList.add('hidden');
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

function normalizeDisplayMode(mode) {
  const clean = String(mode || '').trim().toLowerCase();
  return ['story', 'mud', 'rpg'].includes(clean) ? clean : 'story';
}

function displayModeLabel(mode) {
  return {
    story: 'Story Mode',
    mud: 'MUD Mode',
    rpg: 'RPG Mode',
  }[normalizeDisplayMode(mode)];
}

function addGuaranteedAbilityEditorRow(entry = {}, options = {}) {
  const { containerId = 'sheet-guaranteed-abilities', fieldPrefix = 'ga' } = options;
  const container = document.getElementById(containerId);
  if (!container) return;
  const row = document.createElement('div');
  row.className = 'sheet-ability-entry';
  row.innerHTML = `
    <label class="sheet-ability-half">Name <input data-${fieldPrefix}-field="name" type="text" value="${escapeHtml(entry.name || '')}" /></label>
    <label class="sheet-ability-half">Type
      <select data-${fieldPrefix}-field="type">
        <option value="spell">Spell</option>
        <option value="skill">Skill</option>
        <option value="ability">Ability</option>
        <option value="passive">Passive</option>
      </select>
    </label>
    <label class="sheet-ability-half">Description <input data-${fieldPrefix}-field="description" type="text" value="${escapeHtml(entry.description || '')}" /></label>
    <label class="sheet-ability-half">Cost / Resource <input data-${fieldPrefix}-field="cost_or_resource" type="text" value="${escapeHtml(entry.cost_or_resource || '')}" /></label>
    <label class="sheet-ability-half">Cooldown <input data-${fieldPrefix}-field="cooldown" type="text" value="${escapeHtml(entry.cooldown || '')}" /></label>
    <label class="sheet-ability-half">Tags (comma separated) <input data-${fieldPrefix}-field="tags" type="text" value="${escapeHtml((entry.tags || []).join(', '))}" /></label>
    <label class="sheet-ability-full">Notes <textarea data-${fieldPrefix}-field="notes" rows="2">${escapeHtml(entry.notes || '')}</textarea></label>
    <div class="button-row sheet-ability-actions"><button type="button" data-${fieldPrefix}-remove="true">Remove</button></div>
  `;
  const typeSelect = row.querySelector(`select[data-${fieldPrefix}-field="type"]`);
  if (typeSelect) typeSelect.value = entry.type || 'ability';
  row.querySelector(`button[data-${fieldPrefix}-remove="true"]`)?.addEventListener('click', () => row.remove());
  container.appendChild(row);
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
    runtimeCharacterSheetsList.innerHTML = `
      <div class="runtime-sheets-empty-state">
        <p>No character sheets attached yet.</p>
        <button type="button" id="runtime-character-sheet-empty-create">Create Character Sheet</button>
      </div>
    `;
    runtimeCharacterSheetsList.querySelector('#runtime-character-sheet-empty-create')?.addEventListener('click', () => {
      runtimeCharacterSheetCreateModal?.classList.remove('hidden');
      console.log('[character-sheets] create_modal_opened=true');
      runtimeSheetCreateName?.focus();
    });
    runtimeCharacterSheetDetail.textContent = 'Create a character sheet to view details here.';
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
      console.log(`[character-sheets] selected=${selectedRuntimeSheetId || 'none'}`);
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
  const guaranteed = Array.isArray(sheet.guaranteed_abilities) ? sheet.guaranteed_abilities : [];
  const listMarkup = (entries, emptyText = 'None') => {
    const clean = Array.isArray(entries) ? entries.filter((entry) => String(entry || '').trim()) : [];
    if (!clean.length) return `<p class="runtime-sheet-muted">${escapeHtml(emptyText)}</p>`;
    return `<ul class="runtime-sheet-list">${clean.map((entry) => `<li>${escapeHtml(entry)}</li>`).join('')}</ul>`;
  };
  const guaranteedMarkup = guaranteed.length
    ? `<ul class="runtime-sheet-list">${guaranteed.map((entry) => `<li>${escapeHtml(`${entry.type || 'ability'}: ${entry.name || 'Unnamed'}`)}</li>`).join('')}</ul>`
    : '<p class="runtime-sheet-muted">No guaranteed abilities.</p>';
  const baseDetails = [
    ['Role', sheet.role],
    ['Archetype', sheet.archetype],
    ['Faction', sheet.faction],
    ['Level / Rank', sheet.level_or_rank],
    ['Description', sheet.description],
    ['Condition', sheet.state?.current_condition],
    ['Notes', sheet.notes],
  ].filter(([, value]) => String(value || '').trim());
  runtimeCharacterSheetDetail.innerHTML = `
    <article class="runtime-sheet-card">
      <h4>${escapeHtml(sheet.name || 'Unnamed')} • ${escapeHtml(sheet.sheet_type || 'unknown')}</h4>
      <section class="runtime-sheet-section">
        <h5>Profile</h5>
        ${baseDetails.length ? `<dl>${baseDetails.map(([label, value]) => `<dt>${escapeHtml(label)}</dt><dd>${escapeHtml(String(value))}</dd>`).join('')}</dl>` : '<p class="runtime-sheet-muted">No profile metadata.</p>'}
      </section>
      <section class="runtime-sheet-section">
        <h5>Stats</h5>
        <div class="runtime-sheet-grid">
          <div><span>HP</span><strong>${Number(stats.health ?? 0)}</strong></div>
          <div><span>Energy</span><strong>${Number(stats.energy_or_mana ?? 0)}</strong></div>
          <div><span>Attack</span><strong>${Number(stats.attack ?? 0)}</strong></div>
          <div><span>Defense</span><strong>${Number(stats.defense ?? 0)}</strong></div>
          <div><span>Speed</span><strong>${Number(stats.speed ?? 0)}</strong></div>
          <div><span>Magic</span><strong>${Number(stats.magic ?? 0)}</strong></div>
          <div><span>Willpower</span><strong>${Number(stats.willpower ?? 0)}</strong></div>
          <div><span>Presence</span><strong>${Number(stats.presence ?? 0)}</strong></div>
        </div>
      </section>
      <section class="runtime-sheet-section">
        <h5>Attributes</h5>
        <div class="runtime-sheet-grid">
          <div><span>STR</span><strong>${classic.strength ?? '—'}</strong></div>
          <div><span>DEX</span><strong>${classic.dexterity ?? '—'}</strong></div>
          <div><span>CON</span><strong>${classic.constitution ?? '—'}</strong></div>
          <div><span>INT</span><strong>${classic.intelligence ?? '—'}</strong></div>
          <div><span>WIS</span><strong>${classic.wisdom ?? '—'}</strong></div>
          <div><span>CHA</span><strong>${classic.charisma ?? '—'}</strong></div>
        </div>
      </section>
      <section class="runtime-sheet-section">
        <h5>Traits & Loadout</h5>
        <p><strong>Traits</strong></p>${listMarkup(sheet.traits, 'No traits listed.')}
        <p><strong>Abilities</strong></p>${listMarkup(sheet.abilities, 'No abilities listed.')}
        <p><strong>Guaranteed Abilities</strong></p>${guaranteedMarkup}
        <p><strong>Equipment</strong></p>${listMarkup(sheet.equipment, 'No equipment listed.')}
        <p><strong>Weaknesses</strong></p>${listMarkup(sheet.weaknesses, 'No weaknesses listed.')}
      </section>
    </article>
  `;
}

function resetRuntimeSheetCreateForm() {
  if (runtimeSheetCreateName) runtimeSheetCreateName.value = '';
  if (runtimeSheetCreateType) runtimeSheetCreateType.value = 'npc_or_mob';
  if (runtimeSheetCreateRole) runtimeSheetCreateRole.value = 'companion';
  if (runtimeSheetCreateCustomRole) runtimeSheetCreateCustomRole.value = '';
  if (runtimeSheetCreateArchetype) runtimeSheetCreateArchetype.value = '';
  if (runtimeSheetCreateLevelRank) runtimeSheetCreateLevelRank.value = '';
  if (runtimeSheetCreateFaction) runtimeSheetCreateFaction.value = '';
  if (runtimeSheetCreateDescription) runtimeSheetCreateDescription.value = '';
  if (runtimeSheetCreateTraits) runtimeSheetCreateTraits.value = '';
  if (runtimeSheetCreateTemperament) runtimeSheetCreateTemperament.value = '';
  if (runtimeSheetCreateLoyalty) runtimeSheetCreateLoyalty.value = '';
  if (runtimeSheetCreateFear) runtimeSheetCreateFear.value = '';
  if (runtimeSheetCreateDesire) runtimeSheetCreateDesire.value = '';
  if (runtimeSheetCreateSocialStyle) runtimeSheetCreateSocialStyle.value = '';
  if (runtimeSheetCreateSpeechStyle) runtimeSheetCreateSpeechStyle.value = '';
  if (runtimeSheetCreateAbilities) runtimeSheetCreateAbilities.value = '';
  if (runtimeSheetCreateEquipment) runtimeSheetCreateEquipment.value = '';
  if (runtimeSheetCreateWeaknesses) runtimeSheetCreateWeaknesses.value = '';
  if (runtimeSheetCreateHealth) runtimeSheetCreateHealth.value = '10';
  if (runtimeSheetCreateEnergy) runtimeSheetCreateEnergy.value = '10';
  if (runtimeSheetCreateAttack) runtimeSheetCreateAttack.value = '10';
  if (runtimeSheetCreateDefense) runtimeSheetCreateDefense.value = '10';
  if (runtimeSheetCreateSpeed) runtimeSheetCreateSpeed.value = '10';
  if (runtimeSheetCreateMagic) runtimeSheetCreateMagic.value = '10';
  if (runtimeSheetCreateWillpower) runtimeSheetCreateWillpower.value = '10';
  if (runtimeSheetCreatePresence) runtimeSheetCreatePresence.value = '10';
  if (runtimeSheetCreateNotes) runtimeSheetCreateNotes.value = '';
  if (runtimeSheetCreateCurrentCondition) runtimeSheetCreateCurrentCondition.value = '';
  if (runtimeSheetCreateTrust) runtimeSheetCreateTrust.value = '';
  if (runtimeSheetCreateSuspicion) runtimeSheetCreateSuspicion.value = '';
  if (runtimeSheetCreateAnger) runtimeSheetCreateAnger.value = '';
  if (runtimeSheetCreateFearState) runtimeSheetCreateFearState.value = '';
  if (runtimeSheetCreateMorale) runtimeSheetCreateMorale.value = '';
  if (runtimeSheetCreateBond) runtimeSheetCreateBond.value = '';
  if (runtimeSheetCreateGuidanceStrength) runtimeSheetCreateGuidanceStrength.value = 'light';
  const guaranteedContainer = document.getElementById('runtime-sheet-guaranteed-abilities');
  if (guaranteedContainer) guaranteedContainer.innerHTML = '';
  addGuaranteedAbilityEditorRow({}, { containerId: 'runtime-sheet-guaranteed-abilities', fieldPrefix: 'rga' });
  runtimeSheetCreateCustomRoleWrap?.classList.add('hidden');
}

function currentRuntimeSheetRole() {
  const selectedRole = (runtimeSheetCreateRole?.value || '').trim();
  if (selectedRole === 'custom') return (runtimeSheetCreateCustomRole?.value || '').trim();
  return selectedRole;
}

async function createRuntimeCharacterSheet() {
  const numberOrNull = (input) => {
    const value = input?.value ?? '';
    if (value === '') return null;
    return Number(value);
  };
  const guaranteedAbilities = Array.from(document.querySelectorAll('#runtime-sheet-guaranteed-abilities .sheet-ability-entry')).map((row) => {
    const valueFor = (field) => (row.querySelector(`[data-rga-field="${field}"]`)?.value || '').trim();
    return {
      name: valueFor('name'),
      type: valueFor('type') || 'ability',
      description: valueFor('description'),
      cost_or_resource: valueFor('cost_or_resource'),
      cooldown: valueFor('cooldown'),
      tags: parseCsv(valueFor('tags')),
      notes: valueFor('notes'),
    };
  }).filter((entry) => entry.name);
  const role = currentRuntimeSheetRole() || 'companion';
  console.log(`[character-sheets] create_requested role=${role}`);
  const result = await api('/api/campaign/character-sheets', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      action: 'create',
      name: runtimeSheetCreateName?.value?.trim() || '',
      sheet_type: runtimeSheetCreateType?.value || 'npc_or_mob',
      role,
      archetype: runtimeSheetCreateArchetype?.value?.trim() || '',
      level_or_rank: runtimeSheetCreateLevelRank?.value?.trim() || '',
      faction: runtimeSheetCreateFaction?.value?.trim() || '',
      description: runtimeSheetCreateDescription?.value?.trim() || '',
      traits: parseCsv(runtimeSheetCreateTraits?.value || ''),
      temperament: runtimeSheetCreateTemperament?.value?.trim() || '',
      loyalty: runtimeSheetCreateLoyalty?.value?.trim() || '',
      fear: runtimeSheetCreateFear?.value?.trim() || '',
      desire: runtimeSheetCreateDesire?.value?.trim() || '',
      social_style: runtimeSheetCreateSocialStyle?.value?.trim() || '',
      speech_style: runtimeSheetCreateSpeechStyle?.value?.trim() || '',
      abilities: parseCsv(runtimeSheetCreateAbilities?.value || ''),
      guaranteed_abilities: guaranteedAbilities,
      equipment: parseCsv(runtimeSheetCreateEquipment?.value || ''),
      weaknesses: parseCsv(runtimeSheetCreateWeaknesses?.value || ''),
      notes: runtimeSheetCreateNotes?.value?.trim() || '',
      state: {
        trust: numberOrNull(runtimeSheetCreateTrust),
        suspicion: numberOrNull(runtimeSheetCreateSuspicion),
        anger: numberOrNull(runtimeSheetCreateAnger),
        fear_state: numberOrNull(runtimeSheetCreateFearState),
        morale: numberOrNull(runtimeSheetCreateMorale),
        bond_to_player: numberOrNull(runtimeSheetCreateBond),
        current_condition: runtimeSheetCreateCurrentCondition?.value?.trim() || '',
      },
      guidance_strength: runtimeSheetCreateGuidanceStrength?.value || 'light',
      stats: {
        health: Number(runtimeSheetCreateHealth?.value || 10),
        energy_or_mana: Number(runtimeSheetCreateEnergy?.value || 10),
        attack: Number(runtimeSheetCreateAttack?.value || 10),
        defense: Number(runtimeSheetCreateDefense?.value || 10),
        speed: Number(runtimeSheetCreateSpeed?.value || 10),
        magic: Number(runtimeSheetCreateMagic?.value || 10),
        willpower: Number(runtimeSheetCreateWillpower?.value || 10),
        presence: Number(runtimeSheetCreatePresence?.value || 10),
      },
    }),
  });
  runtimeCharacterSheets = Array.isArray(result.character_sheets) ? result.character_sheets : runtimeCharacterSheets;
  selectedRuntimeSheetId = result.created_id || selectedRuntimeSheetId;
  console.log(`[character-sheets] created id=${result.created_id || 'unknown'} total=${runtimeCharacterSheets.length}`);
  console.log(`[character-sheets] selected=${selectedRuntimeSheetId || 'none'}`);
  renderRuntimeCharacterSheets();
  runtimeCharacterSheetCreateModal?.classList.add('hidden');
  resetRuntimeSheetCreateForm();
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
  const guaranteedContainer = document.getElementById('sheet-guaranteed-abilities');
  if (guaranteedContainer) guaranteedContainer.innerHTML = '';
  const guaranteedEntries = Array.isArray(existing?.guaranteed_abilities) ? existing.guaranteed_abilities : [];
  if (guaranteedEntries.length) {
    guaranteedEntries.forEach((entry) => addGuaranteedAbilityEditorRow(entry));
  } else {
    addGuaranteedAbilityEditorRow();
  }
  editor.classList.remove('hidden');
}

function buildSheetFromEditor() {
  const sheetId = `sheet_${Date.now()}_${Math.floor(Math.random() * 1000)}`;
  const numberOrNull = (id) => {
    const value = document.getElementById(id).value;
    if (value === '') return null;
    return Number(value);
  };
  const guaranteedAbilities = Array.from(document.querySelectorAll('#sheet-guaranteed-abilities .sheet-ability-entry')).map((row) => {
    const valueFor = (field) => (row.querySelector(`[data-ga-field="${field}"]`)?.value || '').trim();
    return {
      name: valueFor('name'),
      type: valueFor('type') || 'ability',
      description: valueFor('description'),
      cost_or_resource: valueFor('cost_or_resource'),
      cooldown: valueFor('cooldown'),
      tags: parseCsv(valueFor('tags')),
      notes: valueFor('notes'),
    };
  }).filter((entry) => entry.name);
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
    guaranteed_abilities: guaranteedAbilities,
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
  const readableCaption = (caption || '').trim();
  currentSceneImagePrompt = readableCaption;
  currentSceneImageTurn = turn;
  imageHistory = [{ url, caption: readableCaption, turn }, ...imageHistory.filter((entry) => entry.url !== url)].slice(0, 30);
  sceneImageDisplay.innerHTML = '';
  const img = document.createElement('img');
  img.src = url;
  img.alt = readableCaption || 'Generated scene image';
  sceneImageDisplay.appendChild(img);
  if (sceneVisualMeta) {
    sceneVisualMeta.textContent = readableCaption || (turn ? `Scene visual updated for Turn ${turn}.` : 'Scene visual reflects the current area.');
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
    setSceneImage(sceneVisual.image_url, sceneVisual.caption || 'Latest generated image loaded in Scene Visual.', sceneVisual.turn || null);
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

function normalizeSpellbookEntry(entry = {}) {
  return {
    id: entry.id || '',
    name: entry.name || '',
    type: ['spell', 'skill', 'ability', 'passive'].includes(entry.type) ? entry.type : 'ability',
    description: entry.description || '',
    cost_or_resource: entry.cost_or_resource || '',
    cooldown: entry.cooldown || '',
    tags: Array.isArray(entry.tags) ? entry.tags : [],
    notes: entry.notes || '',
  };
}

function renderInventoryViewer() {
  if (!runtimeInventoryDetail) return;
  const state = runtimeInventoryState || {};
  const groups = ['items', 'weapons', 'armor', 'consumables', 'key_items'];
  runtimeInventoryDetail.innerHTML = groups.map((group) => {
    const entries = Array.isArray(state[group]) ? state[group] : [];
    return `<div class="spellbook-group"><strong>${escapeHtml(group.replace('_', ' ').toUpperCase())}</strong><div>${escapeHtml(entries.join(', ') || 'None')}</div></div>`;
  }).join('') + `
    <div class="spellbook-group"><strong>CURRENCY</strong><div>${escapeHtml(JSON.stringify(state.currency || { gold: 0, silver: 0, copper: 0 }))}</div></div>
    <div class="spellbook-group"><strong>EQUIPPED</strong><div>${escapeHtml(JSON.stringify(state.equipped || {}))}</div></div>
  `;
}

function renderSpellbookViewer() {
  if (!runtimeSpellbookList) return;
  const grouped = { spell: [], skill: [], ability: [], passive: [] };
  runtimeSpellbookEntries.forEach((entry) => {
    const clean = normalizeSpellbookEntry(entry);
    grouped[clean.type].push(clean);
  });
  runtimeSpellbookList.innerHTML = ['spell', 'skill', 'ability', 'passive'].map((type) => {
    const entries = grouped[type];
    const rows = entries.length ? entries.map((entry) => `
      <div class="spellbook-entry">
        <strong>${escapeHtml(entry.name)}</strong> <small>(${escapeHtml(type)})</small>
        <div>${escapeHtml(entry.description || 'No description')}</div>
        <div>Cost: ${escapeHtml(entry.cost_or_resource || '-')} • Cooldown: ${escapeHtml(entry.cooldown || '-')}</div>
        <div>Tags: ${escapeHtml((entry.tags || []).join(', ') || '-')}</div>
        <div>Notes: ${escapeHtml(entry.notes || '-')}</div>
        <div class="button-row compact-row">
          <button type="button" data-spellbook-edit="${escapeHtml(entry.id)}">Edit</button>
          <button type="button" data-spellbook-delete="${escapeHtml(entry.id)}">Delete</button>
        </div>
      </div>
    `).join('') : '<div>None</div>';
    return `<div class="spellbook-group"><h4>${escapeHtml(type[0].toUpperCase() + type.slice(1))}s</h4>${rows}</div>`;
  }).join('');
  runtimeSpellbookList.querySelectorAll('button[data-spellbook-edit]').forEach((button) => {
    button.onclick = () => {
      const entry = runtimeSpellbookEntries.find((candidate) => candidate.id === button.dataset.spellbookEdit);
      if (!entry) return;
      document.getElementById('spellbook-entry-id').value = entry.id;
      document.getElementById('spellbook-entry-name').value = entry.name;
      document.getElementById('spellbook-entry-type').value = entry.type;
      document.getElementById('spellbook-entry-description').value = entry.description;
      document.getElementById('spellbook-entry-cost').value = entry.cost_or_resource;
      document.getElementById('spellbook-entry-cooldown').value = entry.cooldown;
      document.getElementById('spellbook-entry-tags').value = (entry.tags || []).join(', ');
      document.getElementById('spellbook-entry-notes').value = entry.notes;
    };
  });
  runtimeSpellbookList.querySelectorAll('button[data-spellbook-delete]').forEach((button) => {
    button.onclick = async () => {
      await api('/api/campaign/spellbook', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'delete', id: button.dataset.spellbookDelete }),
      });
      await refreshSpellbook();
      renderSpellbookViewer();
    };
  });
}

async function refreshInventory() {
  const payload = await api('/api/campaign/inventory');
  runtimeInventoryState = payload.inventory || {};
  renderInventoryViewer();
}

async function refreshSpellbook() {
  const payload = await api('/api/campaign/spellbook');
  runtimeSpellbookEntries = Array.isArray(payload.spellbook) ? payload.spellbook.map(normalizeSpellbookEntry) : [];
  renderSpellbookViewer();
}

function renderNarratorRules() {
  if (!narratorRulesList) return;
  if (!customNarratorRules.length) {
    narratorRulesList.textContent = 'No custom narrator rules yet.';
    return;
  }
  narratorRulesList.innerHTML = '';
  customNarratorRules.forEach((entry) => {
    const card = document.createElement('div');
    card.className = 'narrator-rule-item';
    card.innerHTML = `<p>${escapeHtml(entry.text || '')}</p>`;
    const actions = document.createElement('div');
    actions.className = 'button-row';
    const editBtn = document.createElement('button');
    editBtn.type = 'button';
    editBtn.textContent = 'Edit';
    editBtn.onclick = () => {
      document.getElementById('narrator-rule-edit-id').value = entry.id;
      document.getElementById('narrator-rule-input').value = entry.text || '';
    };
    const deleteBtn = document.createElement('button');
    deleteBtn.type = 'button';
    deleteBtn.textContent = 'Delete';
    deleteBtn.onclick = async () => {
      const result = await api('/api/campaign/narrator-rules', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'delete', id: entry.id }),
      });
      customNarratorRules = Array.isArray(result.rules) ? result.rules : [];
      renderNarratorRules();
      console.log(`[narrator-rules] rule_deleted campaign=${loadedSlot || 'unknown'} count=${customNarratorRules.length}`);
    };
    actions.appendChild(editBtn);
    actions.appendChild(deleteBtn);
    card.appendChild(actions);
    narratorRulesList.appendChild(card);
  });
}

async function refreshNarratorRules() {
  const payload = await api('/api/campaign/narrator-rules');
  customNarratorRules = Array.isArray(payload.rules) ? payload.rules : [];
  renderNarratorRules();
}

function renderWorldBuildingBulletList(items, emptyText) {
  const clean = Array.isArray(items) ? items.filter((item) => String(item || '').trim()) : [];
  if (!clean.length) return `<p class="runtime-sheet-muted">${escapeHtml(emptyText)}</p>`;
  return `<ul class="world-building-bullet-list">${clean.map((item) => `<li>${escapeHtml(item)}</li>`).join('')}</ul>`;
}

function renderWorldBuildingViewer() {
  if (!worldBuildingNpcList || !worldBuildingDesignList || !worldBuildingReactiveList) return;
  const npcProfiles = Array.isArray(worldBuildingState.npc_personalities) ? worldBuildingState.npc_personalities : [];
  const worldDesign = Array.isArray(worldBuildingState.world_design) ? worldBuildingState.world_design : [];
  const reactiveChanges = Array.isArray(worldBuildingState.reactive_world_changes) ? worldBuildingState.reactive_world_changes : [];

  worldBuildingNpcList.innerHTML = npcProfiles.length ? npcProfiles.map((profile) => `
    <article class="world-building-card">
      <h5>${escapeHtml(profile.name || 'Unnamed NPC')} <small>${escapeHtml(profile.role_or_archetype || 'Unknown role')}</small></h5>
      <div class="world-building-grid">
        <div><span>Personality Summary</span><p>${escapeHtml(profile.personality_summary || 'Not available')}</p></div>
        <div><span>Social Style</span><p>${escapeHtml(profile.social_style || 'Not available')}</p></div>
        <div><span>Likely Motivations</span><p>${escapeHtml(profile.likely_motivations || 'Not available')}</p></div>
        <div><span>Speaking Style</span><p>${escapeHtml(profile.speaking_style || 'Not available')}</p></div>
        <div><span>Conflict Style</span><p>${escapeHtml(profile.conflict_style || 'Not available')}</p></div>
        <div><span>Current Stance Toward Player</span><p>${escapeHtml(profile.current_stance_toward_player || 'Not available')}</p></div>
        <div><span>Persistent Conditions</span>${renderWorldBuildingBulletList(profile.current_persistent_conditions || [], 'None recorded.')}</div>
        <div><span>Notable Evolution</span><p>${escapeHtml(profile.notable_evolution || 'Not available')}</p></div>
      </div>
    </article>
  `).join('') : '<p class="runtime-sheet-muted">No NPC personalities generated yet.</p>';

  worldBuildingDesignList.innerHTML = worldDesign.length ? worldDesign.map((group) => `
    <article class="world-building-card">
      <h5>${escapeHtml(group.label || 'World Design')}</h5>
      ${renderWorldBuildingBulletList(group.entries || [], `No ${String(group.label || 'entries').toLowerCase()} available yet.`)}
    </article>
  `).join('') : '<p class="runtime-sheet-muted">No world design entries available yet.</p>';

  worldBuildingReactiveList.innerHTML = reactiveChanges.length ? reactiveChanges.map((group) => `
    <article class="world-building-card">
      <h5>${escapeHtml(group.label || 'Reactive Changes')}</h5>
      ${renderWorldBuildingBulletList(group.entries || [], `No ${String(group.label || 'entries').toLowerCase()} available yet.`)}
    </article>
  `).join('') : '<p class="runtime-sheet-muted">No reactive world changes recorded yet.</p>';
}

async function refreshWorldBuilding() {
  const payload = await api('/api/campaign/world-building');
  worldBuildingState = payload.world_building || { npc_personalities: [], world_design: [], reactive_world_changes: [] };
  renderWorldBuildingViewer();
}

async function recalibrateWorldBuilding() {
  if (!recalibrateWorldBuildingButton) return;
  const idleLabel = 'Recalibrate';
  recalibrateWorldBuildingButton.disabled = true;
  recalibrateWorldBuildingButton.textContent = 'Recalibrating...';
  try {
    await api('/api/campaign/recalibrate', { method: 'POST' });
    await refreshWorldBuilding();
    await refreshState();
    setStatus('Recalibration complete.');
  } catch (error) {
    setStatus(`Recalibration failed: ${error.message}`, true);
  } finally {
    recalibrateWorldBuildingButton.disabled = false;
    recalibrateWorldBuildingButton.textContent = idleLabel;
  }
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
  runtimeInventoryState = state.inventory_state || runtimeInventoryState || {};
  runtimeSpellbookEntries = Array.isArray(state.spellbook) ? state.spellbook.map(normalizeSpellbookEntry) : [];
  customNarratorRules = Array.isArray(state.custom_narrator_rules) ? state.custom_narrator_rules : [];
  renderRuntimeCharacterSheets();
  renderInventoryViewer();
  renderSpellbookViewer();
  renderNarratorRules();
  campaignMeta.textContent = `${state.campaign_name || 'Campaign'} · Turn ${state.turn_count || 0}`;
  if (campaignDisplayModeIndicator) {
    campaignDisplayModeIndicator.textContent = `Display Mode: ${displayModeLabel(state.settings?.display_mode || 'story')}`;
  }
  ingestPersistedCampaignSettings(
    {
      image_generation_enabled: !!state.settings.image_generation_enabled,
      suggested_moves_enabled: !!state.settings.effective_suggested_moves_enabled,
      display_mode: normalizeDisplayMode(state.settings?.display_mode || 'story'),
      play_style: state.settings?.play_style || campaignSettingsPersisted?.play_style || playStyleSnapshotFromUi(),
    },
    incomingSlot,
  );
  updateSelectedSaveLabel();
  renderSelectedCampaignSummary();
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
    renderSelectedCampaignSummary();
    saveList.textContent = 'No saves found yet.';
    return;
  }
  if (!campaigns.some((campaign) => campaign.slot === selectedSlot)) {
    selectedSlot = loadedSlot;
  }
  campaigns.forEach((campaign) => {
    const btn = document.createElement('button');
    btn.className = `save-item ${campaign.slot === selectedSlot ? 'selected' : ''}`;
    btn.innerHTML = `
      <span class="save-item-head">
        <strong>${escapeHtml(campaign.campaign_name || campaign.slot)}</strong>
        <small>${escapeHtml(campaign.slot)}</small>
      </span>
      <small>${escapeHtml(campaign.world_name || 'Unknown world')} · Turn ${campaign.turn_count} · ${displayModeLabel(campaign.display_mode || 'story')}</small>
    `;
    if (campaign.loadable === false) {
      btn.classList.add('warning');
      btn.title = 'This save file exists but could not be parsed.';
    }
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
  renderSelectedCampaignSummary();
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
    console.log(`[path-config] draft_updated field=${inputElement.id}`);
    setStatus(`Selected folder: ${result.path}`);
  } catch (error) {
    setStatus(error.message, true);
  }
}

async function pickFile(title, inputElement, filters = ['.json']) {
  try {
    const result = await api('/api/setup/pick-file', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title, initial_path: inputElement.value.trim(), filters }),
    });
    if (!result.ok) {
      setStatus(result.message || 'File selection failed.', true);
      return;
    }
    inputElement.value = result.path || '';
    console.log(`[path-config] draft_updated field=${inputElement.id}`);
    setStatus(`Selected file: ${result.path}`);
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
    if (campaignSettingsDirty && !campaignSettingsApplying) {
      await applySettings();
    }
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
      setSceneImage(
        result.scene_visual.image_url,
        result.scene_visual.caption || 'Latest generated image loaded in Scene Visual.',
        result.scene_visual.turn || null,
      );
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
    const sceneVisualMode = normalizeSceneVisualMode(document.getElementById('form-scene-visual-mode')?.value || 'after_narration');
    const playStyle = {
      allow_freeform_powers: !!document.getElementById('form-allow-freeform-powers')?.checked,
      auto_update_character_sheet_from_actions: !!document.getElementById('form-auto-update-sheet-from-actions')?.checked,
      strict_sheet_enforcement: !!document.getElementById('form-strict-sheet-enforcement')?.checked,
      auto_sync_player_declared_identity: !!document.getElementById('form-auto-sync-player-identity')?.checked,
      auto_generate_npc_personalities: !!document.getElementById('form-auto-generate-npc-personalities')?.checked,
      auto_evolve_npc_personalities: !!document.getElementById('form-auto-evolve-npc-personalities')?.checked,
      reactive_world_persistence: !!document.getElementById('form-reactive-world-persistence')?.checked,
      narration_format_mode: normalizeNarrationFormatMode(document.getElementById('form-narration-format-mode')?.value || 'book'),
      scene_visual_mode: sceneVisualMode,
    };
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
      display_mode: 'story',
      suggested_moves_enabled: !!document.getElementById('form-suggested-moves-enabled')?.checked,
      play_style: playStyle,
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

function visualPipelineDraftFromUi() {
  return {
    comfyui_path: comfyuiPathInput?.value.trim() || '',
    comfyui_workflow_path: comfyuiWorkflowPathInput?.value.trim() || '',
    comfyui_output_dir: comfyuiOutputDirInput?.value.trim() || '',
    checkpoint_folder: checkpointFolderInput?.value.trim() || '',
  };
}

async function applyVisualPipelineSettings() {
  console.log('[path-config] apply_requested');
  const button = document.getElementById('apply-visual-pipeline-settings');
  if (button) button.disabled = true;
  try {
    const payload = visualPipelineDraftFromUi();
    const response = await api('/api/settings/visual-pipeline', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    renderPathConfigStatus(response.path_config);
    if (!response.ok) {
      const reason = response.error_field || 'unknown';
      console.log(`[path-config] apply_failed field=${reason} reason=validation_failed`);
      setStatus(response.message || 'Visual pipeline settings are invalid.', true);
      return;
    }
    appliedVisualPipelinePaths = { ...payload };
    console.log('[path-config] apply_succeeded');
    setStatus(response.message || 'Visual pipeline settings applied.');
    await Promise.all([refreshDependencyReadiness(), refreshComfyuiModelList()]);
  } catch (error) {
    console.log('[path-config] apply_failed field=unknown reason=request_failed');
    setStatus(error.message, true);
  } finally {
    if (button) button.disabled = false;
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
    const playStyle = playStyleSnapshotFromUi();
    const campaignAutoVisualTiming = ['before_narration', 'after_narration'].includes(playStyle.scene_visual_mode)
      ? playStyle.scene_visual_mode
      : 'off';
    const settings = await api('/api/settings/global', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model: { provider: modelProvider, model_name: modelName, ollama_path: ollamaPathInput?.value.trim() || '' },
        image: {
          provider: imageProvider,
          comfyui_path: appliedVisualPipelinePaths.comfyui_path || '',
          comfyui_workflow_path: appliedVisualPipelinePaths.comfyui_workflow_path || '',
          comfyui_output_dir: appliedVisualPipelinePaths.comfyui_output_dir || '',
          manual_image_generation_enabled: manualImageEnabled,
          campaign_auto_visual_timing: campaignAutoVisualTiming,
          checkpoint_source: checkpointSourceInput?.value || 'local',
          checkpoint_folder: appliedVisualPipelinePaths.checkpoint_folder || '',
          preferred_checkpoint: preferredCheckpointInput?.value.trim() || 'DreamShaper',
          preferred_launcher: preferredLauncherInput?.value || 'auto',
        },
      }),
    });
    const campaignSettings = await api('/api/settings/campaign', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        image_generation_enabled: campaignImageEnabled,
        suggested_moves_enabled: suggestedMovesEnabled,
        player_suggested_moves_override: suggestedMovesEnabled,
        play_style: playStyle,
      }),
    });
    await refreshDependencyReadiness();
    await refreshSupportedModels(false);
    await refreshComfyuiModelList();
    syncVisualModeUi({ manualEnabled: manualImageEnabled });
    ingestPersistedCampaignSettings(
      {
        image_generation_enabled: !!campaignSettings.settings?.image_generation_enabled,
        suggested_moves_enabled: !!campaignSettings.settings?.effective_suggested_moves_enabled,
        play_style: campaignSettings.settings?.play_style || playStyle,
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
    renderPathConfigStatus(settings.settings?.path_config);
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

function renderPathConfigStatus(config) {
  if (!pathConfigStatus) return;
  const imageConfig = config?.image || {};
  const comfy = imageConfig.comfyui_root || {};
  const workflow = imageConfig.workflow_path || {};
  const output = imageConfig.output_dir || {};
  const checkpoint = imageConfig.checkpoint_dir || {};
  const pipelineReady = !!imageConfig.pipeline_ready;
  const lineFor = (field, item, { optional = false } = {}) => {
    let status = 'Missing';
    if (item?.valid) status = 'Valid';
    else if (optional && !item?.configured) status = 'Optional, not set';
    else if (!item?.configured) status = 'Missing';
    return `${field}: ${status}${item?.message ? ` (${item.message})` : ''}`;
  };
  const updateFieldValidation = (el, item, { optional = false } = {}) => {
    if (!el) return;
    el.classList.remove('valid', 'invalid', 'optional');
    if (item?.valid) el.classList.add('valid');
    else if (optional && !item?.configured) el.classList.add('optional');
    else el.classList.add('invalid');
    el.textContent = lineFor(el.dataset.fieldLabel || '', item, { optional });
  };
  if (comfyuiPathValidation) comfyuiPathValidation.dataset.fieldLabel = 'ComfyUI folder';
  if (workflowPathValidation) workflowPathValidation.dataset.fieldLabel = 'Workflow JSON';
  if (outputPathValidation) outputPathValidation.dataset.fieldLabel = 'Output folder';
  if (checkpointPathValidation) checkpointPathValidation.dataset.fieldLabel = 'Checkpoint folder';
  updateFieldValidation(comfyuiPathValidation, comfy);
  updateFieldValidation(workflowPathValidation, workflow);
  updateFieldValidation(outputPathValidation, output, { optional: true });
  updateFieldValidation(checkpointPathValidation, checkpoint);
  const entries = [
    `ComfyUI folder: ${comfy.valid ? 'valid' : (comfy.configured ? 'invalid' : 'not configured')}`,
    `Workflow file: ${workflow.valid ? 'valid' : (workflow.configured ? 'invalid' : 'not configured')}`,
    `Checkpoint folder: ${checkpoint.valid ? 'valid' : (checkpoint.configured ? 'invalid' : 'not configured')}`,
    `Output folder: ${output.valid ? 'valid' : (output.configured ? 'invalid' : 'optional')}`,
    `Image pipeline: ${pipelineReady ? 'ready' : 'not ready'}`,
  ];
  const details = [comfy.message, workflow.message, checkpoint.message, output.message].filter(Boolean).join(' | ');
  pathConfigStatus.textContent = `${entries.join(' • ')}${details ? ` — ${details}` : ''}`;
}

async function loadSettings() {
  const data = await api('/api/settings/global');
  document.getElementById('model-provider').value = data.settings.model.provider;
  document.getElementById('model-name').value = data.settings.model.model_name;
  document.getElementById('image-provider').value = data.settings.image.provider;
  if (manualImageEnabledInput) manualImageEnabledInput.checked = !!data.settings.image.manual_image_generation_enabled;
  if (ollamaPathInput) ollamaPathInput.value = data.settings.model.ollama_path || '';
  if (comfyuiPathInput) comfyuiPathInput.value = data.settings.image.comfyui_path || '';
  if (comfyuiWorkflowPathInput) comfyuiWorkflowPathInput.value = data.settings.image.comfyui_workflow_path || '';
  if (comfyuiOutputDirInput) comfyuiOutputDirInput.value = data.settings.image.comfyui_output_dir || '';
  if (checkpointFolderInput) checkpointFolderInput.value = data.settings.image.checkpoint_folder || '';
  appliedVisualPipelinePaths = {
    comfyui_path: data.settings.image.comfyui_path || '',
    comfyui_workflow_path: data.settings.image.comfyui_workflow_path || '',
    comfyui_output_dir: data.settings.image.comfyui_output_dir || '',
    checkpoint_folder: data.settings.image.checkpoint_folder || '',
  };
  if (checkpointSourceInput) checkpointSourceInput.value = data.settings.image.checkpoint_source || 'local';
  if (preferredCheckpointInput) preferredCheckpointInput.value = data.settings.image.preferred_checkpoint || 'DreamShaper';
  if (preferredLauncherInput) preferredLauncherInput.value = data.settings.image.preferred_launcher || 'auto';
  ingestPersistedCampaignSettings(
    {
      image_generation_enabled: campaignSettingsPersisted?.image_generation_enabled ?? document.getElementById('image-enabled').checked,
      suggested_moves_enabled: campaignSettingsPersisted?.suggested_moves_enabled ?? !!suggestedMovesToggleInput?.checked,
      play_style: campaignSettingsPersisted?.play_style || playStyleSnapshotFromUi(),
    },
    loadedSlot,
  );
  syncVisualModeUi({ manualEnabled: !!(manualImageEnabledInput?.checked) });
  const modelStatus = data.settings.model_status;
  if (modelStatus && modelStatus.provider === 'ollama' && !modelStatus.ready) {
    setStatus(modelStatus.user_message || 'Ollama provider is unavailable.', true);
  }
  renderDependencyReadiness(data.settings?.dependency_readiness || { items: [], setup_guidance: [] });
  renderPathConfigStatus(data.settings?.path_config);
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
document.getElementById('open-campaign-browser').onclick = openCampaignBrowser;
document.getElementById('new-campaign').onclick = openNewCampaignModal;
document.getElementById('close-campaign-browser').onclick = closeCampaignBrowser;
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
document.getElementById('pick-comfyui-workflow-file').onclick = () => pickFile('Select ComfyUI workflow JSON', comfyuiWorkflowPathInput, ['.json']);
document.getElementById('pick-comfyui-output-folder').onclick = () => pickFolder('Select ComfyUI output folder', comfyuiOutputDirInput);
document.getElementById('pick-checkpoint-folder').onclick = () => pickFolder('Select checkpoint folder', checkpointFolderInput);
document.getElementById('connect-ollama-folder').onclick = connectOllamaFolder;
document.getElementById('apply-visual-pipeline-settings').onclick = applyVisualPipelineSettings;
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
document.getElementById('test-image-pipeline-from-setup').onclick = () => runReadinessAction('test_image_pipeline', {});
document.getElementById('recheck-readiness').onclick = async () => {
  try {
    await runReadinessAction('recheck', {});
  } catch (error) {
    setStatus(error.message, true);
  }
};
if (manualImageEnabledInput) {
  manualImageEnabledInput.onchange = () => syncVisualModeUi({ manualEnabled: !!manualImageEnabledInput.checked });
}
[
  { field: 'comfyui_path', element: comfyuiPathInput },
  { field: 'workflow_path', element: comfyuiWorkflowPathInput },
  { field: 'output_dir', element: comfyuiOutputDirInput },
  { field: 'checkpoint_folder', element: checkpointFolderInput },
].forEach(({ field, element }) => {
  if (!element) return;
  element.addEventListener('input', () => console.log(`[path-config] draft_updated field=${field}`));
});
if (suggestedMovesToggleInput) {
  suggestedMovesToggleInput.onchange = () => {
    updateCampaignDirtyState();
    queueAutoApplyCampaignSettings();
  };
}
[
  allowFreeformPowersInput,
  autoUpdateSheetFromActionsInput,
  strictSheetEnforcementInput,
  autoSyncPlayerIdentityInput,
  autoGenerateNpcPersonalitiesInput,
  autoEvolveNpcPersonalitiesInput,
  reactiveWorldPersistenceInput,
  narrationFormatModeInput,
].forEach((input) => {
  if (!input) return;
  input.onchange = () => {
    updateCampaignDirtyState();
    queueAutoApplyCampaignSettings();
  };
});
if (sceneVisualModeInput) {
  sceneVisualModeInput.onchange = () => {
    syncVisualModeUi({ manualEnabled: !!(manualImageEnabledInput?.checked) });
    updateCampaignDirtyState();
    queueAutoApplyCampaignSettings();
  };
}
const campaignImageEnabledInput = document.getElementById('image-enabled');
if (campaignImageEnabledInput) {
  campaignImageEnabledInput.onchange = () => {
    updateCampaignDirtyState();
    queueAutoApplyCampaignSettings();
  };
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
  runtimeCharacterSheetCreateModal?.classList.add('hidden');
  resetRuntimeSheetCreateForm();
  runtimeCharacterSheetsModal?.classList.remove('hidden');
};
document.getElementById('open-runtime-inventory').onclick = async () => {
  console.log('[inventory] runtime_button_rendered=true');
  await refreshInventory();
  runtimeInventoryModal?.classList.remove('hidden');
};
document.getElementById('close-runtime-inventory').onclick = () => {
  runtimeInventoryModal?.classList.add('hidden');
};
document.getElementById('open-runtime-spellbook').onclick = async () => {
  console.log('[spellbook] runtime_button_rendered=true');
  await refreshSpellbook();
  runtimeSpellbookModal?.classList.remove('hidden');
};
document.getElementById('close-runtime-spellbook').onclick = () => {
  runtimeSpellbookModal?.classList.add('hidden');
};
campaignBrowserModal?.addEventListener('click', (event) => {
  if (event.target === campaignBrowserModal) {
    closeCampaignBrowser();
  }
});
document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape' && campaignBrowserModal && !campaignBrowserModal.classList.contains('hidden')) {
    closeCampaignBrowser();
  }
});
document.getElementById('open-narrator-rules').onclick = async () => {
  console.log('[narrator-rules] runtime_button_rendered=true');
  await refreshNarratorRules();
  narratorRulesModal?.classList.remove('hidden');
  console.log(`[narrator-rules] modal_opened campaign=${loadedSlot || 'unknown'}`);
};
document.getElementById('open-world-building').onclick = async () => {
  await refreshWorldBuilding();
  worldBuildingModal?.classList.remove('hidden');
};
if (recalibrateWorldBuildingButton) {
  recalibrateWorldBuildingButton.onclick = async () => {
    await recalibrateWorldBuilding();
  };
}
document.getElementById('close-narrator-rules').onclick = () => {
  narratorRulesModal?.classList.add('hidden');
};
document.getElementById('close-world-building').onclick = () => {
  worldBuildingModal?.classList.add('hidden');
};
document.getElementById('narrator-rule-clear').onclick = () => {
  document.getElementById('narrator-rule-edit-id').value = '';
  document.getElementById('narrator-rule-input').value = '';
};
document.getElementById('narrator-rule-save').onclick = async () => {
  const text = document.getElementById('narrator-rule-input').value.trim();
  if (!text) {
    setStatus('Narrator rule cannot be empty.', true);
    return;
  }
  const result = await api('/api/campaign/narrator-rules', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      action: 'upsert',
      id: document.getElementById('narrator-rule-edit-id').value.trim(),
      text,
    }),
  });
  customNarratorRules = Array.isArray(result.rules) ? result.rules : [];
  renderNarratorRules();
  document.getElementById('narrator-rule-edit-id').value = '';
  document.getElementById('narrator-rule-input').value = '';
  console.log(`[narrator-rules] rule_added campaign=${loadedSlot || 'unknown'} count=${customNarratorRules.length}`);
};
document.getElementById('narrator-rules-save-campaign').onclick = async () => {
  await api('/api/campaign/save', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ slot: loadedSlot || selectedSlot || 'autosave' }),
  });
  await refreshSaves();
  setStatus('Narrator rules saved to campaign.');
};
document.getElementById('close-runtime-character-sheets').onclick = () => {
  runtimeCharacterSheetsModal?.classList.add('hidden');
  runtimeCharacterSheetCreateModal?.classList.add('hidden');
};
runtimeCharacterSheetCreateToggle?.addEventListener('click', () => {
  runtimeCharacterSheetCreateModal?.classList.remove('hidden');
  console.log('[character-sheets] create_modal_opened=true');
  runtimeSheetCreateName?.focus();
});
runtimeSheetCreateRole?.addEventListener('change', () => {
  const isCustom = runtimeSheetCreateRole.value === 'custom';
  runtimeSheetCreateCustomRoleWrap?.classList.toggle('hidden', !isCustom);
  if (isCustom) runtimeSheetCreateCustomRole?.focus();
});
runtimeCharacterSheetCreateCancel?.addEventListener('click', () => {
  runtimeCharacterSheetCreateModal?.classList.add('hidden');
  console.log('[character-sheets] create_modal_closed=true');
  resetRuntimeSheetCreateForm();
});
closeRuntimeCharacterSheetCreate?.addEventListener('click', () => {
  runtimeCharacterSheetCreateModal?.classList.add('hidden');
  console.log('[character-sheets] create_modal_closed=true');
  resetRuntimeSheetCreateForm();
});
runtimeCharacterSheetCreateSave?.addEventListener('click', async () => {
  await createRuntimeCharacterSheet();
});
runtimeSheetAddGuaranteedAbility?.addEventListener('click', () => {
  addGuaranteedAbilityEditorRow({}, { containerId: 'runtime-sheet-guaranteed-abilities', fieldPrefix: 'rga' });
});
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
document.getElementById('sheet-add-guaranteed-ability').onclick = () => addGuaranteedAbilityEditorRow();
document.getElementById('spellbook-entry-clear').onclick = () => {
  document.getElementById('spellbook-entry-id').value = '';
  document.getElementById('spellbook-entry-name').value = '';
  document.getElementById('spellbook-entry-type').value = 'spell';
  document.getElementById('spellbook-entry-description').value = '';
  document.getElementById('spellbook-entry-cost').value = '';
  document.getElementById('spellbook-entry-cooldown').value = '';
  document.getElementById('spellbook-entry-tags').value = '';
  document.getElementById('spellbook-entry-notes').value = '';
};
document.getElementById('spellbook-entry-save').onclick = async () => {
  await api('/api/campaign/spellbook', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      action: 'upsert',
      id: document.getElementById('spellbook-entry-id').value.trim(),
      name: document.getElementById('spellbook-entry-name').value.trim(),
      type: document.getElementById('spellbook-entry-type').value,
      description: document.getElementById('spellbook-entry-description').value.trim(),
      cost_or_resource: document.getElementById('spellbook-entry-cost').value.trim(),
      cooldown: document.getElementById('spellbook-entry-cooldown').value.trim(),
      tags: parseCsv(document.getElementById('spellbook-entry-tags').value),
      notes: document.getElementById('spellbook-entry-notes').value.trim(),
    }),
  });
  await refreshSpellbook();
};

Promise.all([refreshMessages(), refreshState(), refreshSaves(), loadSettings(), refreshDependencyReadiness(), refreshSceneVisual()]).catch((error) => setStatus(error.message, true));

console.log('[character-sheets] runtime_button_rendered=true');
console.log('[inventory] runtime_button_rendered=true');
console.log('[spellbook] runtime_button_rendered=true');
console.log('[ui] left_panel_resized=true');
console.log('[ui] header_simplified=true');
console.log('[ui] turn_visuals_removed=true');
console.log('[ui] duplicate_scene_visual_text_removed=true');
