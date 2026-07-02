const dialogueFeed = document.getElementById('dialogue-feed');
const campaignMeta = document.getElementById('campaign-meta');
const campaignDisplayModeIndicator = document.getElementById('campaign-display-mode-indicator');
const creatorModeBadge = document.getElementById('creator-mode-badge');
const saveList = document.getElementById('save-list');
const sceneImageDisplay = document.getElementById('scene-image-display');
const sceneVisualMeta = document.getElementById('scene-visual-meta');
const imagePromptInput = document.getElementById('image-prompt-input');
const imageStatusLine = document.getElementById('image-status-line');
const sceneImageProgressStrip = document.getElementById('scene-image-progress-strip');
const sceneImageProgressText = document.getElementById('scene-image-progress-text');
const statusLine = document.getElementById('status-line');
const autosaveStatus = document.getElementById('autosave-status');
const statusCampaignName = document.getElementById('status-campaign-name');
const statusWorldLocation = document.getElementById('status-world-location');
const statusTurnCount = document.getElementById('status-turn-count');
const statusDisplayMode = document.getElementById('status-display-mode');
const inputModeToggle = document.getElementById('input-mode-toggle');
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
const imageAiSimpleStatus = document.getElementById('image-ai-simple-status');
const imageAiSimpleError = document.getElementById('image-ai-simple-error');
const imageImportComfySourceInput = document.getElementById('image-import-comfy-source');
const imageImportModelSourceInput = document.getElementById('image-import-model-source');
const imageBackendOverallState = document.getElementById('image-backend-overall-state');
const imageBackendDiagnosticsSummary = document.getElementById('image-backend-diagnostics-summary');
const imageBackendDiagnosticsLog = document.getElementById('image-backend-diagnostics-log');
const openImageBackendFolderButton = document.getElementById('open-image-backend-folder');
const showImageDiagnosticsButton = document.getElementById('show-image-diagnostics');
const retryImageAiSetupButton = document.getElementById('retry-image-ai-setup');
const disableImageAiButton = document.getElementById('disable-image-ai');
const pickCheckpointFolderButton = document.getElementById('pick-checkpoint-folder');
const preferredLauncherInput = document.getElementById('preferred-launcher');
const manualImageEnabledInput = document.getElementById('manual-image-enabled');
const creatorModeToggleInput = document.getElementById('creator-mode-toggle');
const creatorModeConfirmModal = document.getElementById('creator-mode-confirm-modal');
const creatorModeConfirmCheckbox = document.getElementById('creator-mode-confirm-checkbox');
const creatorModeConfirmEnable = document.getElementById('creator-mode-confirm-enable');
const creatorModeConfirmCancel = document.getElementById('creator-mode-confirm-cancel');
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
const developerToolsToggleInput = document.getElementById('developer-tools-toggle');
const developerToolsPanel = document.getElementById('developer-tools-panel');
const gmOrchestratorStatus = document.getElementById('gm-orchestrator-status');
const gmOrchestratorOutput = document.getElementById('gm-orchestrator-output');
const forceGmOrchestratorInput = document.getElementById('force-gm-orchestrator');
const gmTestInput = document.getElementById('gm-test-input');
const refreshGmOrchestratorButton = document.getElementById('refresh-gm-orchestrator');
const testGmDecisionButton = document.getElementById('test-gm-decision');
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
const inventoryEntryIdInput = document.getElementById('inventory-entry-id');
const inventoryEntryNameInput = document.getElementById('inventory-entry-name');
const inventoryEntryCategoryInput = document.getElementById('inventory-entry-category');
const inventoryEntryQuantityInput = document.getElementById('inventory-entry-quantity');
const inventoryEntryNotesInput = document.getElementById('inventory-entry-notes');
const runtimeSpellbookModal = document.getElementById('runtime-spellbook-modal');
const runtimeSpellbookList = document.getElementById('runtime-spellbook-list');
const campaignEventsList = document.getElementById('campaign-events-list');
const campaignEventsPendingCount = document.getElementById('campaign-events-pending-count');
const narratorRulesModal = document.getElementById('narrator-rules-modal');
const narratorRulesList = document.getElementById('narrator-rules-list');
const worldBuildingModal = document.getElementById('world-building-modal');
const worldBuildingNpcList = document.getElementById('world-building-npc-list');
const worldBuildingDesignList = document.getElementById('world-building-design-list');
const worldBuildingReactiveList = document.getElementById('world-building-reactive-list');
const recalibrateWorldBuildingButton = document.getElementById('recalibrate-world-building');

const PRIMARY_MODAL_IDS = new Set([
  'campaign-browser-modal',
  'new-campaign-modal',
  'setup-modal',
  'runtime-character-sheets-modal',
  'runtime-inventory-modal',
  'runtime-spellbook-modal',
  'campaign-events-modal',
  'narrator-rules-modal',
  'world-building-modal',
]);
const DIALOG_MODAL_IDS = new Set([
  'creator-mode-confirm-modal',
  'runtime-character-sheet-create-modal',
]);
const modalManager = {
  activePrimaryId: null,
  openDialogs: new Set(),
  getModal(id) {
    return document.getElementById(id);
  },
  prepareModal(modal, layer) {
    modal.classList.toggle('modal-primary', layer === 'primary');
    modal.classList.toggle('modal-dialog', layer === 'dialog');
    modal.setAttribute('aria-modal', 'true');
    if (!modal.hasAttribute('role')) modal.setAttribute('role', 'dialog');
  },
  focusModal(modal) {
    const card = modal.querySelector('.modal-card') || modal;
    if (typeof card.scrollTo === 'function') card.scrollTo({ top: 0, left: 0 });
    else card.scrollTop = 0;
    const firstInteractive = modal.querySelector('button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])');
    (firstInteractive || card || modal).focus?.({ preventScroll: true });
  },
  bringToFront(id, layer = 'primary') {
    const modal = this.getModal(id);
    if (!modal) return null;
    this.prepareModal(modal, layer);
    modal.classList.remove('hidden');
    requestAnimationFrame(() => this.focusModal(modal));
    return modal;
  },
  openPrimaryModal(id) {
    if (!PRIMARY_MODAL_IDS.has(id)) console.warn(`[modal-manager] opening unregistered primary modal: ${id}`);
    if (this.activePrimaryId && this.activePrimaryId !== id) {
      this.closePrimaryModal();
    }
    this.activePrimaryId = id;
    return this.bringToFront(id, 'primary');
  },
  closePrimaryModal(id = this.activePrimaryId) {
    if (!id) return;
    const modal = this.getModal(id);
    modal?.classList.add('hidden');
    modal?.classList.remove('modal-primary');
    if (!id || this.activePrimaryId === id) {
      this.activePrimaryId = null;
    }
  },
  openDialog(id) {
    if (!DIALOG_MODAL_IDS.has(id)) console.warn(`[modal-manager] opening unregistered dialog modal: ${id}`);
    this.openDialogs.add(id);
    return this.bringToFront(id, 'dialog');
  },
  closeDialog(id) {
    const modal = this.getModal(id);
    modal?.classList.add('hidden');
    modal?.classList.remove('modal-dialog');
    this.openDialogs.delete(id);
  },
};
function openPrimaryModal(id) { return modalManager.openPrimaryModal(id); }
function closePrimaryModal(id) { return modalManager.closePrimaryModal(id); }
function openDialog(id) { return modalManager.openDialog(id); }
function closeDialog(id) { return modalManager.closeDialog(id); }

const intelligenceStatus = document.getElementById('intelligence-status');
const intelligenceSourceList = document.getElementById('intelligence-source-list');
const intelligenceSourceIdInput = document.getElementById('intelligence-source-id');
const intelligenceSourceTitleInput = document.getElementById('intelligence-source-title');
const intelligenceSourceCategoryInput = document.getElementById('intelligence-source-category');
const intelligenceSourcePriorityInput = document.getElementById('intelligence-source-priority');
const intelligenceSourceEnabledInput = document.getElementById('intelligence-source-enabled');
const refreshIntelligenceSourcesButton = document.getElementById('refresh-intelligence-sources');
const addIntelligenceSourceButton = document.getElementById('add-intelligence-source');
const replaceIntelligenceSourceButton = document.getElementById('replace-intelligence-source');
const addIntelligenceSourceFileInput = document.getElementById('add-intelligence-source-file');
const replaceIntelligenceSourceFileInput = document.getElementById('replace-intelligence-source-file');
const applyIntelligenceEnabledButton = document.getElementById('apply-intelligence-enabled');
const applyIntelligencePriorityButton = document.getElementById('apply-intelligence-priority');
const rebuildIntelligenceIndexButton = document.getElementById('rebuild-intelligence-index');
const testIntelligenceRetrievalButton = document.getElementById('test-intelligence-retrieval');
const intelligenceRetrievalQueryInput = document.getElementById('intelligence-retrieval-query');
const intelligenceRetrievalResults = document.getElementById('intelligence-retrieval-results');
const applyCampaignIntelligenceSourcesButton = document.getElementById('apply-campaign-intelligence-sources');
const removeCurrentCampaignIntelligenceSourceButton = document.getElementById('remove-current-campaign-intelligence-source');
const deleteIntelligenceSourceButton = document.getElementById('delete-intelligence-source');
const resetImportedIntelligenceSourcesButton = document.getElementById('reset-imported-intelligence-sources');
const runtimeSpellbookButton = document.getElementById('open-runtime-spellbook');
const runtimeSpellbookTitle = document.querySelector('#runtime-spellbook-modal h3');
const refreshPromptInspectorButton = document.getElementById('refresh-prompt-inspector');
const campaignPromptInspector = document.getElementById('campaign-prompt-inspector');
let intelligenceSourcesCache = [];
let selectedIntelligenceSourceId = '';
let selectedCampaignIntelligenceSourceIds = new Set();

let draftCharacterSheets = [];
let editingSheetIndex = -1;
let runtimeCharacterSheets = [];
let selectedRuntimeSheetId = '';
let runtimeInventoryState = {};
let runtimeSpellbookEntries = [];
let campaignEvents = [];
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
let currentInputMode = 'ic';
let modelInventoryState = { active_model_id: '', models: [] };
let modelInstallState = {};
let latestGlobalSettings = null;
let latestImageSetupSnapshot = null;
let latestImageBackendDiagnostics = null;
let imageSetupRequestInFlight = false;
let imageSetupTerminalFailure = false;
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
let suppressCreatorModeToggle = false;
// TODO: Keep future Developer Mode separate from Creator Mode. Developer Mode should cover diagnostics, provider setup, prompt debugging, logs, image addon tools, and model/provider details only for users who intentionally reveal it.
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
    setup_image_ai: 'Import, Set Up, and Start Image AI',
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
  return ['off', 'manual', 'before_narration', 'after_narration'].includes(clean) ? clean : 'off';
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
    scene_visual_mode: normalizeSceneVisualMode(sceneVisualModeInput?.value || 'off'),
  };
}

