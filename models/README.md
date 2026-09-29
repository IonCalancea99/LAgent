# Model templates

The GPU server loads optional YOLO weights from the `current.pt` path in each
model family directory:

```text
models/
├── common/current.pt   # shared, class-agnostic detections
├── warlord/current.pt  # Warlord-specific detections
├── prophet/current.pt  # Prophet-specific detections
└── fishing/current.pt  # Fishing-specific detections
```

The `current.pt` files are intentionally not included in the repository. Add
compatible weights manually or create them with the training pipeline:

Before training, follow the complete [Label Studio labeling and export guide](../docs/site/training.html#label-studio-setup)
to create the required `recordings/<recording>/labels.json` file.

```bash
.venv/bin/python -m lagent.train train \
  --recording recordings/<recording> \
  --model-class common
```

Use `--model-class warlord`, `--model-class prophet`, or `--model-class fishing`
for the class-specific models. Deployment writes each result atomically to the
matching `current.pt` path and archives the previous model when one exists.