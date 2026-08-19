"""AI-Q/NAT registration for the query-driven medical-device Deep Agent."""

from __future__ import annotations

from decimal import Decimal
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field

AIQ_AVAILABLE = False

try:
    from aiq_agent.agents.deep_researcher.deepagents_runtime import DeepResearchSandboxConfig
    from nat.builder.builder import Builder
    from nat.builder.framework_enum import LLMFrameworkEnum
    from nat.builder.function_info import FunctionInfo
    from nat.cli.register_workflow import register_function
    from nat.data_models.component_ref import FunctionGroupRef, FunctionRef, LLMRef
    from nat.data_models.function import FunctionBaseConfig

    AIQ_AVAILABLE = True
except ImportError:
    Builder = object
    FunctionInfo = None
    FunctionBaseConfig = object


@lru_cache(maxsize=8)
def _get_domain_tools(db_path: str, live_fda: bool):
    from healthcare_alm.agent.domain import MedicalDeviceTools

    return MedicalDeviceTools(db_path=Path(db_path), live_fda=live_fda)


if AIQ_AVAILABLE:

    class HospitalToolConfig(FunctionBaseConfig):
        db_path: Path = Path("output/agent-data/healthcare_alm.db")
        live_fda: bool = False

    class DescribeHospitalDatabaseConfig(HospitalToolConfig, name="healthcare_describe_database"):
        pass

    @register_function(config_type=DescribeHospitalDatabaseConfig)
    async def describe_database_tool(config: DescribeHospitalDatabaseConfig, _builder: Builder):
        async def _run(query: str = "") -> dict:
            del query
            return _get_domain_tools(str(config.db_path), config.live_fda).describe_hospital_database()

        yield FunctionInfo.from_fn(
            _run,
            description=(
                "Inspect the fictional hospital SQLite schema, column meanings, and FDA safety semantics. "
                "Call this before query_hospital_database."
            ),
        )

    class QueryHospitalDatabaseConfig(HospitalToolConfig, name="healthcare_query_database"):
        pass

    class QueryHospitalDatabaseInput(BaseModel):
        sql: str = Field(description="One read-only SQLite SELECT or WITH query.")

    @register_function(config_type=QueryHospitalDatabaseConfig)
    async def query_database_tool(config: QueryHospitalDatabaseConfig, _builder: Builder):
        async def _run(sql: str) -> dict:
            return _get_domain_tools(str(config.db_path), config.live_fda).query_hospital_database(sql)

        yield FunctionInfo.from_fn(
            _run,
            input_schema=QueryHospitalDatabaseInput,
            description=(
                "Run one read-only SELECT/WITH query over fictional hospital inventory and maintenance data. "
                "FDA MAUDE and recall evidence must use their dedicated tools."
            ),
        )

    class SearchMAUDEConfig(HospitalToolConfig, name="healthcare_search_maude"):
        pass

    class SearchMAUDEInput(BaseModel):
        product_code: str = "FRN"
        manufacturer: str | None = None
        model_number: str | None = None
        limit: int = Field(default=50, ge=1, le=200)

    @register_function(config_type=SearchMAUDEConfig)
    async def search_maude_tool(config: SearchMAUDEConfig, _builder: Builder):
        async def _run(
            product_code: str = "FRN",
            manufacturer: str | None = None,
            model_number: str | None = None,
            limit: int = 50,
        ) -> dict:
            return _get_domain_tools(str(config.db_path), config.live_fda).search_maude_events(
                product_code=product_code,
                manufacturer=manufacturer,
                model_number=model_number,
                limit=limit,
            )

        yield FunctionInfo.from_fn(
            _run,
            input_schema=SearchMAUDEInput,
            description=(
                "Search public FDA MAUDE reports by product code and optional manufacturer/model. "
                "Results are safety signals, not unit attribution or incidence rates."
            ),
        )

    class ScoreRetirementConfig(HospitalToolConfig, name="healthcare_score_retirement"):
        pass

    class ScoreRetirementInput(BaseModel):
        asset_ids: list[str] | None = None
        department: str | None = None

    @register_function(config_type=ScoreRetirementConfig)
    async def score_retirement_tool(config: ScoreRetirementConfig, _builder: Builder):
        async def _run(asset_ids: list[str] | None = None, department: str | None = None) -> dict:
            return _get_domain_tools(str(config.db_path), config.live_fda).score_retirement_risk(asset_ids, department)

        yield FunctionInfo.from_fn(
            _run,
            input_schema=ScoreRetirementInput,
            description=(
                "Apply the authoritative healthcare-alm-risk-v1 formula and return ranked component-level scores. "
                "Use this tool for every retirement recommendation."
            ),
        )

    class BuildReplacementPlanConfig(HospitalToolConfig, name="healthcare_build_replacement_plan"):
        pass

    class BuildReplacementPlanInput(BaseModel):
        annual_budget: Decimal = Decimal("120000")
        asset_ids: list[str] | None = None
        department: str | None = None

    @register_function(config_type=BuildReplacementPlanConfig)
    async def build_replacement_plan_tool(config: BuildReplacementPlanConfig, _builder: Builder):
        async def _run(
            annual_budget: Decimal = Decimal("120000"),
            asset_ids: list[str] | None = None,
            department: str | None = None,
        ) -> dict:
            return _get_domain_tools(str(config.db_path), config.live_fda).build_replacement_plan(
                annual_budget, asset_ids, department
            )

        yield FunctionInfo.from_fn(
            _run,
            input_schema=BuildReplacementPlanInput,
            description=(
                "After a separate score_retirement_risk call, phase deterministic scores against an annual replacement "
                "budget. Always call score_retirement_risk first."
            ),
        )

    class HealthcareALMDeepAgentConfig(FunctionBaseConfig, name="healthcare_alm_deep_agent"):
        llm: LLMRef
        tools: list[FunctionRef | FunctionGroupRef] = Field(default_factory=list)
        sandbox: DeepResearchSandboxConfig | FunctionRef
        artifact_db_url: str | None = "sqlite:///output/agent-runs/artifacts.db"

    @register_function(
        config_type=HealthcareALMDeepAgentConfig,
        framework_wrappers=[LLMFrameworkEnum.LANGCHAIN],
    )
    async def healthcare_alm_deep_agent(config: HealthcareALMDeepAgentConfig, builder: Builder):
        from healthcare_alm.agent.deep_agent import MedicalDeviceDeepAgent

        model = await builder.get_llm(config.llm, wrapper_type=LLMFrameworkEnum.LANGCHAIN)
        tools = await builder.get_tools(tool_names=config.tools, wrapper_type=LLMFrameworkEnum.LANGCHAIN)
        if isinstance(config.sandbox, DeepResearchSandboxConfig):
            sandbox_config = config.sandbox
        else:
            sandbox_config = builder.get_function_config(config.sandbox)
        if not isinstance(sandbox_config, DeepResearchSandboxConfig):
            raise TypeError("sandbox must reference a deep_research_sandbox function")

        agent = MedicalDeviceDeepAgent(
            model=model,
            tools=tools,
            sandbox_config=sandbox_config,
            artifact_db_url=config.artifact_db_url,
        )

        async def _run(query: str) -> str:
            return await agent.run(query)

        yield FunctionInfo.from_fn(
            _run,
            description="Answer a medical-device asset lifecycle question with tools and an AI-Q OpenShell sandbox.",
        )