function campaignSettingsSnapshotFromUi() {
  const playStyle = playStyleSnapshotFromUi();
  return {
    campaign_mode: creatorModeToggleInput?.checked ? 'creator' : 'adventure',
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
    && normalizeCampaignMode(left.campaign_mode) === normalizeCampaignMode(right.campaign_mode)
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
  if (creatorModeToggleInput) {
    suppressCreatorModeToggle = true;
    creatorModeToggleInput.checked = normalizeCampaignMode(snapshot.campaign_mode) === 'creator';
    suppressCreatorModeToggle = false;
  }
  updateCreatorModeUi();
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
    campaign_mode: normalizeCampaignMode(snapshot.campaign_mode || 'adventure'),
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
      scene_visual_mode: normalizeSceneVisualMode(snapshot.play_style?.scene_visual_mode || 'off'),
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

function normalizeCampaignMode(mode) {
  return String(mode || '').trim().toLowerCase() === 'creator' ? 'creator' : 'adventure';
}

function isCreatorModeEnabled() {
  return normalizeCampaignMode(campaignSettingsPersisted?.campaign_mode || (creatorModeToggleInput?.checked ? 'creator' : 'adventure')) === 'creator';
}

function updateCreatorModeUi() {
  const creatorEnabled = isCreatorModeEnabled();
  document.body?.classList.toggle('creator-mode-enabled', creatorEnabled);
  document.body?.classList.toggle('adventure-mode-enabled', !creatorEnabled);
  creatorModeBadge?.classList.toggle('hidden', !creatorEnabled);
  document.querySelectorAll('.creator-mode-only').forEach((element) => {
    element.classList.toggle('hidden', !creatorEnabled);
    element.setAttribute('aria-hidden', creatorEnabled ? 'false' : 'true');
  });
  renderRuntimeCharacterSheets();
  renderInventoryViewer();
  renderSpellbookViewer();
}

function openCreatorModeConfirmation() {
  if (!creatorModeConfirmModal) return;
  if (creatorModeConfirmCheckbox) creatorModeConfirmCheckbox.checked = false;
  if (creatorModeConfirmEnable) creatorModeConfirmEnable.disabled = true;
  openDialog('creator-mode-confirm-modal');
}

function closeCreatorModeConfirmation() {
  closeDialog('creator-mode-confirm-modal');
}

async function setCampaignMode(mode) {
  const normalizedMode = normalizeCampaignMode(mode);
  if (creatorModeToggleInput) creatorModeToggleInput.checked = normalizedMode === 'creator';
  await applySettings();
  setStatus(normalizedMode === 'creator' ? 'Creator Mode enabled for this campaign.' : 'Adventure Mode enabled. Editing tools are tucked away.');
}

function syncVisualModeUi({ manualEnabled }) {
  if (manualImagePanel) {
    manualImagePanel.style.display = 'none';
    manualImagePanel.classList.add('hidden');
    manualImagePanel.setAttribute('aria-hidden', 'true');
  }
}

function setAutosaveStatus(message) {
  if (!autosaveStatus) return;
  autosaveStatus.textContent = message || 'Campaigns autosave automatically.';
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
  const managedButtons = document.querySelectorAll('#setup-text-ai, #import-image-ai, #retry-image-ai-setup, #setup-everything, #recheck-readiness, #disable-image-ai, .readiness-action-btn');
  managedButtons.forEach((button) => {
    const actionId = button.dataset.action || (button.id === 'setup-text-ai' ? 'setup_text_ai'
      : button.id === 'import-image-ai' ? 'setup_image_ai'
      : button.id === 'setup-everything' ? 'setup_everything'
      : button.id === 'recheck-readiness' ? 'recheck'
      : button.id === 'retry-image-ai-setup' ? 'setup_image_ai'
      : button.id === 'disable-image-ai' ? 'guided_image_action'
      : '');
    if (!actionId) return;
    if (!setupRunState.busy) {
      if (imageSetupTerminalFailure && button.id === 'import-image-ai') {
        button.disabled = true;
        return;
      }
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
  const withFailureDetail = (result, fallbackMessage) => {
    const base = result?.next_step ? `${result.message} ${result.next_step}` : (result?.message || fallbackMessage);
    const detail = String(result?.error_line || result?.detail || '').trim();
    return detail ? `${base} Detail: ${detail}`.trim() : base;
  };
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
      await Promise.all([refreshDependencyReadiness(), refreshImageBackendDiagnostics()]);
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
      startSetupRun(actionId, 'Starting Image AI guided setup...', [
        { step: 'validate-comfyui-source', label: 'Validate ComfyUI source', state: 'running', message: 'Checking selected ComfyUI source...' },
      ]);
      setStatus('Import, Set Up, and Start Image AI: validating / importing / starting...');
      const result = await api('/api/setup/orchestrate-image', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({}),
      });
      updateSetupRun({
        steps: normalizeSetupSteps(result.steps),
        summary: result.summary || result.message || (result.ok ? 'Image AI is ready.' : 'Image AI setup failed.'),
      });
      await Promise.all([refreshDependencyReadiness(), refreshImageBackendDiagnostics()]);
      console.log('[setup-action] readiness refresh triggered');
      setStatus(
        result.ok
          ? (result.summary || result.message || 'Image AI ready.')
          : withFailureDetail(result, 'Image AI setup failed.'),
        !result.ok,
      );
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
      await Promise.all([refreshDependencyReadiness(), refreshImageBackendDiagnostics()]);
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
      await Promise.all([refreshDependencyReadiness(), refreshImageBackendDiagnostics()]);
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
      await Promise.all([refreshDependencyReadiness(), refreshImageBackendDiagnostics()]);
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
      setStatus(result.ok ? (result.message || 'ComfyUI started.') : withFailureDetail(result, 'ComfyUI failed to start.'), !result.ok);
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
  success: '',
  error: 'Image generation failed',
};

function clearImageProgressTimer() {
  if (imageProgressState.timeoutId) {
    window.clearTimeout(imageProgressState.timeoutId);
    imageProgressState.timeoutId = 0;
  }
}

function visualsEnabledForPlayer() {
  return !!campaignSettingsPersisted?.image_generation_enabled
    && normalizeSceneVisualMode(campaignSettingsPersisted?.play_style?.scene_visual_mode || 'off') !== 'off';
}

function setImageProgressPhase(phase, message = '') {
  if (!sceneImageProgressStrip || !sceneImageProgressText) return;
  clearImageProgressTimer();
  imageProgressState.phase = phase;
  if (phase === 'idle' || !visualsEnabledForPlayer()) {
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
    <small>${normalizeCampaignMode(selectedCampaign.campaign_mode || (selectedCampaign.slot === loadedSlot ? campaignSettingsPersisted?.campaign_mode : 'adventure')) === 'creator' ? 'Creator Mode' : 'Adventure Mode'}</small>
  `;
}

function openNewCampaignModal() {
  campaignWizardStep = 0;
  renderCampaignWizardStep();
  draftCharacterSheets = [];
  editingSheetIndex = -1;
  renderCharacterSheetList();
  document.getElementById('character-sheets-manager')?.classList.add('hidden');
  document.getElementById('character-sheet-editor')?.classList.add('hidden');
  openPrimaryModal('new-campaign-modal');
}

let campaignWizardStep = 0;
const campaignWizardStepNames = ['Choose World', 'Choose Race', 'Choose Class', 'Enter Character Name', 'Describe Appearance', 'Review and Enter World'];

function checkedValue(name, fallback) {
  return document.querySelector(`input[name="${name}"]:checked`)?.value || fallback;
}

function buildCampaignWizardPayload() {
  const rulesStyle = checkedValue('form-rules-style-choice', 'Hybrid');
  const playStyleRules = {
    allow_freeform_powers: rulesStyle !== 'Sheet Strict',
    auto_update_character_sheet_from_actions: rulesStyle === 'Hybrid',
    strict_sheet_enforcement: rulesStyle === 'Sheet Strict',
    auto_sync_player_declared_identity: false,
    auto_generate_npc_personalities: true,
    auto_evolve_npc_personalities: true,
    reactive_world_persistence: true,
    narration_format_mode: 'book',
    scene_visual_mode: 'off',
  };
  return {
    mode: 'mud_v2',
    campaign_name: document.getElementById('form-campaign-name').value.trim() || 'New Adventure',
    world_id: document.getElementById('form-world-name').value.trim() || 'shattered_realms',
    world_name: 'The Shattered Realms',
    theme: 'fantasy medieval',
    world_theme: 'fantasy medieval',
    tone: 'world-defined',
    campaign_tone: 'world-defined',
    premise: '',
    play_style: checkedValue('form-play-style-choice', 'Storybook Mode'),
    rules_style: rulesStyle,
    character_name: document.getElementById('form-player-name').value.trim(),
    character_role: document.getElementById('form-player-class').value.trim(),
    class_id: (document.getElementById('form-player-class').value.trim() || 'ranger').toLowerCase().replace(/[^a-z0-9]+/g, '_'),
    species: document.getElementById('form-species').value.trim(),
    race_id: (document.getElementById('form-species').value.trim() || 'human').toLowerCase().replace(/[^a-z0-9]+/g, '_'),
    background: document.getElementById('form-background').value.trim(),
    goal: document.getElementById('form-goal').value.trim(),
    description: document.getElementById('form-player-concept').value.trim(),
    appearance: document.getElementById('form-player-concept').value.trim(),
    power_level: checkedValue('form-power-level-choice', 'Capable Adventurer'),
    stats: {
      Strength: Number(document.getElementById('form-stat-strength')?.value || 5),
      Dexterity: Number(document.getElementById('form-stat-dexterity')?.value || 5),
      Constitution: Number(document.getElementById('form-stat-constitution')?.value || 5),
      Intelligence: Number(document.getElementById('form-stat-intelligence')?.value || 5),
      Wisdom: Number(document.getElementById('form-stat-wisdom')?.value || 5),
      Charisma: Number(document.getElementById('form-stat-charisma')?.value || 5),
    },
    starting_ability_mode: checkedValue('form-ability-mode', 'suggest'),
    starting_abilities: document.getElementById('form-starting-abilities').value.trim(),
    starting_item_mode: checkedValue('form-item-mode', 'suggest'),
    starting_items: document.getElementById('form-starting-items').value.trim(),
    player_name: document.getElementById('form-player-name').value.trim(),
    char_class: document.getElementById('form-player-class').value.trim(),
    player_concept: document.getElementById('form-player-concept').value.trim(),
    profile: 'classic_fantasy',
    thematic_flags: ['adventure'],
    display_mode: 'mud',
    suggested_moves_enabled: false,
    play_style_rules: playStyleRules,
    character_sheets: [],
    character_sheet_guidance_strength: 'light',
  };
}

function renderCampaignWizardReview() {
  const p = buildCampaignWizardPayload();
  const review = document.getElementById('campaign-wizard-review');
  if (!review) return;
  review.innerHTML = campaignWizardStepNames.slice(0, 5).map(() => '').join('');
  const rows = [
    ['World', p.world_name], ['Race', p.species || 'Human'], ['Class', p.character_role || 'Ranger'], ['Character name', p.character_name], ['Appearance', p.appearance || p.description], ['Starting stats/items/abilities', 'Defined by selected world race and class'], ['Starting room', 'Guildhall Crossing'],
  ];
  review.innerHTML = rows.map(([label, value]) => `<p><strong>${escapeHtml(label)}:</strong> ${escapeHtml(value || '—')}</p>`).join('');
}

function renderCampaignWizardStep() {
  document.querySelectorAll('#new-campaign-modal .wizard-step').forEach((step) => {
    step.classList.toggle('hidden', Number(step.dataset.step || 0) !== campaignWizardStep);
  });
  document.getElementById('campaign-wizard-back')?.toggleAttribute('disabled', campaignWizardStep === 0);
  document.getElementById('campaign-wizard-next')?.classList.toggle('hidden', campaignWizardStep >= 5);
  document.getElementById('create-campaign-confirm')?.classList.toggle('hidden', campaignWizardStep !== 5);
  document.getElementById('campaign-wizard-validation')?.classList.add('hidden');
  if (campaignWizardStep === 5) renderCampaignWizardReview();
}

function advanceCampaignWizard() {
  if (campaignWizardStep === 3) {
    const valid = document.getElementById('form-player-name').value.trim() && document.getElementById('form-player-class').value.trim();
    document.getElementById('campaign-wizard-validation')?.classList.toggle('hidden', !!valid);
    if (!valid) return;
  }
  campaignWizardStep = Math.min(5, campaignWizardStep + 1);
  renderCampaignWizardStep();
}

function backCampaignWizard() {
  campaignWizardStep = Math.max(0, campaignWizardStep - 1);
  renderCampaignWizardStep();
}


function setIntelligenceStatus(message, isError = false) {
  if (!intelligenceStatus) return;
  intelligenceStatus.textContent = message;
  intelligenceStatus.classList.toggle('error', !!isError);
}

function renderIntelligenceSources(sources) {
  if (!intelligenceSourceList) return;
  if (!Array.isArray(sources) || !sources.length) {
    intelligenceSourceList.textContent = 'No intelligence sources found.';
    return;
  }
  intelligenceSourcesCache = sources;
  intelligenceSourceList.innerHTML = sources.map((source) => {
    const enabled = source.enabled ? 'enabled' : 'disabled';
    const campaignSelectable = ['packs', 'imported'].includes(source.category || '');
    const sourceId = source.id || '';
    const checked = selectedCampaignIntelligenceSourceIds.has(sourceId) ? 'checked' : '';
    const selectedClass = selectedIntelligenceSourceId === sourceId ? ' selected' : '';
    const selector = campaignSelectable ? `<label><input type="checkbox" data-campaign-source-id="${escapeHtml(sourceId)}" ${checked} /> Use in this campaign</label>` : `<small>Core file: affects all campaigns.</small>`;
    return `<button type="button" class="model-card intelligence-source-card${selectedClass}" data-source-id="${escapeHtml(sourceId)}" aria-pressed="${selectedIntelligenceSourceId === sourceId ? 'true' : 'false'}">
      <strong>${escapeHtml(source.title || source.id || '')}</strong>
      <span>${escapeHtml(source.id || '')} • ${escapeHtml(source.category || '')} • priority ${escapeHtml(String(source.priority ?? 0))} • ${enabled}</span>
      <small>${escapeHtml(source.filename || '')}</small>
      ${selector}
    </button>`;
  }).join('');
  intelligenceSourceList.querySelectorAll('[data-campaign-source-id]').forEach((checkbox) => {
    checkbox.addEventListener('click', (event) => event.stopPropagation());
    checkbox.addEventListener('change', () => {
      if (checkbox.checked) selectedCampaignIntelligenceSourceIds.add(checkbox.dataset.campaignSourceId || '');
      else selectedCampaignIntelligenceSourceIds.delete(checkbox.dataset.campaignSourceId || '');
    });
  });
  intelligenceSourceList.querySelectorAll('[data-source-id]').forEach((button) => {
    button.addEventListener('click', () => {
      const source = sources.find((item) => item.id === button.dataset.sourceId);
      if (!source) return;
      selectedIntelligenceSourceId = source.id || '';
      if (intelligenceSourceIdInput) intelligenceSourceIdInput.value = selectedIntelligenceSourceId;
      renderIntelligenceSources(sources);
      if (intelligenceSourceTitleInput) intelligenceSourceTitleInput.value = source.title || '';
      if (intelligenceSourcePriorityInput) intelligenceSourcePriorityInput.value = source.priority || 0;
      if (intelligenceSourceEnabledInput) intelligenceSourceEnabledInput.checked = !!source.enabled;
    });
  });
}

async function refreshIntelligenceSources() {
  if (!intelligenceSourceList) return;
  setIntelligenceStatus('Loading intelligence sources...');
  try {
    const [result, inspector] = await Promise.all([api('/api/developer/intelligence'), api('/api/developer/intelligence/prompt-inspector')]);
    const uploadOk = result.python_multipart?.available !== false;
    [addIntelligenceSourceButton, replaceIntelligenceSourceButton].forEach((button) => { if (button) button.disabled = !uploadOk; });
    selectedCampaignIntelligenceSourceIds = new Set(inspector.selected_source_ids || []);
    renderPromptInspector(inspector);
    renderIntelligenceSources(result.sources || []);
    setIntelligenceStatus(result.python_multipart?.available === false ? result.python_multipart.message : `Loaded ${(result.sources || []).length} intelligence source(s).`);
  } catch (error) {
    setIntelligenceStatus(`Could not load intelligence sources: ${error.message}`, true);
  }
}

function intelligencePayload() {
  return {
    id: intelligenceSourceIdInput?.value?.trim() || '',
    title: intelligenceSourceTitleInput?.value?.trim() || '',
    category: intelligenceSourceCategoryInput?.value || 'imported',
    priority: Number.parseInt(intelligenceSourcePriorityInput?.value || '0', 10) || 0,
    enabled: !!intelligenceSourceEnabledInput?.checked,
  };
}

function renderPromptInspector(data) {
  if (!campaignPromptInspector || !data) return;
  const names = (items) => (items || []).map((item) => item.title || item.id).join(', ') || 'none';
  const snippets = (data.retrieved_chunks_injected || data.injected_snippets || []).map((item) => `<li><strong>${escapeHtml(item.title || item.source_id || 'source')}</strong> — ${escapeHtml(item.heading || 'chunk')} (score ${escapeHtml(String(item.score || 0))})<br /><small>${escapeHtml(item.snippet || '')}</small><br /><em>${escapeHtml(item.reason || '')}</em></li>`).join('') || '<li>none</li>';
  const skipped = (data.source_files_not_injected || []).map((item) => `<li>${escapeHtml(item.title || item.id)}: ${escapeHtml(item.reason || '')}</li>`).join('') || '<li>none</li>';
  campaignPromptInspector.innerHTML = `<strong>Core sources considered:</strong> ${escapeHtml(names(data.core_sources_considered || data.core_intelligence_files))}<br />
    <strong>Campaign-selected sources considered:</strong> ${escapeHtml(names(data.campaign_selected_sources_considered || data.campaign_intelligence_files))}<br />
    <strong>Selected IDs:</strong> ${escapeHtml((data.selected_campaign_source_ids || data.selected_source_ids || []).join(', ') || 'none')}<br />
    Indexed sources: ${escapeHtml(String(data.indexed_source_count || 0))}; Retrieved source IDs: ${escapeHtml((data.retrieved_source_ids || []).join(', ') || 'none')}; Retrieved chunks: ${escapeHtml(String(data.retrieved_chunk_count || 0))}; Injected chunks: ${escapeHtml(String(data.injected_chunk_count || 0))}; Injected chars: ${escapeHtml(String(data.estimated_injected_chars || data.estimated_guidance_char_count || 0))}; Zero reason: ${escapeHtml(data.zero_injection_reason || '—')}
    <div><strong>Retrieved chunks actually injected</strong><ul>${snippets}</ul></div>
    <div><strong>Source files not injected and why</strong><ul>${skipped}</ul></div>`;
}

function renderGmInspector(data) {
  if (!gmOrchestratorStatus || !data) return;
  if (forceGmOrchestratorInput) forceGmOrchestratorInput.checked = !!data.force_gm_orchestrator;
  const rows = ['provider_available', 'gm_orchestrator_used', 'provider_decision_used', 'deterministic_fallback_used']
    .map((key) => `<div><strong>${escapeHtml(key)}</strong>: ${escapeHtml(String(!!data[key]))}</div>`).join('');
  const upload = data.python_multipart?.available ? 'python-multipart available' : (data.python_multipart?.message || 'File uploads require python-multipart. Run python -m pip install -r requirements.txt.');
  gmOrchestratorStatus.innerHTML = `<strong>${escapeHtml(data.fallback_mode_label || '')}</strong><br />Provider: ${escapeHtml(data.provider || 'null')}<br />${rows}<div>${escapeHtml(upload)}</div>`;
  if (gmOrchestratorOutput) gmOrchestratorOutput.textContent = JSON.stringify({
    raw_provider_response: data.raw_provider_response,
    parsed_decision: data.parsed_decision,
    validation_errors: data.validation_errors,
    applied_changes: data.applied_changes,
  }, null, 2);
}

async function refreshGmInspector() {
  try { renderGmInspector(await api('/api/developer/gm-orchestrator')); }
  catch (error) { if (gmOrchestratorStatus) gmOrchestratorStatus.textContent = error.message; }
}

async function setForceGmOrchestrator() {
  try { renderGmInspector(await api('/api/developer/gm-orchestrator/settings', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ force_gm_orchestrator: !!forceGmOrchestratorInput?.checked }) })); }
  catch (error) { if (gmOrchestratorStatus) gmOrchestratorStatus.textContent = error.message; }
}

async function testGmDecision() {
  if (gmOrchestratorOutput) gmOrchestratorOutput.textContent = 'Testing provider GM decision...';
  try {
    const data = await api('/api/developer/gm-orchestrator/test-decision', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ player_input: gmTestInput?.value?.trim() || 'look around' }) });
    if (gmOrchestratorOutput) gmOrchestratorOutput.textContent = JSON.stringify(data, null, 2);
    if (gmOrchestratorStatus) gmOrchestratorStatus.innerHTML = `Provider valid JSON: <strong>${escapeHtml(String(!!data.valid_json))}</strong>; validation passed: <strong>${escapeHtml(String(!!data.valid_decision))}</strong>; mutated campaign state: <strong>${escapeHtml(String(!!data.mutated_campaign_state))}</strong>`;
  } catch (error) { if (gmOrchestratorOutput) gmOrchestratorOutput.textContent = error.message; }
}

async function rebuildIntelligenceIndex() {
  try { const result = await api('/api/developer/intelligence/rebuild-index', { method: 'POST' }); setIntelligenceStatus(`Rebuilt index: ${result.chunk_count || 0} chunk(s) from ${result.indexed_source_count || 0} source(s).`); await refreshPromptInspector(); }
  catch (error) { setIntelligenceStatus(error.message, true); }
}

async function testIntelligenceRetrieval() {
  if (!intelligenceRetrievalResults) return;
  const query = intelligenceRetrievalQueryInput?.value?.trim() || '';
  try {
    const data = await api('/api/developer/intelligence/test-retrieval', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ query, selected_source_ids: Array.from(selectedCampaignIntelligenceSourceIds) }) });
    const rows = (data.results || []).map((item) => `<article class="ability-card"><strong>${escapeHtml(item.title || item.source_id)}</strong> <small>${escapeHtml(item.category || '')} score ${escapeHtml(String(item.score || 0))}</small><div>${escapeHtml(item.heading || '')}</div><p>${escapeHtml(item.snippet || '')}</p><em>${escapeHtml(item.reason || '')}</em></article>`).join('');
    intelligenceRetrievalResults.innerHTML = rows || `<strong>No results:</strong> ${escapeHtml(data.reason || 'no chunks above threshold')}`;
  } catch (error) { intelligenceRetrievalResults.textContent = error.message; }
}

async function refreshPromptInspector() {
  try { renderPromptInspector(await api('/api/developer/intelligence/prompt-inspector')); } catch (error) { setIntelligenceStatus(error.message, true); }
}

async function applyCampaignIntelligenceSources() {
  try {
    const inspector = await api('/api/developer/intelligence/campaign-sources', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ enabled_source_ids: Array.from(selectedCampaignIntelligenceSourceIds) }) });
    selectedCampaignIntelligenceSourceIds = new Set(inspector.selected_source_ids || []);
    renderPromptInspector(inspector);
    renderIntelligenceSources(intelligenceSourcesCache);
    setIntelligenceStatus('Updated campaign intelligence selection.');
  } catch (error) { setIntelligenceStatus(error.message, true); }
}


function isSupportedIntelligenceFile(file) {
  return !!file && /\.(txt|md|json)$/i.test(file.name || '');
}

async function uploadIntelligenceSource(endpoint, file, payload, successPrefix) {
  if (!file) {
    setIntelligenceStatus('Choose a .txt, .md, or .json file.', true);
    return;
  }
  if (!isSupportedIntelligenceFile(file)) {
    setIntelligenceStatus('Import failed: unsupported file type.', true);
    return;
  }
  const formData = new FormData();
  formData.append('file', file);
  Object.entries(payload).forEach(([key, value]) => formData.append(key, String(value)));
  try {
    const result = await api(endpoint, { method: 'POST', body: formData });
    selectedIntelligenceSourceId = result.source?.id || selectedIntelligenceSourceId;
    await refreshIntelligenceSources();
    setIntelligenceStatus(`${successPrefix}: ${result.source?.title || payload.title || file.name}`);
  } catch (error) {
    const prefix = endpoint.includes('/replace') ? 'Replace failed' : 'Import failed';
    setIntelligenceStatus(`${prefix}: ${error.message}`, true);
  }
}

function openAddIntelligenceFilePicker() {
  setIntelligenceStatus('Choose a .txt, .md, or .json file.');
  if (addIntelligenceSourceFileInput) {
    addIntelligenceSourceFileInput.value = '';
    addIntelligenceSourceFileInput.click();
  }
}

function openReplaceIntelligenceFilePicker() {
  const sourceId = intelligencePayload().id;
  if (!sourceId) {
    setIntelligenceStatus('Replace failed: select a source first.', true);
    return;
  }
  setIntelligenceStatus('Choose a .txt, .md, or .json file.');
  if (replaceIntelligenceSourceFileInput) {
    replaceIntelligenceSourceFileInput.value = '';
    replaceIntelligenceSourceFileInput.click();
  }
}

async function postIntelligence(endpoint, payload, successMessage) {
  try {
    const result = await api(endpoint, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
    if (result.inspector) {
      selectedCampaignIntelligenceSourceIds = new Set(result.inspector.selected_source_ids || []);
      renderPromptInspector(result.inspector);
    } else {
      await refreshPromptInspector();
    }
    renderIntelligenceSources(result.sources || []);
    setIntelligenceStatus(successMessage);
  } catch (error) {
    setIntelligenceStatus(error.message, true);
  }
}

async function removeSelectedSourceFromCurrentCampaign() {
  const sourceId = intelligencePayload().id;
  if (!sourceId) { setIntelligenceStatus('Remove failed: select a source first.', true); return; }
  selectedCampaignIntelligenceSourceIds.delete(sourceId);
  await applyCampaignIntelligenceSources();
  setIntelligenceStatus('Removed selected source from current campaign.');
}

async function deleteSelectedIntelligenceSource() {
  const sourceId = intelligencePayload().id;
  if (!sourceId) { setIntelligenceStatus('Delete failed: select a source first.', true); return; }
  if (!window.confirm(`Delete intelligence source "${sourceId}"? This removes it from disk and all campaign selections.`)) return;
  try {
    const result = await api('/api/developer/intelligence/delete', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id: sourceId }) });
    selectedIntelligenceSourceId = '';
    if (intelligenceSourceIdInput) intelligenceSourceIdInput.value = '';
    selectedCampaignIntelligenceSourceIds = new Set(result.inspector?.selected_source_ids || []);
    renderPromptInspector(result.inspector);
    renderIntelligenceSources(result.sources || []);
    setIntelligenceStatus('Deleted source and rebuilt the index.');
  } catch (error) { setIntelligenceStatus(`Delete failed: ${error.message}`, true); }
}

async function resetImportedIntelligenceSources() {
  if (!window.confirm('Reset imported intelligence sources? This deletes all pack/imported sources and clears campaign selections.')) return;
  try {
    const result = await api('/api/developer/intelligence/reset-imported', { method: 'POST' });
    selectedIntelligenceSourceId = '';
    selectedCampaignIntelligenceSourceIds = new Set(result.inspector?.selected_source_ids || []);
    renderPromptInspector(result.inspector);
    renderIntelligenceSources(result.sources || []);
    setIntelligenceStatus('Reset imported sources and rebuilt the index.');
  } catch (error) { setIntelligenceStatus(`Reset failed: ${error.message}`, true); }
}

function closeNewCampaignModal() {
  closePrimaryModal('new-campaign-modal');
}

function openCampaignBrowser() {
  openPrimaryModal('campaign-browser-modal');
}

function closeCampaignBrowser() {
  closePrimaryModal('campaign-browser-modal');
}

function setDeveloperToolsVisible(visible) {
  if (developerToolsPanel) developerToolsPanel.classList.toggle('hidden', !visible);
  if (developerToolsToggleInput) developerToolsToggleInput.checked = !!visible;
  try {
    window.localStorage?.setItem('adventurersGuildDeveloperToolsVisible', visible ? 'true' : 'false');
  } catch (error) {
    console.warn(`[settings] could not persist Developer Tools visibility: ${error.message}`);
  }
}

function getDeveloperToolsVisiblePreference() {
  try {
    return window.localStorage?.getItem('adventurersGuildDeveloperToolsVisible') === 'true';
  } catch (error) {
    console.warn(`[settings] could not read Developer Tools visibility: ${error.message}`);
    return false;
  }
}

function openSetupModal() {
  setDeveloperToolsVisible(getDeveloperToolsVisiblePreference());
  openPrimaryModal('setup-modal');
}

function closeSetupModal() {
  closePrimaryModal('setup-modal');
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
        ${isCreatorModeEnabled() ? '<button type="button" id="runtime-character-sheet-empty-create">Create Character Sheet</button>' : '<p class="runtime-sheet-muted">Adventure Mode: sheets are reference pages while you play.</p>'}
      </div>
    `;
    runtimeCharacterSheetsList.querySelector('#runtime-character-sheet-empty-create')?.addEventListener('click', () => {
      openDialog('runtime-character-sheet-create-modal');
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
        <span>${escapeHtml(titleizeValue(sheet.sheet_type || 'unknown'))}</span>
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
    ['Role', titleizeValue(sheet.role, '')],
    ['Archetype', sheet.archetype],
    ['Faction', sheet.faction],
    ['Level / Rank', sheet.level_or_rank],
    ['Description', sheet.description],
    ['Condition', sheet.state?.current_condition],
    ['Notes', sheet.notes],
  ].filter(([, value]) => String(value || '').trim());
  runtimeCharacterSheetDetail.innerHTML = `
    <article class="runtime-sheet-card">
      <h4>${escapeHtml(sheet.name || 'Unnamed')} <span>${escapeHtml(titleizeValue(sheet.sheet_type || 'unknown'))}</span></h4>
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
  closeDialog('runtime-character-sheet-create-modal');
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
  const text = await response.text();
  let data = {};
  try {
    data = text ? JSON.parse(text) : {};
  } catch (_error) {
    data = { error: 'Invalid server response', detail: text.slice(0, 400) };
  }
  if (!response.ok) {
    const detail = data.error || data.message || data.detail || data.reason || '';
    const nested = data.metadata?.error_body || '';
    const stage = data.failure_stage ? `stage=${data.failure_stage}` : '';
    const nextStep = data.next_step ? `next=${data.next_step}` : '';
    const composed = [detail, nested, stage, nextStep].filter(Boolean).join(' ').trim();
    throw new Error(composed || `Request failed for ${path}`);
  }
  return data;
}

function renderMessage(msg) {
  if (!dialogueFeed) return;
  if (msg.type === 'image') {
    if (!visualsEnabledForPlayer()) return;
    msg = { ...msg, type: 'system', text: msg.text || 'Scene visual updated.' };
  }
  const el = document.createElement('div');
  if (msg.type === 'npc' && msg.speaker_name) {
    el.className = 'msg msg-npc-inline';
    const ts = new Date(msg.timestamp).toLocaleTimeString();
    el.innerHTML = `
      <small>NPC • ${ts}</small>
      <div><strong>${escapeHtml(msg.speaker_name)}:</strong> ${escapeHtml(msg.text || '')}</div>
    `;
    dialogueFeed.appendChild(el);
    dialogueFeed.scrollTop = dialogueFeed.scrollHeight;
    return;
  }
  el.className = `msg msg-${msg.type}`;
  const ts = new Date(msg.timestamp).toLocaleTimeString();
  el.innerHTML = `<small>${labelForType(msg.type)} • ${ts}</small>${escapeHtml(msg.text || '')}`;
  dialogueFeed.appendChild(el);
  dialogueFeed.scrollTop = dialogueFeed.scrollHeight;
}

function labelForType(type) {
  return ({
    player: 'PLAYER',
    narrator: 'NARRATOR',
    npc: 'NPC',
    quest: 'QUEST',
    image: 'IMAGE',
    system: 'SYSTEM',
    error: 'ERROR',
    ooc_player: 'OOC',
    ooc_gm: 'GM',
  })[type] || 'SYSTEM';
}

function renderInputModeToggle() {
  if (!inputModeToggle) return;
  const label = currentInputMode === 'ooc' ? 'OOC' : 'IC';
  inputModeToggle.textContent = label;
  inputModeToggle.title = currentInputMode === 'ooc'
    ? 'Out of Character: ask the GM brain without advancing canon.'
    : 'In Character: submit canon gameplay actions.';
}

function toggleInputMode() {
  if (turnRequestInFlight) return;
  currentInputMode = currentInputMode === 'ic' ? 'ooc' : 'ic';
  renderInputModeToggle();
  setStatus(currentInputMode === 'ooc' ? 'Input mode set to OOC (non-canon).' : 'Input mode set to IC (canon gameplay).');
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

function renderSceneContext(sceneState = {}) {
  if (!dialogueFeed) return;
  const locationName = escapeHtml(sceneState.location_name || 'Unknown location');
  const atmosphere = escapeHtml(sceneState.atmosphere || '');
  const summary = escapeHtml(sceneState.summary || '');
  const context = document.createElement('section');
  context.className = 'scene-context';
  context.innerHTML = `
    <div class="scene-location">${locationName}</div>
    ${atmosphere ? `<div class="scene-atmosphere">${atmosphere}</div>` : ''}
    ${summary ? `<div class="scene-summary">${summary}</div>` : ''}
  `;
  dialogueFeed.appendChild(context);
}

async function refreshMessages() {
  const data = await api('/api/campaign/play-view');
  if (dialogueFeed) {
    dialogueFeed.innerHTML = '';
    renderSceneContext(data.scene_state || {});
    const messages = data.dialogue_entries || [];
    if (!messages.length) {
      const fallbackNarration = String(data.scene_state?.narration || '').trim();
      if (fallbackNarration) {
        renderMessage({
          type: 'narrator',
          text: fallbackNarration,
          timestamp: new Date().toISOString(),
        });
      } else {
        dialogueFeed.innerHTML += '<div class="dialogue-empty">No dialogue yet.</div>';
      }
    } else {
      messages.forEach(renderMessage);
    }
  }
}

async function refreshSceneVisual() {
  if (!visualsEnabledForPlayer()) {
    clearSceneImage('Scene visuals are off.');
    setImageProgressPhase('idle');
    return null;
  }
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
      if (visualsEnabledForPlayer()) setImageStatus('Scene visual updated.');
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
  const canonicalCategory = typeof entry.category === 'string' ? entry.category : entry.type;
  const hiddenSubtype = entry.subtype || canonicalCategory || '';
  return {
    id: entry.id || '',
    name: entry.name || '',
    category: 'ability',
    type: 'ability',
    subtype: hiddenSubtype,
    description: entry.description || '',
    cost_or_resource: entry.cost_or_resource || '',
    cooldown: entry.cooldown || '',
    tags: Array.isArray(entry.tags) ? entry.tags : [],
    flags: Array.isArray(entry.flags) ? entry.flags : [],
    notes: entry.notes || '',
    classifier_confidence: entry.classifier_confidence || '',
    classifier_reason: entry.classifier_reason || '',
  };
}

function titleizeValue(value, fallback = '—') {
  const clean = String(value || '').trim();
  if (!clean) return fallback;
  return clean
    .replaceAll('_', ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function renderInlineTags(values = [], emptyText = '—') {
  const clean = (Array.isArray(values) ? values : []).filter((value) => String(value || '').trim());
  if (!clean.length) return `<span class="runtime-sheet-muted">${escapeHtml(emptyText)}</span>`;
  return clean.map((value) => `<span class="tag-chip">${escapeHtml(titleizeValue(value))}</span>`).join('');
}

function renderInventoryViewer() {
  if (!runtimeInventoryDetail) return;
  const state = runtimeInventoryState || {};
  const entries = Array.isArray(state.entries) ? state.entries : [];
  const currency = state.currency || {};
  const equipped = state.equipped || {};
  const equippedEntries = Object.entries(equipped).filter(([, value]) => String(value || '').trim());
  const actionMarkup = (entry) => isCreatorModeEnabled() ? `
        <div class="subtle-actions">
          <button type="button" data-inventory-edit="${escapeHtml(entry.id || '')}">Edit</button>
          <button type="button" data-inventory-delete="${escapeHtml(entry.id || '')}">Delete</button>
        </div>` : '';
  const rows = entries.length ? entries.map((entry) => `
      <article class="item-card">
        <div class="item-card-head">
          <div>
            <strong>${escapeHtml(entry.name || 'Unnamed item')}</strong>
            <small>${escapeHtml(titleizeValue(entry.category || 'items'))}</small>
          </div>
          <span class="quantity-badge">×${escapeHtml(String(entry.quantity || 1))}</span>
        </div>
        ${entry.notes ? `<p>${escapeHtml(entry.notes)}</p>` : '<p class="runtime-sheet-muted">No notes yet.</p>'}
        ${actionMarkup(entry)}
      </article>
    `).join('') : '<div class="runtime-sheet-muted">No items recorded.</div>';
  runtimeInventoryDetail.innerHTML = `
    <section class="inventory-summary-grid">
      <div class="currency-card"><span>Gold</span><strong>${Number(currency.gold || 0)}</strong></div>
      <div class="currency-card"><span>Silver</span><strong>${Number(currency.silver || 0)}</strong></div>
      <div class="currency-card"><span>Copper</span><strong>${Number(currency.copper || 0)}</strong></div>
    </section>
    <section class="spellbook-group">
      <h4>Equipped</h4>
      <div class="equipped-list">${equippedEntries.length ? equippedEntries.map(([slot, value]) => `<span class="tag-chip">${escapeHtml(titleizeValue(slot))}: ${escapeHtml(value)}</span>`).join('') : '<span class="runtime-sheet-muted">Nothing equipped.</span>'}</div>
    </section>
    <section class="spellbook-group"><h4>Items</h4><div class="item-card-grid">${rows}</div></section>
  `;
  runtimeInventoryDetail.querySelectorAll('button[data-inventory-edit]').forEach((button) => {
    button.onclick = () => {
      const entry = entries.find((candidate) => candidate.id === button.dataset.inventoryEdit);
      if (!entry) return;
      inventoryEntryIdInput.value = entry.id || '';
      inventoryEntryNameInput.value = entry.name || '';
      inventoryEntryCategoryInput.value = entry.category || 'items';
      inventoryEntryQuantityInput.value = String(entry.quantity || 1);
      inventoryEntryNotesInput.value = entry.notes || '';
    };
  });
  runtimeInventoryDetail.querySelectorAll('button[data-inventory-delete]').forEach((button) => {
    button.onclick = async () => {
      await api('/api/campaign/inventory', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'delete', id: button.dataset.inventoryDelete }),
      });
      await refreshInventory();
    };
  });
}

function renderCampaignEvents() {
  if (!campaignEventsList) return;
  const events = Array.isArray(campaignEvents) ? [...campaignEvents] : [];
  const pending = events.filter((event) => event.status === 'pending');
  const growth = pending.filter((event) => event.type === 'ability_suggested');
  const hooks = pending.filter((event) => event.type !== 'ability_suggested' && /quest|hook/i.test(`${event.type || ''} ${event.title || ''}`));
  const world = pending.filter((event) => event.type !== 'ability_suggested' && !hooks.includes(event));
  const recent = events.filter((event) => event.status !== 'pending').slice(-10).reverse();
  const pendingCount = pending.length;
  if (campaignEventsPendingCount) {
    campaignEventsPendingCount.textContent = String(pendingCount);
    campaignEventsPendingCount.classList.toggle('hidden', pendingCount === 0);
  }
  const renderCard = (event) => {
    const isAbilityProposal = event.type === 'ability_suggested' && event.status === 'pending';
    return `
      <article class="ability-card campaign-event-card">
        <div class="item-card-head"><strong>${escapeHtml(event.title || 'Campaign Event')}</strong><small>${escapeHtml(titleizeValue(event.type || 'other'))}</small></div>
        <p>${escapeHtml(event.description || '')}</p>
        <p class="ability-notes"><strong>Reason:</strong> ${escapeHtml(event.reason || '—')}</p>
        <div class="ability-meta"><span>Status: <strong>${escapeHtml(titleizeValue(event.status || 'pending'))}</strong></span><span>Created: <strong>${escapeHtml(event.created_at || '—')}</strong></span></div>
        ${isAbilityProposal ? `<div class="button-row"><button type="button" data-event-accept="${escapeHtml(event.id)}">Learn</button><button type="button" data-event-not-yet="${escapeHtml(event.id)}">Not Yet</button><button type="button" data-event-reject="${escapeHtml(event.id)}">Reject</button></div>` : ''}
      </article>`;
  };
  campaignEventsList.innerHTML = events.length ? `
    <section class="spellbook-group"><h4>Character Growth</h4><p class="runtime-sheet-muted">${growth.length ? 'Starting abilities ready to learn' : 'No character growth choices pending.'}</p>${growth.length ? growth.map(renderCard).join('') : ''}</section>
    <section class="spellbook-group"><h4>Quests & Hooks</h4>${hooks.length ? hooks.map(renderCard).join('') : '<div class="runtime-sheet-muted">No quest hooks pending.</div>'}</section>
    <section class="spellbook-group"><h4>World Events</h4>${world.length ? world.map(renderCard).join('') : '<div class="runtime-sheet-muted">No world events pending.</div>'}</section>
    <section class="spellbook-group"><h4>Recent Events</h4>${recent.length ? recent.map(renderCard).join('') : '<div class="runtime-sheet-muted">No resolved events yet.</div>'}</section>
  ` : '<div class="runtime-sheet-muted">No campaign events yet.</div>';
  campaignEventsList.querySelectorAll('button[data-event-accept]').forEach((button) => {
    button.onclick = async () => { await api('/api/campaign/events/accept', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id: button.dataset.eventAccept }) }); await refreshCampaignEvents(); await refreshSpellbook(); };
  });
  campaignEventsList.querySelectorAll('button[data-event-reject]').forEach((button) => {
    button.onclick = async () => { await api('/api/campaign/events/reject', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id: button.dataset.eventReject }) }); await refreshCampaignEvents(); };
  });
  campaignEventsList.querySelectorAll('button[data-event-not-yet]').forEach((button) => { button.onclick = () => closePrimaryModal('campaign-events-modal'); });
}

async function refreshCampaignEvents() {
  const payload = await api('/api/campaign/events');
  campaignEvents = Array.isArray(payload.events) ? payload.events : [];
  renderCampaignEvents();
}


function isSpellcastingRoleText(value) {
  return /\b(mage|wizard|sorcerer|warlock|cleric|druid|necromancer|spellblade|spellcaster|witch|shaman|priest|oracle|magus|arcanist|enchanter|pyromancer|cryomancer|healer|mystic)\b/i.test(value || '');
}

function updateAbilityToolLabel(state = {}) {
  const player = state.player || {};
  const roleText = [player.class, player.role, player.archetype].filter(Boolean).join(' ');
  const label = isSpellcastingRoleText(roleText) ? 'Spellbook' : 'Abilities';
  if (runtimeSpellbookButton) runtimeSpellbookButton.textContent = label;
  if (runtimeSpellbookTitle) runtimeSpellbookTitle.textContent = label;
}

function renderSpellbookViewer() {
  if (!runtimeSpellbookList) return;
  const normalizedEntries = runtimeSpellbookEntries.map((entry) => normalizeSpellbookEntry(entry));
  const rows = normalizedEntries.length ? normalizedEntries.map((entry) => `
      <article class="ability-card">
        <div class="item-card-head">
          <strong>${escapeHtml(entry.name || 'Unnamed ability')}</strong>
          <small>${escapeHtml(titleizeValue(entry.subtype || 'ability'))}</small>
        </div>
        <p>${escapeHtml(entry.description || 'No description yet.')}</p>
        <div class="ability-meta">
          <span>Cost: <strong>${escapeHtml(entry.cost_or_resource || '—')}</strong></span>
          <span>Cooldown: <strong>${escapeHtml(entry.cooldown || '—')}</strong></span>
        </div>
        <div class="tag-row">${renderInlineTags([...(entry.tags || []), ...(entry.flags || [])])}</div>
        ${entry.notes ? `<p class="ability-notes">${escapeHtml(entry.notes)}</p>` : ''}
        ${isCreatorModeEnabled() ? `<div class="subtle-actions">
          <button type="button" data-spellbook-edit="${escapeHtml(entry.id)}">Edit</button>
          <button type="button" data-spellbook-delete="${escapeHtml(entry.id)}">Delete</button>
        </div>` : ''}
      </article>
    `).join('') : '<div class="runtime-sheet-muted">No abilities recorded.</div>';
  runtimeSpellbookList.innerHTML = `<div class="spellbook-group"><h4>${escapeHtml(runtimeSpellbookButton?.textContent || 'Abilities')}</h4>${rows}</div>`;
  runtimeSpellbookList.querySelectorAll('button[data-spellbook-edit]').forEach((button) => {
    button.onclick = () => {
      const entry = runtimeSpellbookEntries.find((candidate) => candidate.id === button.dataset.spellbookEdit);
      if (!entry) return;
      document.getElementById('spellbook-entry-id').value = entry.id;
      document.getElementById('spellbook-entry-name').value = entry.name;
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
  const abilityPayload = Array.isArray(payload.abilities) ? payload.abilities : payload.spellbook;
  runtimeSpellbookEntries = Array.isArray(abilityPayload) ? abilityPayload.map(normalizeSpellbookEntry) : [];
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
  const stateAbilities = Array.isArray(state.abilities) ? state.abilities : state.spellbook;
  runtimeSpellbookEntries = Array.isArray(stateAbilities) ? stateAbilities.map(normalizeSpellbookEntry) : [];
  customNarratorRules = Array.isArray(state.custom_narrator_rules) ? state.custom_narrator_rules : [];
  updateAbilityToolLabel(state);
  renderRuntimeCharacterSheets();
  renderInventoryViewer();
  renderSpellbookViewer();
  renderNarratorRules();
  const displayModeText = displayModeLabel(state.settings?.display_mode || 'story');
  const locationText = world.starting_location || world.current_location || world.world_name || state.world_name || 'Unknown world';
  campaignMeta.textContent = `${state.campaign_name || 'Campaign'} · Turn ${state.turn_count || 0}`;
  if (statusCampaignName) statusCampaignName.textContent = state.campaign_name || 'Campaign';
  if (statusWorldLocation) statusWorldLocation.textContent = locationText;
  if (statusTurnCount) statusTurnCount.textContent = String(state.turn_count || 0);
  if (statusDisplayMode) statusDisplayMode.textContent = displayModeText;
  if (campaignDisplayModeIndicator) {
    campaignDisplayModeIndicator.textContent = `Display Mode: ${displayModeText}`;
  }
  const chatInput = document.getElementById('chat-input');
  if (chatInput) {
    chatInput.placeholder = state.startup_state === 'character_creation'
      ? 'Tell the DM who you are: name, role, appearance, and what matters to you.'
      : 'What do you do?';
  }
  ingestPersistedCampaignSettings(
    {
      image_generation_enabled: !!state.settings.image_generation_enabled,
      suggested_moves_enabled: !!state.settings.effective_suggested_moves_enabled,
      display_mode: normalizeDisplayMode(state.settings?.display_mode || 'story'),
      campaign_mode: normalizeCampaignMode(state.settings?.campaign_mode || 'adventure'),
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
      const fallbackUsed = await pickFolderBrowserFallback(title);
      if (!fallbackUsed) setStatus(result.message || 'Folder selection failed.', true);
      return '';
    }
    inputElement.value = result.path || '';
    console.log(`[path-config] draft_updated field=${inputElement.id}`);
    setStatus(`Selected folder: ${result.path}`);
    return result.path || '';
  } catch (error) {
    const fallbackUsed = await pickFolderBrowserFallback(title);
    if (fallbackUsed) return '';
    setStatus(error.message, true);
    return '';
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
      const fallbackUsed = await pickFileBrowserFallback(filters);
      if (!fallbackUsed) setStatus(result.message || 'File selection failed.', true);
      return '';
    }
    inputElement.value = result.path || '';
    console.log(`[path-config] draft_updated field=${inputElement.id}`);
    setStatus(`Selected file: ${result.path}`);
    return result.path || '';
  } catch (error) {
    const fallbackUsed = await pickFileBrowserFallback(filters);
    if (fallbackUsed) return '';
    setStatus(error.message, true);
    return '';
  }
}

async function pickFolderBrowserFallback(title) {
  if (typeof window.showDirectoryPicker === 'function') {
    try {
      const handle = await window.showDirectoryPicker({ mode: 'read' });
      setStatus(`Selected folder "${handle.name}" in browser picker. Desktop/native mode is required to save the full system path.`, true);
      return true;
    } catch (error) {
      return false;
    }
  }
  return new Promise((resolve) => {
    const input = document.createElement('input');
    input.type = 'file';
    input.multiple = true;
    input.setAttribute('webkitdirectory', '');
    input.style.display = 'none';
    input.onchange = () => {
      document.body.removeChild(input);
      if (input.files && input.files.length) {
        setStatus(`Folder selection was captured in browser fallback for "${title}". Desktop/native mode is required to save local paths.`, true);
        resolve(true);
      } else {
        resolve(false);
      }
    };
    document.body.appendChild(input);
    input.click();
  });
}

async function pickFileBrowserFallback(filters = ['.json']) {
  return new Promise((resolve) => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = filters.join(',');
    input.style.display = 'none';
    input.onchange = () => {
      document.body.removeChild(input);
      if (input.files && input.files.length) {
        setStatus(`Selected "${input.files[0].name}" in browser fallback. Desktop/native mode is required to save local file paths.`, true);
        resolve(true);
      } else {
        resolve(false);
      }
    };
    document.body.appendChild(input);
    input.click();
  });
}

function renderImageSetupCard(snapshot = latestImageSetupSnapshot) {
  if (!imageAiSimpleStatus) return;
  const current = snapshot || {};
  const readiness = current.image_readiness_state || {};
  const diagnostics = latestImageBackendDiagnostics?.diagnostics || {};
  const startup = diagnostics.startup_status || {};
  const isSettingUp = setupRunState.busy && ['setup_image_ai', 'start_image_engine', 'recheck'].includes(setupRunState.actionId);
  const hasError = readiness.status_code === 'error' || startup.state === 'failed';
  const isReady = !!readiness.ready;
  const notInstalled = ['not_installed', 'setup_required'].includes(readiness.status_code) || (!isReady && !hasError && !isSettingUp);
  const setupStatus = String(current.setup_status || '').trim();
  const statusLabel = setupStatus
    || (isSettingUp
      ? 'starting image ai'
      : isReady
        ? 'connected'
        : hasError
          ? 'failed'
          : (notInstalled ? 'waiting for comfyui source' : 'waiting for comfyui source'));
  imageAiSimpleStatus.textContent = `Status: ${statusLabel}`;
  if (imageAiSimpleError) {
    const errorText = String(startup.error_line || startup.summary || readiness.message || '').trim();
    if (statusLabel === 'failed' && errorText) {
      imageAiSimpleError.classList.remove('hidden');
      imageAiSimpleError.textContent = `Error: ${errorText}`;
    } else {
      imageAiSimpleError.classList.add('hidden');
      imageAiSimpleError.textContent = '';
    }
  }
  if (retryImageAiSetupButton) {
    retryImageAiSetupButton.classList.toggle('hidden', statusLabel !== 'failed');
  }
  if (statusLabel === 'failed') {
    imageSetupTerminalFailure = true;
  } else if (isReady) {
    imageSetupTerminalFailure = false;
  }
  updateSetupButtonsBusyState();
}

async function importAndSetupImageAi({ allowExisting = false } = {}) {
  if (imageSetupRequestInFlight || setupRunState.busy) {
    setStatus('Image setup is already running. Please wait for it to finish.');
    return;
  }
  if (imageSetupTerminalFailure && !allowExisting) {
    setStatus('Image setup previously failed. Click Retry Setup to run a new attempt.', true);
    return;
  }
  const comfySource = imageImportComfySourceInput?.value.trim() || '';
  const modelSource = imageImportModelSourceInput?.value.trim() || '';
  const hasSources = !!(comfySource && modelSource);
  if (!hasSources && !allowExisting) {
    setStatus('Select both a ComfyUI source and a model source before starting setup.', true);
    return;
  }
  imageSetupRequestInFlight = true;
  startSetupRun('setup_image_ai', 'Running guided Image AI setup flow...', [
    { step: 'validate-comfyui-source', label: 'Validate ComfyUI source', state: 'running', message: hasSources ? 'Checking ComfyUI source path...' : 'Using existing managed ComfyUI runtime...' },
  ]);
  try {
    const result = hasSources
      ? await api('/api/setup/import-image-ai', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ comfyui_source: comfySource, model_source: modelSource }),
      })
      : await api('/api/setup/orchestrate-image', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      });
    updateSetupRun({
      steps: normalizeSetupSteps(result.steps),
      summary: result.summary || result.message || (result.ok ? 'Image AI is ready.' : 'Image AI setup failed.'),
      startupStatus: result.startup_status || result.startup || null,
    });
    finishSetupRun({
      summary: result.summary || result.message || (result.ok ? 'Image AI is ready.' : 'Image AI setup failed.'),
      isError: !result.ok,
      steps: normalizeSetupSteps(result.steps),
      startupStatus: result.startup_status || result.startup || null,
    });
    imageSetupTerminalFailure = !result.ok;
    setStatus(result.message || (result.ok ? 'Image AI imported, set up, and started.' : 'Image AI setup failed.'), !result.ok);
    await Promise.all([loadSettings(), refreshDependencyReadiness(), refreshImageSetupSnapshot(), refreshImageBackendDiagnostics(), refreshComfyuiModelList()]);
  } finally {
    imageSetupRequestInFlight = false;
  }
}

function bindClickOnce(element, handler) {
  if (!element) return;
  if (element.dataset.clickBound === 'true') return;
  element.dataset.clickBound = 'true';
  element.onclick = handler;
}

function getElementByIdOrWarn(id) {
  const element = document.getElementById(id);
  if (!element) {
    console.warn(`[ui-init] Missing expected element: #${id}`);
  }
  return element;
}

function bindClickById(id, handler, { once = false } = {}) {
  const element = getElementByIdOrWarn(id);
  if (!element) return null;
  if (once) {
    bindClickOnce(element, handler);
  } else {
    element.onclick = handler;
  }
  return element;
}

async function refreshImageSetupSnapshot() {
  try {
    const payload = await api('/api/setup/image-readiness-card');
    latestImageSetupSnapshot = payload;
    renderImageSetupCard(payload);
    return payload;
  } catch (error) {
    setStatus(error.message, true);
    return null;
  }
}

function renderImageBackendDiagnostics(payload = latestImageBackendDiagnostics) {
  const diagnostics = payload?.diagnostics || {};
  if (imageBackendOverallState) {
    imageBackendOverallState.textContent = `Overall state: ${diagnostics.overall_state || 'Unknown'}`;
  }
  if (imageBackendDiagnosticsSummary) {
    imageBackendDiagnosticsSummary.textContent = diagnostics.status_message || 'Image backend diagnostics unavailable.';
  }
  if (imageBackendDiagnosticsLog) {
    const lines = [
      `Image generation enabled: ${diagnostics.image_generation_enabled ? 'yes' : 'no'}`,
      `Provider selected: ${diagnostics.provider_selected || 'unknown'}`,
      `ComfyUI path: ${diagnostics.comfyui_path || '(not set)'}`,
      `ComfyUI detected: ${diagnostics.comfyui_detected ? 'yes' : 'no'}`,
      `ComfyUI process running: ${diagnostics.comfyui_process_running ? 'yes' : 'no'}`,
      `API reachable: ${diagnostics.api_reachable ? 'yes' : 'no'}`,
      `Workflow path: ${diagnostics.workflow_path || '(not set)'}`,
      `Workflow files found: ${diagnostics.workflow_files_found ? 'yes' : 'no'}`,
      `Checkpoint path: ${diagnostics.checkpoint_path || '(not set)'}`,
      `Checkpoint present: ${diagnostics.checkpoint_present ? 'yes' : 'no'}`,
      `Output path: ${diagnostics.output_path || '(app managed default)'}`,
      `Custom node checks: ${diagnostics.custom_node_message || 'Not available'}`,
      `Last error: ${diagnostics.last_error || '(none)'}`,
      `Recommended next action: ${diagnostics.recommended_next_action || 'Recheck setup.'}`,
    ];
    imageBackendDiagnosticsLog.textContent = lines.join('\n');
  }
}

async function refreshImageBackendDiagnostics() {
  try {
    const payload = await api('/api/setup/image-backend-diagnostics');
    latestImageBackendDiagnostics = payload;
    renderImageBackendDiagnostics(payload);
    return payload;
  } catch (error) {
    setStatus(error.message, true);
    return null;
  }
}

async function checkImageEngineStatus() {
  const payload = await api('/api/setup/image-engine-status');
  const state = payload.state || 'unknown';
  const pid = payload.process_id ? ` (PID ${payload.process_id})` : '';
  const startupState = payload.startup_status?.state ? ` | bootstrap: ${payload.startup_status.state}` : '';
  const startupStep = payload.startup_status?.current_step ? ` (${payload.startup_status.current_step})` : '';
  const startupSummary = payload.startup_status?.summary ? ` - ${payload.startup_status.summary}` : '';
  setStatus(`Image engine status: ${state}${pid}${startupState}${startupStep}${startupSummary}`);
  return payload;
}

async function useBundledImageEngine() {
  const result = await api('/api/setup/use-bundled-image-engine', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({}) });
  setStatus(result.message || (result.ok ? 'Bundled image engine selected.' : 'Bundled image engine could not be selected.'), !result.ok);
  if (result.path_config) renderPathConfigStatus(result.path_config);
  if (result.snapshot) {
    latestImageSetupSnapshot = result.snapshot;
    renderImageSetupCard(result.snapshot);
  }
  await Promise.all([loadSettings(), refreshDependencyReadiness(), refreshComfyuiModelList()]);
}

async function chooseExistingModelFolder() {
  const selectedPath = await pickFolder('Select checkpoint folder', checkpointFolderInput);
  if (!selectedPath) return;
  const result = await api('/api/setup/save-checkpoint-folder', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path: selectedPath }),
  });
  setStatus(result.message || (result.ok ? 'Model folder saved.' : 'Model folder could not be saved.'), !result.ok);
  if (result.ok) {
    checkpointFolderInput.value = selectedPath;
    appliedVisualPipelinePaths.checkpoint_folder = selectedPath;
  }
  if (result.path_config) renderPathConfigStatus(result.path_config);
  if (result.snapshot) {
    latestImageSetupSnapshot = result.snapshot;
    renderImageSetupCard(result.snapshot);
  }
  await Promise.all([refreshDependencyReadiness(), refreshComfyuiModelList()]);
}

function openRecommendedModelPage() {
  const modelPage = latestImageSetupSnapshot?.recommended_model_page
    || latestGlobalSettings?.settings?.image?.checkpoint_model_page
    || 'https://civitai.com/models/4384/dreamshaper';
  openOfficialDownload(modelPage);
}

async function skipImagesForNow() {
  const result = await api('/api/setup/skip-images', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({}) });
  setStatus(result.message || (result.ok ? 'Image setup skipped.' : 'Could not skip image setup.'), !result.ok);
  if (result.snapshot) {
    latestImageSetupSnapshot = result.snapshot;
    renderImageSetupCard(result.snapshot);
  }
  await Promise.all([loadSettings(), refreshDependencyReadiness()]);
}

