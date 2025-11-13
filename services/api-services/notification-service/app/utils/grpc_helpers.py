import importlib
import os
import sys
import tempfile
from pathlib import Path
from grpc_tools import protoc


def compile_proto(proto_path: str, out_dir: str) -> None:
    """Compile a .proto file into Python modules under out_dir.

    proto_path: absolute path to the .proto file
    out_dir: directory where generated files will be placed
    """
    proto_dir = str(Path(proto_path).parent)
    args = [
        "protoc",
        f"-I{proto_dir}",
        f"--python_out={out_dir}",
        f"--grpc_python_out={out_dir}",
        proto_path,
    ]
    # protoc.main expects sys.argv-style list
    protoc.main(args)


def import_generated_module(package_dir: str, module_name: str):
    """Import a generated module by ensuring package_dir is on sys.path and importing module_name."""
    if package_dir not in sys.path:
        sys.path.insert(0, package_dir)
    return importlib.import_module(module_name)


def load_notifier_proto_runtime(proto_path: str):
    """Compile notifier.proto and import the generated _pb2 and _pb2_grpc modules.

    Returns (pb2_module, pb2_grpc_module)
    """
    # create a stable cache directory under the project so repeated calls reuse generated files
    project_root = Path(__file__).resolve().parents[3]
    gen_dir = project_root / "app" / "utils" / "proto_generated" / "notifier"
    gen_dir.mkdir(parents=True, exist_ok=True)

    proto_path = Path(proto_path)
    # Only compile if generated files are missing or proto is newer
    pb2 = gen_dir / (proto_path.stem + "_pb2.py")
    pb2_grpc = gen_dir / (proto_path.stem + "_pb2_grpc.py")
    if not pb2.exists() or not pb2_grpc.exists() or pb2.stat().st_mtime < proto_path.stat().st_mtime:
        compile_proto(str(proto_path), str(gen_dir))

    # Import modules
    module_base = f"app.utils.proto_generated.notifier.{proto_path.stem}"
    pb2_module = import_generated_module(str(project_root), module_base + "_pb2")
    pb2_grpc_module = import_generated_module(str(project_root), module_base + "_pb2_grpc")
    return pb2_module, pb2_grpc_module
