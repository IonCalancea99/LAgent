"""lagent.gpu_server - GPU inference and OCR processing."""

from lagent.gpu_server.server import GpuInferenceServer


def main() -> None:
	from lagent.gpu_server.__main__ import main as module_main

	module_main()


__all__ = ["GpuInferenceServer", "main"]
