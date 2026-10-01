"""Configured host budgets apply to raw grounded graph entry points too."""
import asyncio
import json
import subprocess
import sys
import pytest
from eal.limits import ExecutionLimits
from eal.runtime import ReasoningService
from eal.server import create_server


def test_cli_grounded_uses_operator_budget_file(tmp_path):
    (tmp_path/'limits.toml').write_text('[limits]\ndeclarations=1\n')
    (tmp_path/'graph.json').write_text(json.dumps({'arguments':['a','b'],'attacks':[]}))
    result = subprocess.run([sys.executable,'-m','eal.cli','--workspace',str(tmp_path),'--limits',str(tmp_path/'limits.toml'),'grounded','graph.json'],capture_output=True,text=True)
    assert result.returncode != 0
    assert 'arguments exceeds the limit of 1' in result.stdout + result.stderr


def test_mcp_grounded_uses_service_budget(tmp_path):
    server = create_server(ReasoningService(tmp_path,limits=ExecutionLimits(declarations=1)))
    async def check():
        with pytest.raises(Exception, match='arguments exceeds the limit of 1'):
            await server.call_tool('eal_grounded', {'arguments':['a','b'],'attacks':[]})
    asyncio.run(check())
