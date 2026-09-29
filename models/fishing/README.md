# Fishing model

Place the Fishing-specific YOLO weights at `models/fishing/current.pt`.

This model is loaded when the Fishing agent requests inference (e.g. the
`tension_indicator` class used by the `WAITING` state in `profiles/fishing.yaml`).
It is optional while developing or running tests.

Before training, follow the complete [Label Studio labeling and export guide](../../docs/site/training.html#label-studio-setup).
For Fishing, label the full visible tension UI indicator as `tension_indicator`;
do not label the fixed `bite_indicator` ROI, health/mana text, or input events.

Train and deploy it with:

```bash
.venv/bin/python -m lagent.train train \
  --recording recordings/<recording> \
  --model-class fishing
```

Prelabel new recordings against the current Fishing model with:

```bash
.venv/bin/python -m lagent.train prelabel \
  --recording recordings/<recording> \
  --model-root models
```
