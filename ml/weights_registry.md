# Weights Registry

Track the production artifact version for each model here. Large weight files
must be stored through Git LFS or release assets, not committed to the repo.

To download release assets into the ignored model directories:

```powershell
python scripts/fetch_model_weights.py --tag v0.1.0 `
	--asset pothole_crack=production.pt `
	--asset hawkers=production.pt `
	--asset fallen_trees=production.pt
```