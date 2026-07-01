from pathlib import Path

APP_JS = Path("app/static/app.js").read_text(encoding="utf-8")
STYLES = Path("app/static/styles.css").read_text(encoding="utf-8")


def test_modal_manager_helpers_and_primary_registry_exist() -> None:
    assert "const modalManager =" in APP_JS
    for helper in ["openPrimaryModal", "closePrimaryModal", "openDialog", "closeDialog"]:
        assert f"function {helper}" in APP_JS
    for modal_id in [
        "campaign-browser-modal",
        "new-campaign-modal",
        "setup-modal",
        "runtime-character-sheets-modal",
        "runtime-inventory-modal",
        "runtime-spellbook-modal",
        "narrator-rules-modal",
        "world-building-modal",
    ]:
        assert f"'{modal_id}'" in APP_JS


def test_primary_modal_switches_requested_flows() -> None:
    assert "this.closePrimaryModal();" in APP_JS
    assert "activePrimaryId" in APP_JS
    assert "openPrimaryModal('runtime-character-sheets-modal')" in APP_JS
    assert "openPrimaryModal('world-building-modal')" in APP_JS
    assert "openPrimaryModal('narrator-rules-modal')" in APP_JS
    assert "openPrimaryModal('setup-modal')" in APP_JS
    assert "closeSettingsBeforeOpeningModal" not in APP_JS


def test_dialogs_are_above_primary_modals_without_closing_them() -> None:
    assert "openDialog('creator-mode-confirm-modal')" in APP_JS
    assert "openDialog('runtime-character-sheet-create-modal')" in APP_JS
    assert "openDialog(id)" in APP_JS
    assert "this.openDialogs.add(id);" in APP_JS
    assert ".modal-dialog" in STYLES
    assert "--modal-z-index: 1100" in STYLES


def test_modal_manager_focuses_and_scrolls_newly_opened_modal() -> None:
    assert "scrollTo({ top: 0, left: 0 })" in APP_JS
    assert "firstInteractive" in APP_JS
    assert ".focus?.({ preventScroll: true })" in APP_JS
    assert "requestAnimationFrame(() => this.focusModal(modal))" in APP_JS


def test_modal_z_index_is_centralized() -> None:
    assert "z-index: var(--modal-z-index, 1000);" in STYLES
    assert ".modal-primary" in STYLES
    assert "--modal-z-index: 1000" in STYLES
