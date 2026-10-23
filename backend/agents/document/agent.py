"""Build configured deep-agent specialists with explicit tools and policy."""

import os

from deepagents import (
    GeneralPurposeSubagentProfile,
    HarnessProfile,
    create_deep_agent,
    register_harness_profile,
)


def build_document_agent(model, tools, backend, middleware, prompt, name):
    # Keep all delegation explicit instead of adding an unconfigured general-purpose role.
    register_harness_profile(
        'openai:' + os.environ['LLM_MODEL_NAME'],
        HarnessProfile(
            general_purpose_subagent=GeneralPurposeSubagentProfile(enabled=False),
        ),
    )
    return create_deep_agent(
        model, tools=tools, backend=backend, middleware=middleware,
        system_prompt=prompt, name=name,
    )
