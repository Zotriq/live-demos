"""Spec Writer tools: read_plan_file (shared), write_spec_file.

Writes are restricted to ``.claude/spec/``; the plan read to ``.claude/plans/``.
"""

from __future__ import annotations

from pydantic import BaseModel

from specforge import context
from specforge.config import settings
from specforge.plugins import file_io
from specforge.tools.base import traced_tool
from specforge.tools.plan_tools import read_plan_file, slug

__all__ = ["read_plan_file", "write_spec_file"]


class WriteSpecFileInput(BaseModel):
    feature_name: str
    markdown: str


class WriteSpecFileOutput(BaseModel):
    spec_path: str


@traced_tool(name="write_spec_file", description="Write the spec-driven document to .claude/spec/<feature>.md.",
             input_model=WriteSpecFileInput, output_model=WriteSpecFileOutput, status_label="writing_spec")
def write_spec_file(args: WriteSpecFileInput) -> WriteSpecFileOutput:
    path = settings.spec_dir / f"{slug(args.feature_name)}.md"
    return WriteSpecFileOutput(spec_path=file_io.write_text(path, args.markdown, cache=context.current().cache))
