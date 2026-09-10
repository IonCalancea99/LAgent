# Common model

Place the shared YOLO weights at `models/common/current.pt`.

This model contains detections used by every agent. It is loaded at GPU-server
startup and is optional while developing or running tests.