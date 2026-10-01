"""An operator-installed numerical method must work through the actual MCP server."""
import asyncio
import json
import os
import sys

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from eal.runtime import load_method_registry
from _runtime_cases import RMS_SOURCE, write_case


def test_host_factory_is_explicit_and_returns_a_checked_registry():
    default = load_method_registry()
    extended = load_method_registry('eal.extensions:example_registry')
    assert default.get('engineering/rms/1') is None
    assert extended.get('engineering/rms/1') is not None
    assert default.fingerprint != extended.fingerprint
    for value in ('eal.extensions', 'eal.extensions:__dict__', 'eal.extensions:missing', '../untrusted:run'):
        with pytest.raises(ValueError):
            load_method_registry(value)


def test_registered_extension_real_mcp_collection_format_reason_and_explain(tmp_path):
    _, _, registry = write_case(tmp_path, 'rms')
    source = RMS_SOURCE
    context = {'site': 'bench'}
    parameters = StdioServerParameters(command=sys.executable, args=[
        '-m', 'eal.server', '--workspace', str(tmp_path),
        '--registry', str(registry),
        '--methods', 'eal.extensions:example_registry',
    ], env=dict(os.environ))

    async def exercise():
        async with stdio_client(parameters) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                async def call(name, args):
                    response = await session.call_tool(name, args)
                    assert not response.is_error, response.content
                    return response.structured_content
                described = await call('eal_describe', {})
                assert 'engineering/rms/1' in described['typed_bindings']['methods']
                fingerprint = described['method_registry_fingerprint']
                formatted = await call('eal_format', {'source': source})
                source_to_assess = formatted['source']
                valid = await call('eal_validate', {'source': source_to_assess})
                assert valid['valid']
                assert valid['method_registry_fingerprint'] == fingerprint
                collected = await call('eal_collect', {'source': source_to_assess, 'context': context})
                assert collected['records']['series']['status'] == 'ok'
                assessed = await call('eal_reason', {'source': source_to_assess, 'context': context,
                    'collection_id': collected['collection_id'], 'now': '2026-09-23T12:00:00Z'})
                assert assessed['claims']['bounded_rms']['status'] == 'supported'
                computation = assessed['arguments']['sampled_rms']['reasoning_result']
                assert computation['details']['rms'] == pytest.approx((12.5)**0.5)
                assert computation['binding']['output_unit'] == 'kPa'
                assert assessed['method_registry_fingerprint'] == fingerprint
                explained = await call('eal_explain', {'assessment_id': assessed['assessment_id'], 'claim': 'bounded_rms'})
                assert explained['result']['status'] == 'supported'
                assert explained['method_registry_fingerprint'] == fingerprint
                assert explained['result']['prose_verified'] is False
    asyncio.run(exercise())
