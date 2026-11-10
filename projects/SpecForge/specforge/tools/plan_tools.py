"""Plan Agent tools: check_existing_plan, write_plan_file, read_plan_file.

All file access goes through the scoped File I/O plugin (``specforge.plugins.file_io``),
restricted to ``.claude/plans/``.
"""

from __future__ import annotations

import re

from pydantic import BaseModel

from specforge import context
from specforge.config import settings
from specforge.plugins import file_io
from specforge.tools.base import traced_tool


def slug(feature_name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", feature_name.lower()).strip("-") or "feature"


class CheckExistingPlanInput(BaseModel):
    feature_name: str


class CheckExistingPlanOutput(BaseModel):
    exists: bool
    plan_path: str | None = None
    contents: str | None = None


class WritePlanFileInput(BaseModel):
    feature_name: str
    markdown: str


class WritePlanFileOutput(BaseModel):
    plan_path: str


class ReadPlanFileInput(BaseModel):
    plan_path: str


class ReadPlanFileOutput(BaseModel):
    contents: str


@traced_tool(name="check_existing_plan", description="Return an existing plan for this feature, if any.",
             input_model=CheckExistingPlanInput, output_model=CheckExistingPlanOutput, status_label="reading_file")
def check_existing_plan(args: CheckExistingPlanInput) -> CheckExistingPlanOutput:
    path = settings.plans_dir / f"{slug(args.feature_name)}.md"
    if not path.exists():
        return CheckExistingPlanOutput(exists=False)
    return CheckExistingPlanOutput(exists=True, plan_path=str(path.resolve()),
                                   contents=file_io.read_text(path, cache=context.current().cache))


@traced_tool(name="write_plan_file", description="Write the implementation plan to .claude/plans/<feature>.md.",
             input_model=WritePlanFileInput, output_model=WritePlanFileOutput, status_label="generating_plan")
def write_plan_file(args: WritePlanFileInput) -> WritePlanFileOutput:
    path = settings.plans_dir / f"{slug(args.feature_name)}.md"
    return WritePlanFileOutput(plan_path=file_io.write_text(path, args.markdown, cache=context.current().cache))


@traced_tool(name="read_plan_file", description="Read a plan file (served from the run cache when possible).",
             input_model=ReadPlanFileInput, output_model=ReadPlanFileOutput, status_label="reading_file")
def read_plan_file(args: ReadPlanFileInput) -> ReadPlanFileOutput:
    return ReadPlanFileOutput(contents=file_io.read_text(args.plan_path, cache=context.current().cache))
