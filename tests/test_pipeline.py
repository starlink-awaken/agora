"""Tests for Pipeline — orchestration engine."""
import tempfile
from pathlib import Path

from agora.pipeline import Pipeline
from agora.registry import ServiceRegistry
from agora.router import Router


def _new_pipeline():
    r = ServiceRegistry(storage_path=str(Path(tempfile.mkdtemp()) / "test-svc.json"))
    return Pipeline(r, Router(r))


class TestPipelineBuiltins:
    def test_builtin_pipelines_loaded(self):
        pl = _new_pipeline()
        names = pl.list_pipelines()
        assert "match-derive" in names
        assert "research-derive" in names
        assert "derive-check" in names
        assert "full-pipeline" in names

    def test_get_pipeline_definition(self):
        pl = _new_pipeline()
        steps = pl.get_pipeline("derive-check")
        assert steps is not None
        assert len(steps) == 2
        assert steps[0]["tool"] == "ontoderive.derive"
        assert steps[1]["tool"] == "ontoderive.check"

    def test_pipeline_not_found(self):
        pl = _new_pipeline()
        assert pl.get_pipeline("nonexistent") is None


class TestPipelineCustom:
    def test_define_custom_pipeline(self):
        pl = _new_pipeline()
        pl.define("my-pipe", [
            {"tool": "toolforge.match", "args": {"goal": "{{goal}}"}},
        ])
        assert "my-pipe" in pl.list_pipelines()
        assert len(pl.get_pipeline("my-pipe")) == 1

    def test_load_save_definition(self):
        pl = _new_pipeline()
        pl.define("save-test", [{"tool": "test.tool"}])
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            pl.save_definition("save-test", f.name)
            loaded_name = pl.load_definition(f.name)
        assert loaded_name == "save-test"


class TestPipelineRender:
    def test_render_template_variables(self):
        pl = _new_pipeline()
        result = pl._render_args(
            {"goal": "{{goal}}", "context": "{{context}}", "fixed": "val"},
            {"goal": "分析市场", "context": "竞争"},
            {},
        )
        assert result["goal"] == "分析市场"
        assert result["context"] == "竞争"
        assert result["fixed"] == "val"

    def test_render_no_template(self):
        pl = _new_pipeline()
        result = pl._render_args({"x": "y"}, {}, {})
        assert result["x"] == "y"


class TestPipelineRun:
    def test_run_unknown_pipeline(self):
        pl = _new_pipeline()
        import asyncio
        result = asyncio.run(pl.run("unknown", {}))
        assert "error" in str(result).lower()

    def test_run_stream_unknown(self):
        pl = _new_pipeline()
        import asyncio

        async def _test():
            results = []
            async for step in pl.run_stream("unknown", {}):
                results.append(step)
            return results

        results = asyncio.run(_test())
        assert results[0]["status"] == "error"
