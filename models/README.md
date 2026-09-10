# Model templates

The GPU server loads optional YOLO weights from the `current.pt` path in each
model family directory:

```text
models/
├── common/current.pt   # shared, class-agnostic detections
├── warlord/current.pt  # Warlord-specific detections
└── prophet/current.pt  # Prophet-specific detections
```

The `current.pt` files are intentionally not included in the repository. Add
compatible weights manually or create them with the training pipeline:

```bash
.venv/bin/python -m lagent.train train \
  --recording recordings/<recording> \
  --model-class common
```

Use `--model-class warlord` or `--model-class prophet` for the class-specific
models. Deployment writes each result atomically to the matching `current.pt`
path and archives the previous model when one exists.