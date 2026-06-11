from __future__ import annotations

import argparse
from collections.abc import Sequence
import sys

from dramepulse_cli.registry import PIPELINES, PipelineCommand, get_pipeline


VERSION = "0.1.0"
ANSI_CYAN = "\033[36m"
ANSI_GREEN = "\033[32m"
ANSI_DIM = "\033[2m"
ANSI_RESET = "\033[0m"


def _banner(*, color: bool = True) -> str:
    c1 = ANSI_CYAN if color else ""
    c2 = ANSI_GREEN if color else ""
    dim = ANSI_DIM if color else ""
    reset = ANSI_RESET if color else ""
    return "\n".join(
        [
            f"{c2}DramePulse Pipeline CLI{reset}",
            f"{c1} ____                       ____        _          {reset}",
            f"{c1}|  _ \\ _ __ __ _ _ __ ___   |  _ \\ _   _| |___  ___ {reset}",
            f"{c1}| | | | '__/ _` | '_ ` _ \\  | |_) | | | | / __|/ _ \\{reset}",
            f"{c2}| |_| | | | (_| | | | | | | |  __/| |_| | \\__ \\  __/{reset}",
            f"{c2}|____/|_|  \\__,_|_| |_| |_| |_|    \\__,_|_|___/\\___|{reset}",
            f"{dim}Short-drama data pipelines for demos, review, and local iteration.{reset}",
        ]
    )


def _print_top_help(registry: Sequence[PipelineCommand]) -> None:
    print(_banner())
    print()
    print("Usage:")
    print("  dramepulse --version")
    print("  dramepulse --help")
    print("  dramepulse pipelines list")
    print("  dramepulse pipelines info <name>")
    print("  dramepulse pipelines run <name> [pipeline args...]")
    print()
    print("Pipeline commands:")
    print("  pipelines list          List runnable algorithm pipelines.")
    print("  pipelines info <name>   Show purpose, module, outputs, and example usage.")
    print("  pipelines run <name>    Forward remaining args to the selected pipeline runner.")
    print()
    print("Available pipelines:")
    for pipeline in registry:
        print(f"  {pipeline.name:<22} {pipeline.title} - {pipeline.summary}")
    print()
    print("Examples:")
    print("  dramepulse pipelines list")
    print("  dramepulse pipelines info highlight-commerce")
    print("  dramepulse pipelines run highlight-commerce --asset data/role-commerce-v2/highlight_commerce_case1.json")
    print()
    print("Tip: pass the selected pipeline's own flags after the pipeline name.")


def _print_pipelines_help() -> None:
    print("Usage:")
    print("  dramepulse pipelines list")
    print("  dramepulse pipelines info <name>")
    print("  dramepulse pipelines run <name> [pipeline args...]")
    print()
    print("Use `dramepulse pipelines info <name>` for examples and expected outputs.")


def _print_pipeline_list(registry: Sequence[PipelineCommand]) -> None:
    print("Available DramePulse pipelines:")
    for pipeline in registry:
        print(f"  {pipeline.name:<22} {pipeline.title}")
        print(f"  {'':<22} {pipeline.summary}")


def _print_pipeline_info(pipeline: PipelineCommand) -> None:
    print(f"{pipeline.title} ({pipeline.name})")
    print(f"Module: {pipeline.module}")
    print()
    print(pipeline.summary)
    print()
    print("Expected outputs:")
    for output in pipeline.outputs:
        print(f"  - {output}")
    print()
    print("Example:")
    args = " ".join(pipeline.example_args)
    print(f"  dramepulse pipelines run {pipeline.name} {args}")
    print()
    print("Runner help:")
    print(f"  dramepulse pipelines run {pipeline.name} --help")


def _unknown_pipeline(name: str, registry: Sequence[PipelineCommand]) -> int:
    print(f"Unknown pipeline: {name}", file=sys.stderr)
    print("Available pipelines:", file=sys.stderr)
    for pipeline in registry:
        print(f"  - {pipeline.name}", file=sys.stderr)
    return 2


def _run_pipeline(argv: list[str], registry: Sequence[PipelineCommand]) -> int:
    if not argv or argv[0] in {"-h", "--help"}:
        _print_pipelines_help()
        return 0

    action = argv[0]
    if action == "list":
        _print_pipeline_list(registry)
        return 0
    if action == "info":
        if len(argv) < 2:
            print("Missing pipeline name for `pipelines info`.", file=sys.stderr)
            return 2
        pipeline = get_pipeline(argv[1], registry)
        if pipeline is None:
            return _unknown_pipeline(argv[1], registry)
        _print_pipeline_info(pipeline)
        return 0
    if action == "run":
        if len(argv) < 2:
            print("Missing pipeline name for `pipelines run`.", file=sys.stderr)
            return 2
        pipeline = get_pipeline(argv[1], registry)
        if pipeline is None:
            return _unknown_pipeline(argv[1], registry)
        forwarded_args = argv[2:]
        if forwarded_args[:1] == ["--"]:
            forwarded_args = forwarded_args[1:]
        return pipeline.run(forwarded_args)

    print(f"Unknown pipelines action: {action}", file=sys.stderr)
    _print_pipelines_help()
    return 2


def main(argv: Sequence[str] | None = None, *, registry: Sequence[PipelineCommand] = PIPELINES) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in {"-h", "--help"}:
        _print_top_help(registry)
        return 0
    if args[0] == "--version":
        print(f"DramePulse {VERSION}")
        return 0
    if args[0] == "pipelines":
        return _run_pipeline(args[1:], registry)

    parser = argparse.ArgumentParser(add_help=False)
    parser.exit(2, f"Unknown command: {args[0]}\nRun `dramepulse --help` for usage.\n")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
