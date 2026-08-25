"""lagent.gpu_server - GPU inference and OCR processing."""

from lagent.gpu_server.server import GpuInferenceServer


def main() -> None:
	GpuInferenceServer().serve()


__all__ = ["GpuInferenceServer", "main"]
