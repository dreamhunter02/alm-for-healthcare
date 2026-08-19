from pathlib import Path

import pytest

from healthcare_alm.models import RetirementRequest
from healthcare_alm.orchestrator.graph import run_workflow


@pytest.fixture(scope="session")
def workflow_result(tmp_path_factory):
    output_dir = tmp_path_factory.mktemp("workflow")
    return run_workflow(RetirementRequest(output_dir=Path(output_dir)))
