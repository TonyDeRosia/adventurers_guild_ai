from pathlib import Path

from images.base import ImageGenerationRequest
from images.workflow_manager import WorkflowManager


def test_scene_workflow_builds_valid_comfy_graph() -> None:
    manager = WorkflowManager(Path('data/workflows'))
    request = ImageGenerationRequest(
        workflow_id='scene_image',
        prompt='ruined temple at dawn',
        negative_prompt='blurry',
        parameters={
            'seed': 123,
            'steps': 20,
            'cfg': 6.5,
            'width': 640,
            'height': 384,
            'checkpoint': 'dreamshaper.safetensors',
        },
    )

    workflow = manager.build_workflow(request)
    manager.validate_workflow(workflow)

    assert workflow['4']['inputs']['ckpt_name'] == 'dreamshaper.safetensors'
    assert workflow['6']['inputs']['text'] == 'ruined temple at dawn'
    assert workflow['3']['inputs']['seed'] == 123
    assert workflow['3']['inputs']['steps'] == 20
    assert workflow['5']['inputs']['width'] == 640


def test_scene_workflow_missing_required_nodes_fails() -> None:
    manager = WorkflowManager(Path('data/workflows'))
    try:
        manager.validate_workflow({'1': {'class_type': 'KSampler', 'inputs': {}}})
    except ValueError as exc:
        assert 'missing required nodes' in str(exc).lower()
    else:
        raise AssertionError('Expected ValueError for incomplete workflow')
