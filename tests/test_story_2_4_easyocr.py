import logging
import threading
import time

from lagent.common.transport import AgentTransport, make_endpoint
from lagent.gpu_server.server import GpuInferenceServer, OcrInference, YoloInference


class FakeReader:
    def __init__(self, responses):
        self.responses = responses
        self.crops = []

    def readtext(self, crop, **kwargs):
        self.crops.append(crop)
        return self.responses[crop]


def test_ocr_extracts_hp_mp_and_buff_values_from_named_rois():
    reader = FakeReader({
        "hp-crop": [([], "245/500", 0.99)],
        "mp-crop": [([], "60%", 0.98)],
        "buff-crop": [([], "12:34", 0.97)],
    })
    ocr = OcrInference(reader=reader, device="cpu")

    values = ocr.read({
        "health_bar": "hp-crop",
        "mana_bar": "mp-crop",
        "buff_1": "buff-crop",
    })

    assert values == {"hp": "245/500", "mp": "60%", "buff_1": "12:34"}
    assert reader.crops == ["hp-crop", "mp-crop", "buff-crop"]


def test_ocr_logs_selected_device(caplog):
    with caplog.at_level(logging.INFO):
        OcrInference(reader=FakeReader({}), device="cuda")

    assert "OCR device: cuda" in caplog.text


def test_server_forwards_roi_map_to_ocr():
    reader = FakeReader({"hp-crop": [([], "95%", 0.9)]})
    inference = YoloInference(models={}, ocr=OcrInference(reader=reader, device="cpu"))
    endpoint = make_endpoint()
    server = GpuInferenceServer(endpoint, inference=inference)
    thread = threading.Thread(target=server.serve, daemon=True)
    thread.start()
    time.sleep(0.03)
    client = AgentTransport("warlord", endpoint)
    client.connect()
    try:
        response = client.request_inference(b"frame", {"health_bar": "hp-crop"}, timeout=0.1)
        assert response.result.ocr_values == {"hp": "95%"}
    finally:
        client.close()
        server.stop()
        thread.join(timeout=1)
