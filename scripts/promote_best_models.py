import json
import os
import glob
import shutil
from pathlib import Path

def find_latest_results(logs_dir):
    files = glob.glob(os.path.join(logs_dir, 'retrain_results_*.json'))
    if not files:
        return None
    # returning the one with the latest modification time or name
    files.sort()
    return files[-1]

def get_latest_model_file(models_dir, prefix, horizon_label, extension):
    pattern = f"{models_dir}/{prefix}_fee_{horizon_label}_latest.{extension}"
    files = glob.glob(pattern)
    return files[0] if files else None

def promote_models():
    base_dir = Path(__file__).resolve().parent.parent
    logs_dir = base_dir / 'logs'
    models_dir = base_dir / 'models'
    production_dir = models_dir / 'production'

    production_dir.mkdir(parents=True, exist_ok=True)

    latest_results_file = find_latest_results(logs_dir)
    if not latest_results_file:
        print("No retraining results found.")
        return

    with open(latest_results_file, 'r') as f:
        results = json.load(f)

    xgb_res = results.get('xgb_results', {})
    lgb_res = results.get('lgb_results', {})

    horizons = set(list(xgb_res.keys()) + list(lgb_res.keys()))

    print(f"Promoting models from: {Path(latest_results_file).name}")

    for horizon in horizons:
        x_res = xgb_res.get(horizon)
        l_res = lgb_res.get(horizon)

        best_model = None
        best_type = None

        if x_res and l_res:
            # We want highest inclusion, then lowest MAE
            x_score = (x_res.get('block_inclusion_accuracy', 0), -x_res.get('mae', float('inf')))
            l_score = (l_res.get('block_inclusion_accuracy', 0), -l_res.get('mae', float('inf')))

            if x_score >= l_score:
                best_type = 'xgb'
            else:
                best_type = 'lgbm'
        elif x_res:
            best_type = 'xgb'
        elif l_res:
            best_type = 'lgbm'
        else:
            print(f"  [{horizon}] No models trained.")
            continue

        print(f"  [{horizon}] Winner: {best_type.upper()}")
        
        # Copy to production
        ext = 'json' if best_type == 'xgb' else 'txt'
        src_file = get_latest_model_file(models_dir, best_type, horizon, ext)
        
        if src_file:
            dst_file = production_dir / f"best_fee_{horizon}.{ext}"
            shutil.copy2(src_file, dst_file)
            print(f"    Copied {Path(src_file).name} -> {dst_file.name}")
            
            # Also save metadata so inference can know which model driver to use
            meta_file = production_dir / f"meta_fee_{horizon}.json"
            meta = {
                'driver': 'xgboost' if best_type == 'xgb' else 'lightgbm',
                'horizon': horizon,
                'metrics': x_res if best_type == 'xgb' else l_res
            }
            with open(meta_file, 'w') as mf:
                json.dump(meta, mf, indent=2)
        else:
            print(f"    Source model file not found for {best_type} {horizon}")

if __name__ == '__main__':
    promote_models()
