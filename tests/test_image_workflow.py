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
    bindings = manager.inspect_bindings(workflow)

    assert bindings.checkpoint_node_ids
    assert bindings.positive_prompt_node_ids
    assert bindings.save_image_node_ids
    assert any(workflow[node]['inputs'].get('ckpt_name') == 'dreamshaper.safetensors' for node in bindings.checkpoint_node_ids)
    assert any(workflow[node]['inputs'].get('text') == 'ruined temple at dawn' for node in bindings.positive_prompt_node_ids)
    assert any(
        isinstance(node, dict)
        and isinstance(node.get('inputs'), dict)
        and node['inputs'].get('seed') == 123
        and node['inputs'].get('steps') == 20
        for node in workflow.values()
    )
    assert any(
        isinstance(node, dict)
        and isinstance(node.get('inputs'), dict)
        and node['inputs'].get('width') == 640
        for node in workflow.values()
    )


def test_scene_workflow_without_output_node_fails() -> None:
    manager = WorkflowManager(Path('data/workflows'))
    try:
        manager.validate_workflow({'1': {'class_type': 'KSampler', 'inputs': {'steps': 10}}})
    except ValueError as exc:
        assert 'output node' in str(exc).lower()
    else:
        raise AssertionError('Expected ValueError for incomplete workflow')
