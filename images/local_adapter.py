"""Local placeholder image generator for GUI-first development flows."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

from images.base import ImageGenerationRequest, ImageGenerationResult, ImageGeneratorAdapter
from images.workflow_manager import WorkflowManager


class LocalPlaceholderImageAdapter(ImageGeneratorAdapter):
    """Writes simple SVG preview images locally without external dependencies."""

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate(self, request: ImageGenerationRequest, workflow_manager: WorkflowManager) -> ImageGenerationResult:
        # Validate template id early so UI errors are actionable.
        workflow_manager.load_template(request.workflow_id)

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
        filename = f"{request.workflow_id}_{timestamp}.svg"
        output_path = self.output_dir / filename
        title = escape(request.prompt.strip() or "Untitled scene")
        subtitle = escape(f"workflow: {request.workflow_id}")
        svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="768" height="512">
  <defs>
    <linearGradient id="bg" x1="0" x2="1" y1="0" y2="1">
      <stop offset="0%" stop-color="#1f2937"/>
      <stop offset="100%" stop-color="#0f172a"/>
    </linearGradient>
  </defs>
  <rect width="100%" height="100%" fill="url(#bg)"/>
  <rect x="24" y="24" width="720" height="464" rx="18" fill="#111827" stroke="#334155" stroke-width="2"/>
  <text x="48" y="90" fill="#38bdf8" font-family="Inter,Segoe UI,Arial,sans-serif" font-size="18">Adventurer Guild AI</text>
  <text x="48" y="138" fill="#e2e8f0" font-family="Inter,Segoe UI,Arial,sans-serif" font-size="28">{title}</text>
  <text x="48" y="184" fill="#94a3b8" font-family="Inter,Segoe UI,Arial,sans-serif" font-size="16">{subtitle}</text>
  <text x="48" y="450" fill="#64748b" font-family="Inter,Segoe UI,Arial,sans-serif" font-size="14">Local placeholder render (no remote service required)</text>
</svg>
"""
        output_path.write_text(svg, encoding="utf-8")
        return ImageGenerationResult(
            success=True,
            workflow_id=request.workflow_id,
            result_path=str(output_path),
            metadata={"renderer": "local_placeholder", "prompt": request.prompt},
        )