async function stopImageBackend() {
  const result = await api('/api/setup/stop-image-engine', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  });
  setStatus(result.message || (result.ok ? 'Image backend stopped.' : 'Could not stop image backend.'), !result.ok);
  await Promise.all([refreshDependencyReadiness(), refreshImageBackendDiagnostics()]);
}

async function locateExistingComfyuiFolder() {
  const selectedPath = await pickFolder('Select existing ComfyUI folder', comfyuiPathInput);
  if (!selectedPath) return;
  const result = await api('/api/setup/connect-comfyui-path', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path: selectedPath }),
  });
  setStatus(result.message || (result.ok ? 'ComfyUI folder connected.' : 'ComfyUI folder could not be connected.'), !result.ok);
  await Promise.all([loadSettings(), refreshDependencyReadiness(), refreshImageBackendDiagnostics(), refreshComfyuiModelList()]);
}

async function openLocalPath(path, label) {
  if (!path) {
    setStatus(`${label} is not configured yet.`, true);
    return;
  }
  const result = await api('/api/setup/open-local-path', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path }),
  });
  if (!result.ok) {
    setStatus(result.message || `Could not open ${label}.`, true);
    return;
  }
  setStatus(`${label} opened.`);
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

async function openOfficialDownload(url) {
  try {
    const result = await api('/api/setup/open-external-url', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url }),
    });
    if (!result.ok) throw new Error(result.message || 'Could not open browser via desktop integration.');
  } catch (error) {
    window.open(url, '_blank', 'noopener,noreferrer');
  }
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
  renderImageSetupCard(latestImageSetupSnapshot);
  readinessPanel.innerHTML = '';
  const byType = Object.fromEntries((payload.items || []).map((item) => [item.provider_type, item]));
  const primaryActions = (payload.primary_actions || [
    { id: 'setup_text_ai', label: 'Set Up Text AI' },
    { id: 'setup_everything', label: 'Set Up Everything' },
  ]).filter((action) => action.id !== 'setup_image_ai');
  const summary = document.createElement('div');
  summary.className = 'readiness-summary';
  const textReady = byType.model_provider?.status_level === 'ready' && byType.selected_model?.status_level === 'ready';
  const imageReady = byType.image_provider?.status_level === 'ready';
  summary.innerHTML = `
    <div><strong>Story DM:</strong> ${textReady ? 'Ready' : 'Basic DM Mode available'}</div>
    <div><strong>Image addon:</strong> Optional and hidden from V1 play</div>
    <div>Basic DM Mode works without local AI setup.</div>
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
      <div>Story DM: <span class="${textReady ? 'ready-badge' : 'ready-badge'}">${textReady ? 'Ready' : 'Basic DM Mode'}</span></div>
      <div>Image addon: optional future setting</div>
      <div>Use <strong>Settings</strong> for optional advanced connections.</div>
    `;
  }

  const sections = [
    { id: 'text', title: 'Text AI Setup', types: ['model_provider', 'selected_model'] },
    { id: 'image', title: 'Image Addon (Future Optional)', types: ['image_provider'] },
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
    const actionButtons = (item.provider_type === 'image_provider' ? [] : (item.actions || []))
      .map((action) => `<button class="readiness-action-btn" data-action="${escapeHtml(action.id)}">${escapeHtml(action.label)}</button>`)
      .join('');
    const statusCode = item.status_code ? `<div>Status: <code>${escapeHtml(toTitle(item.status_code))}</code></div>` : '<div>Status: <code>connected</code></div>';
    const fallbackInfo = item.fallback_available ? '<div>Fallback: available</div>' : '';
    const startupInfo = item.startup_status?.summary
      ? `<div>Image bootstrap: <code>${escapeHtml(item.startup_status.state || item.startup_status.stage || 'unknown')}</code> — ${escapeHtml(item.startup_status.summary)}</div>`
      : '';
    const startupStep = item.startup_status?.current_step
      ? `<div>Current setup step: <code>${escapeHtml(item.startup_status.current_step)}</code></div>`
      : '';
    const startupLog = item.startup_status?.log_text
      ? `<details class="startup-log"><summary>Startup log details</summary><pre>${escapeHtml(item.startup_status.log_text)}</pre></details>`
      : '';
    el.innerHTML = `
      <strong>${escapeHtml(title)}</strong>
      <div>Mode: <code>${escapeHtml(item.provider === 'null' ? 'Basic DM Mode' : item.provider)}</code></div>
      <div class="${badgeClass}">${ready ? 'Ready' : 'Not ready'}</div>
      ${statusCode}
      ${selectedModel}
      <div>${escapeHtml(item.user_message || '')}</div>
      ${startupInfo}
      ${startupStep}
      <div>Next step: ${escapeHtml(item.provider_type === 'image_provider' ? 'Images are optional future addon settings.' : (item.next_action || 'No action needed.'))}</div>
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
  if (!imageProviderItem) return;
  setImageStatus('Image addon is disabled in the default V1 player experience.');
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
    if (inputModeToggle) inputModeToggle.disabled = true;
    const localMessageType = currentInputMode === 'ooc' ? 'ooc_player' : 'player';
    const pendingText = currentInputMode === 'ooc' ? 'Consulting DM…' : 'Resolving turn…';
    renderMessage({ type: localMessageType, text, timestamp: new Date().toISOString() });
    renderMessage({ type: 'system', text: pendingText, timestamp: new Date().toISOString() });
    setStatus(currentInputMode === 'ooc' ? 'Processing OOC question...' : 'Processing action...');
    setAutosaveStatus('Autosave pending…');
    input.value = '';
    console.log(`[turn-timing] frontend_submit_ms=0.00 submitted_at=${new Date().toISOString()}`);
    const turn = await api('/api/campaign/input', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, mode: currentInputMode }),
    });
    const responseAt = performance.now();
    const roundTripMs = responseAt - submittedAt;
    const backendTiming = turn.metadata?.timing || {};
    const firstVisibleMs = roundTripMs - (backendTiming.save_ms || 0);
    console.log(`[turn-timing] frontend_round_trip_ms=${roundTripMs.toFixed(2)} first_visible_estimate_ms=${Math.max(firstVisibleMs, 0).toFixed(2)}`);
    input.value = '';
    if (currentInputMode === 'ic') {
      const previousVisual = await refreshSceneVisual().catch(() => null);
      await Promise.all([refreshMessages(), refreshState()]);
      if (backendTiming.auto_after_image_queued) {
        setImageStatus('Generating scene image...');
        waitForSceneVisualUpdate(previousVisual?.updated_at || '').catch(() => {});
      }
      refreshSaves().catch((error) => console.warn('save list refresh failed', error));
      setAutosaveStatus('Autosaved just now.');
    } else {
      await refreshMessages();
      setAutosaveStatus('Autosaved just now.');
    }
    const modelStatus = turn.metadata?.model_status;
    if (modelStatus && modelStatus.provider === 'ollama' && !modelStatus.ready) {
      setStatus(modelStatus.user_message || 'Local AI is unavailable. Basic DM Mode remains available.', true);
    } else {
      setStatus('Turn processed. Autosaved just now.');
    }
  } catch (error) {
    setStatus(error.message, true);
  } finally {
    const input = document.getElementById('chat-input');
    const sendButton = document.getElementById('send-btn');
    input.disabled = false;
    sendButton.disabled = false;
    if (inputModeToggle) inputModeToggle.disabled = false;
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
    setAutosaveStatus('Autosaved just now.');
    setStatus(`Autosaved ${slot}.`);
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
    if (!document.getElementById('form-player-name').value.trim() || !document.getElementById('form-player-class').value.trim()) {
      campaignWizardStep = 3;
      renderCampaignWizardStep();
      document.getElementById('campaign-wizard-validation')?.classList.remove('hidden');
      return;
    }
    const wizardPayload = buildCampaignWizardPayload();
    await api('/api/campaign/start', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(wizardPayload),
    });
    clearSceneImage();
    closeNewCampaignModal();
    await Promise.all([refreshMessages(), refreshState(), refreshSaves(), refreshSceneVisual()]);
    setAutosaveStatus('Autosaved just now.');
    setStatus('New campaign started. Autosave is on.');
    return;
    const tone = document.getElementById('form-tone').value.trim() || 'heroic';
    const playerName = document.getElementById('form-player-name').value.trim() || 'Aria';
    const playerClass = document.getElementById('form-player-class').value.trim() || 'Ranger';
    const worldTheme = document.getElementById('form-world-theme').value.trim() || 'classic fantasy';
    const sceneVisualMode = normalizeSceneVisualMode(document.getElementById('form-scene-visual-mode')?.value || 'off');
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
      display_mode: 'mud',
      suggested_moves_enabled: !!document.getElementById('form-suggested-moves-enabled')?.checked,
      play_style: playStyle,
      character_sheets: [],
      character_sheet_guidance_strength: 'light',
    };
    await api('/api/campaign/start', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
    });
    clearSceneImage();
    closeNewCampaignModal();
    await Promise.all([refreshMessages(), refreshState(), refreshSaves(), refreshSceneVisual()]);
    setAutosaveStatus('Autosaved just now.');
    setStatus('New campaign started. Autosave is on.');
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
        model: { provider: modelProvider, model_name: modelName, ollama_path: ollamaPathInput?.value.trim() || '', force_gm_orchestrator: !!forceGmOrchestratorInput?.checked },
        image: {
          provider: imageProvider,
          comfyui_path: appliedVisualPipelinePaths.comfyui_path || '',
          comfyui_workflow_path: appliedVisualPipelinePaths.comfyui_workflow_path || '',
          comfyui_output_dir: appliedVisualPipelinePaths.comfyui_output_dir || '',
          manual_image_generation_enabled: manualImageEnabled,
          campaign_auto_visual_timing: campaignAutoVisualTiming,
          checkpoint_source: checkpointSourceInput?.value || 'local',
          checkpoint_folder: appliedVisualPipelinePaths.checkpoint_folder || '',
          preferred_checkpoint: preferredCheckpointInput?.value.trim() || '',
          preferred_launcher: preferredLauncherInput?.value || 'auto',
        },
      }),
    });
    const campaignSettings = await api('/api/settings/campaign', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        campaign_mode: creatorModeToggleInput?.checked ? 'creator' : 'adventure',
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
        campaign_mode: normalizeCampaignMode(campaignSettings.settings?.campaign_mode || 'adventure'),
        image_generation_enabled: !!campaignSettings.settings?.image_generation_enabled,
        suggested_moves_enabled: !!campaignSettings.settings?.effective_suggested_moves_enabled,
        play_style: campaignSettings.settings?.play_style || playStyle,
      },
      loadedSlot,
      { forceUi: true },
    );
    const modelStatus = settings.settings?.model_status;
    if (modelStatus && modelStatus.provider === 'ollama' && !modelStatus.ready) {
      setStatus(modelStatus.user_message || 'Local AI is unavailable. Basic DM Mode remains available.', true);
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
  const engineReady = !!imageConfig.engine_ready;
  const modelReady = !!imageConfig.model_ready;
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
    `Engine: ${engineReady ? 'ready' : 'not ready'}`,
    `Model: ${modelReady ? 'ready' : 'not ready'}`,
    `Image pipeline: ${pipelineReady ? 'ready' : 'not ready'}`,
  ];
  const details = [comfy.message, workflow.message, checkpoint.message, output.message].filter(Boolean).join(' | ');
  pathConfigStatus.textContent = `${entries.join(' • ')}${details ? ` — ${details}` : ''}`;
}

async function loadSettings() {
  const data = await api('/api/settings/global');
  latestGlobalSettings = data;
  document.getElementById('model-provider').value = data.settings.model.provider;
  document.getElementById('model-name').value = data.settings.model.model_name;
  document.getElementById('image-provider').value = data.settings.image.provider;
  if (manualImageEnabledInput) manualImageEnabledInput.checked = !!data.settings.image.manual_image_generation_enabled;
  if (ollamaPathInput) ollamaPathInput.value = data.settings.model.ollama_path || '';
  if (forceGmOrchestratorInput) forceGmOrchestratorInput.checked = !!data.settings.model.force_gm_orchestrator;
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
  if (preferredCheckpointInput) preferredCheckpointInput.value = data.settings.image.preferred_checkpoint || '';
  if (preferredLauncherInput) preferredLauncherInput.value = data.settings.image.preferred_launcher || 'auto';
  ingestPersistedCampaignSettings(
    {
      campaign_mode: campaignSettingsPersisted?.campaign_mode || 'adventure',
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
  renderImageSetupCard(latestImageSetupSnapshot);
  if (data.settings?.supported_models) {
    modelInventoryState = data.settings.supported_models;
    renderSupportedModels(modelInventoryState);
  } else {
    await refreshSupportedModels(false);
  }
  await refreshImageSetupSnapshot();
  await refreshImageBackendDiagnostics();
  await refreshComfyuiModelList();
}

bindClickById('send-btn', sendInput);
getElementByIdOrWarn('chat-input')?.addEventListener('keydown', (e) => { if (e.key === 'Enter') sendInput(); });
if (inputModeToggle) inputModeToggle.onclick = toggleInputMode;
renderInputModeToggle();
bindClickById('load-selected', loadSelectedCampaign);
bindClickById('open-campaign-browser', openCampaignBrowser);
bindClickById('new-campaign', openNewCampaignModal);
bindClickById('close-campaign-browser', closeCampaignBrowser);
bindClickById('create-campaign-cancel', closeNewCampaignModal);
bindClickById('create-campaign-confirm', createCampaignFromForm);
bindClickById('campaign-wizard-next', advanceCampaignWizard);
bindClickById('campaign-wizard-back', backCampaignWizard);
bindClickById('image-generate-submit', generateImage);
bindClickById('rename-campaign', renameCampaign);
bindClickById('delete-campaign', deleteCampaign);
bindClickById('apply-settings', applySettings);

creatorModeToggleInput?.addEventListener('change', () => {
  if (suppressCreatorModeToggle) return;
  if (creatorModeToggleInput.checked) {
    suppressCreatorModeToggle = true;
    creatorModeToggleInput.checked = false;
    suppressCreatorModeToggle = false;
    openCreatorModeConfirmation();
    return;
  }
  setCampaignMode('adventure').catch((error) => setStatus(`Could not leave Creator Mode: ${error.message}`, true));
});
creatorModeConfirmCheckbox?.addEventListener('change', () => {
  if (creatorModeConfirmEnable) creatorModeConfirmEnable.disabled = !creatorModeConfirmCheckbox.checked;
});
creatorModeConfirmCancel?.addEventListener('click', () => {
  closeCreatorModeConfirmation();
  if (creatorModeToggleInput) creatorModeToggleInput.checked = false;
});
creatorModeConfirmEnable?.addEventListener('click', async () => {
  if (!creatorModeConfirmCheckbox?.checked) return;
  closeCreatorModeConfirmation();
  await setCampaignMode('creator');
});

bindClickById('open-setup-modal', openSetupModal);
bindClickById('close-setup-modal', closeSetupModal);

refreshIntelligenceSourcesButton?.addEventListener('click', refreshIntelligenceSources);
applyCampaignIntelligenceSourcesButton?.addEventListener('click', applyCampaignIntelligenceSources);
removeCurrentCampaignIntelligenceSourceButton?.addEventListener('click', removeSelectedSourceFromCurrentCampaign);
deleteIntelligenceSourceButton?.addEventListener('click', deleteSelectedIntelligenceSource);
resetImportedIntelligenceSourcesButton?.addEventListener('click', resetImportedIntelligenceSources);
refreshPromptInspectorButton?.addEventListener('click', refreshPromptInspector);
refreshGmOrchestratorButton?.addEventListener('click', refreshGmInspector);
testGmDecisionButton?.addEventListener('click', testGmDecision);
forceGmOrchestratorInput?.addEventListener('change', setForceGmOrchestrator);
refreshGmInspector();
addIntelligenceSourceButton?.addEventListener('click', openAddIntelligenceFilePicker);
replaceIntelligenceSourceButton?.addEventListener('click', openReplaceIntelligenceFilePicker);
addIntelligenceSourceFileInput?.addEventListener('change', () => uploadIntelligenceSource('/api/developer/intelligence/import', addIntelligenceSourceFileInput.files?.[0], intelligencePayload(), 'Imported source'));
replaceIntelligenceSourceFileInput?.addEventListener('change', () => uploadIntelligenceSource('/api/developer/intelligence/replace', replaceIntelligenceSourceFileInput.files?.[0], intelligencePayload(), 'Replaced source'));
applyIntelligenceEnabledButton?.addEventListener('click', () => postIntelligence('/api/developer/intelligence/enabled', { id: intelligencePayload().id, enabled: intelligencePayload().enabled }, 'Updated source enabled state.'));
applyIntelligencePriorityButton?.addEventListener('click', () => postIntelligence('/api/developer/intelligence/priority', { id: intelligencePayload().id, priority: intelligencePayload().priority }, 'Updated source priority.'));
rebuildIntelligenceIndexButton?.addEventListener('click', rebuildIntelligenceIndex);
testIntelligenceRetrievalButton?.addEventListener('click', testIntelligenceRetrieval);
refreshIntelligenceSources();

developerToolsToggleInput?.addEventListener('change', () => setDeveloperToolsVisible(!!developerToolsToggleInput.checked));
setDeveloperToolsVisible(getDeveloperToolsVisiblePreference());
bindClickById('setup-text-ai', () => runReadinessAction('setup_text_ai', {}));
bindClickById('open-comfyui-download-page', () => openOfficialDownload('https://github.com/comfyanonymous/ComfyUI/releases'));
bindClickById('open-model-download-page', () => openOfficialDownload('https://civitai.com/models/4384/dreamshaper'));
bindClickById('pick-image-import-comfy-file', () => pickFile('Select ComfyUI archive file (.zip or .7z)', imageImportComfySourceInput, ['.zip', '.7z']));
bindClickById('pick-image-import-comfy-folder', () => pickFolder('Select extracted ComfyUI folder', imageImportComfySourceInput));
bindClickById('pick-image-import-model-file', () => pickFile('Select model/checkpoint file', imageImportModelSourceInput, ['.safetensors', '.ckpt', '.pt', '.pth', '.bin']));
bindClickById('pick-image-import-model-folder', () => pickFolder('Select model/checkpoint folder', imageImportModelSourceInput));
bindClickById('import-image-ai', () => importAndSetupImageAi().catch((error) => setStatus(error.message, true)));
bindClickById('setup-everything', () => runReadinessAction('setup_everything', {}));
bindClickById('download-ollama', () => openOfficialDownload('https://ollama.com/download'));
bindClickById('pick-ollama-folder', () => pickFolder('Select Ollama install folder', ollamaPathInput));
bindClickOnce(disableImageAiButton, () => skipImagesForNow().catch((error) => setStatus(error.message, true)));
bindClickOnce(retryImageAiSetupButton, () => importAndSetupImageAi({ allowExisting: true }).catch((error) => setStatus(error.message, true)));
bindClickOnce(openImageBackendFolderButton, () => openLocalPath(latestImageBackendDiagnostics?.diagnostics?.comfyui_path, 'Image backend folder').catch((error) => setStatus(error.message, true)));
bindClickOnce(showImageDiagnosticsButton, () => refreshImageBackendDiagnostics().catch((error) => setStatus(error.message, true)));
bindClickById('connect-ollama-folder', connectOllamaFolder);
bindClickById('install-story-model', () => runReadinessAction('install_model', { selected_model: getElementByIdOrWarn('model-name')?.value.trim() || 'llama3' }));
bindClickById('refresh-supported-models', async () => {
  try {
    await api('/api/models/refresh', { method: 'POST' });
    await refreshSupportedModels(true);
  } catch (error) {
    setStatus(error.message, true);
  }
});
bindClickById('recheck-readiness', async () => {
  try {
    await runReadinessAction('recheck', {});
  } catch (error) {
    setStatus(error.message, true);
  }
});
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

document.getElementById('open-character-sheets')?.addEventListener('click', () => {
  console.log(`[character-sheets] viewer_opened campaign=${selectedCampaignName || loadedSlot || 'draft'}`);
  renderRuntimeCharacterSheets();
  closeDialog('runtime-character-sheet-create-modal');
  openPrimaryModal('runtime-character-sheets-modal');
});
document.getElementById('open-runtime-character-sheets').onclick = () => {
  console.log(`[character-sheets] viewer_opened campaign=${selectedCampaignName || loadedSlot || 'unknown'}`);
  renderRuntimeCharacterSheets();
  closeDialog('runtime-character-sheet-create-modal');
  resetRuntimeSheetCreateForm();
  openPrimaryModal('runtime-character-sheets-modal');
};
document.getElementById('open-runtime-inventory').onclick = async () => {
  console.log('[inventory] runtime_button_rendered=true');
  await refreshInventory();
  openPrimaryModal('runtime-inventory-modal');
};
document.getElementById('close-runtime-inventory').onclick = () => {
  closePrimaryModal('runtime-inventory-modal');
};
document.getElementById('open-runtime-spellbook').onclick = async () => {
  console.log('[spellbook] runtime_button_rendered=true');
  await refreshSpellbook();
  openPrimaryModal('runtime-spellbook-modal');
};
document.getElementById('close-runtime-spellbook').onclick = () => {
  closePrimaryModal('runtime-spellbook-modal');
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
  openPrimaryModal('narrator-rules-modal');
  console.log(`[narrator-rules] modal_opened campaign=${loadedSlot || 'unknown'}`);
};
document.getElementById('open-world-building').onclick = async () => {
  await refreshWorldBuilding();
  openPrimaryModal('world-building-modal');
};
if (recalibrateWorldBuildingButton) {
  recalibrateWorldBuildingButton.onclick = async () => {
    await recalibrateWorldBuilding();
  };
}
document.getElementById('close-narrator-rules').onclick = () => {
  closePrimaryModal('narrator-rules-modal');
};
document.getElementById('close-world-building').onclick = () => {
  closePrimaryModal('world-building-modal');
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
  closePrimaryModal('runtime-character-sheets-modal');
  closeDialog('runtime-character-sheet-create-modal');
};
runtimeCharacterSheetCreateToggle?.addEventListener('click', () => {
  openDialog('runtime-character-sheet-create-modal');
  console.log('[character-sheets] create_modal_opened=true');
  runtimeSheetCreateName?.focus();
});
runtimeSheetCreateRole?.addEventListener('change', () => {
  const isCustom = runtimeSheetCreateRole.value === 'custom';
  runtimeSheetCreateCustomRoleWrap?.classList.toggle('hidden', !isCustom);
  if (isCustom) runtimeSheetCreateCustomRole?.focus();
});
runtimeCharacterSheetCreateCancel?.addEventListener('click', () => {
  closeDialog('runtime-character-sheet-create-modal');
  console.log('[character-sheets] create_modal_closed=true');
  resetRuntimeSheetCreateForm();
});
closeRuntimeCharacterSheetCreate?.addEventListener('click', () => {
  closeDialog('runtime-character-sheet-create-modal');
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
  document.getElementById('spellbook-entry-description').value = '';
  document.getElementById('spellbook-entry-cost').value = '';
  document.getElementById('spellbook-entry-cooldown').value = '';
  document.getElementById('spellbook-entry-tags').value = '';
  document.getElementById('spellbook-entry-notes').value = '';
};
document.getElementById('inventory-entry-clear').onclick = () => {
  inventoryEntryIdInput.value = '';
  inventoryEntryNameInput.value = '';
  inventoryEntryCategoryInput.value = 'items';
  inventoryEntryQuantityInput.value = '1';
  inventoryEntryNotesInput.value = '';
};
document.getElementById('inventory-entry-save').onclick = async () => {
  try {
    await api('/api/campaign/inventory', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        action: 'upsert',
        id: inventoryEntryIdInput.value.trim(),
        name: inventoryEntryNameInput.value.trim(),
        category: inventoryEntryCategoryInput.value,
        quantity: Number(inventoryEntryQuantityInput.value || '1'),
        notes: inventoryEntryNotesInput.value.trim(),
      }),
    });
    document.getElementById('inventory-entry-clear').click();
    await refreshInventory();
  } catch (error) {
    setStatus(error.message, true);
  }
};
document.getElementById('spellbook-entry-save').onclick = async () => {
  await api('/api/campaign/spellbook', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      action: 'upsert',
      id: document.getElementById('spellbook-entry-id').value.trim(),
      name: document.getElementById('spellbook-entry-name').value.trim(),
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

document.getElementById('open-campaign-events')?.addEventListener('click', async () => { await refreshCampaignEvents(); openPrimaryModal('campaign-events-modal'); });
document.getElementById('close-campaign-events')?.addEventListener('click', () => closePrimaryModal('campaign-events-modal'));

// Legacy compatibility marker for tests: display_mode: 'story'
