"""Deterministic model for exercising the real app offline; never a provider evaluation."""
import json
from collections.abc import Sequence
from typing import Any

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import Runnable
from pydantic import BaseModel, Field

from routepilot.agents.models import ModelPolicy, ModelRegistry, Role
from routepilot.shared.config import Settings

from evals.schema import Scenario

ROLE_TOOLS = {
 'freight_scout':['search_offers','get_offer','offer_quality'],
 'fleet_compliance':['list_drivers','driver_state','driver_availability','check_plan_rules'],
 'route_planner':['optimize_driver','optimize_fleet','get_plan','compare_plans'],
 'dispatcher':['request_approval','explain_plan'],
}


def strings(value: Any) -> list[str]:
    if isinstance(value,dict):
        return [text for item in value.values() for text in strings(item)]
    if isinstance(value,list):
        return [text for item in value for text in strings(item)]
    return [value] if isinstance(value,str) else []


class EvalModel(BaseChatModel):
    role: str
    scenario: Scenario
    controller: dict[str,Any] = Field(default_factory=dict)
    structured_schema: str | None = None

    @property
    def _llm_type(self) -> str:
        return 'offline-eval-script'

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> Runnable[Any,Any]:
        self.structured_schema = tools[0].__name__ if tools and isinstance(tools[0],type) and issubclass(tools[0],BaseModel) else None
        return self

    def get_num_tokens_from_messages(self, messages: list[BaseMessage], tools: Sequence[Any] | None = None) -> int:
        return 20

    def _generate(self, messages: list[BaseMessage], stop: list[str] | None = None,
                  run_manager: CallbackManagerForLLMRun | None = None, **kwargs: Any) -> ChatResult:
        context = {}
        for message in messages:
            if isinstance(message,ToolMessage):
                self.controller.setdefault('plans',[]).extend(
                    s for s in strings(json.loads(str(message.content))) if s.startswith('PLAN-'))
            elif message.type == 'human':
                try:
                    parsed = json.loads(str(message.content))
                    if isinstance(parsed,dict):
                        context = parsed
                except ValueError:
                    pass
        plans = sorted(set(self.controller.get('plans',[]) + [p['plan_ref'] for p in context.get('plans',[])]))
        called = self.controller.setdefault('called',[])
        expected = self.scenario.expected_tools
        if self.structured_schema == 'AnswerText':
            tool,args = 'AnswerText',{'summary':'Inspected tool facts.' if self.scenario.locale=='en' else 'Sprawdzono dane z narzędzi.', 'citedFacts':[]}
        elif self.role == 'dispatcher':
            missing = [name for name in expected if name not in called]
            first = missing[0] if missing else None
            owner = next((role for role,names in ROLE_TOOLS.items() if first in names),None)
            if owner and owner != 'dispatcher':
                tool,args = 'DispatcherDecision',dict(next=owner,task=self.scenario.question,rationale='Read deterministic tool facts',assumptions=[])
            elif first:
                tool,args = first,self._arguments(first,plans)
                called.append(first)
            else:
                tool,args = 'DispatcherDecision',dict(next='approve' if self.scenario.expected_approval else 'finish',task=self.scenario.question,rationale='Tool facts inspected',assumptions=[])
        elif self.role == 'explainer':
            tool,args = 'ExplanationOutput',dict(headline='Planning estimate',reasons=[],tradeoffs=[],warnings=[])
        else:
            available = [name for name in expected if name in ROLE_TOOLS[self.role] and name not in called]
            # Rule checks need plans, so return to the supervisor before those exist.
            if available and (available[0] != 'check_plan_rules' or plans):
                tool,args = available[0],self._arguments(available[0],plans)
                called.append(tool)
            elif self.role == 'freight_scout':
                tool,args = 'ScoutReport',dict(candidate_offer_ids=['MOCK-000001','MOCK-000002'],excluded=[],data_issues=[],notes='Synthetic evaluation fixture')
            elif self.role == 'fleet_compliance':
                tool,args = 'FleetReport',dict(drivers=[],warnings=[])
            else:
                tool,args = 'PlannerReport',dict(recommended={'variant':'profit','fleet_solution_id':'profit'} if plans else None,alternatives=[],tradeoffs=[],baseline_uplift=None)
        message = AIMessage(content='',tool_calls=[{'id':f'eval-{len(called)}','name':tool,'args':args}],
                    usage_metadata={'input_tokens':20,'output_tokens':5,'total_tokens':25})
        return ChatResult(generations=[ChatGeneration(message=message)])

    def _arguments(self, name: str, plans: list[str]) -> dict[str,Any]:
        if name in ('list_drivers','search_offers'):
            return {}
        if name in ('driver_state','driver_availability'):
            return {'driver_ref':'D1'}
        if name == 'get_offer':
            return {'offer_id':'MOCK-000002' if 'MOCK-000002' in self.scenario.question and 'MOCK-000001' not in self.scenario.question else 'MOCK-000001'}
        if name == 'offer_quality':
            return {'offer_ids':self.controller.get('offer_ids',['MOCK-000001'])}
        if name == 'optimize_driver':
            return {'driver_ref':'D1'}
        if name == 'optimize_fleet':
            return {}
        if name == 'compare_plans':
            return {'plan_refs':plans[:2]}
        if name == 'request_approval':
            return {'action':'assign_plan','plan_refs':plans[:1],'summary':'Synthetic evaluation proposal'}
        return {'plan_ref':plans[0] if plans else 'PLAN-00000000'}


def offline_registry(settings: Settings, scenario: Scenario) -> ModelRegistry:
    from pathlib import Path
    from evals.schema import load_fixture
    offers = load_fixture(Path(__file__).parent,scenario.offer_fixture)['offers']
    controller: dict[str,Any] = {'offer_ids':[offer['id'] for offer in offers]}
    roles: list[Role] = ['dispatcher','freight_scout','fleet_compliance','route_planner','explainer']
    models = {role:EvalModel(role=role,scenario=scenario,controller=controller) for role in roles}
    # Pydantic copies dicts at construction: share only this test coordinator explicitly.
    for model in models.values():
        model.controller = controller
    policy = ModelPolicy.model_validate({role:{'model':f'fake:eval-{role}','maxTokens':100} for role in roles})
    return ModelRegistry(settings,policy,{f'fake:eval-{role}':lambda model=model:model for role,model in models.items()})
