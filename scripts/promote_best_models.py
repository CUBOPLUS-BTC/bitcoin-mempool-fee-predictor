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

        # Copy XGBoost
        if x_res:
            xgb_src = get_latest_model_file(models_dir, 'xgb', horizon, 'json')
            if xgb_src:
                xgb_dst = production_dir / f"xgb_fee_{horizon}.json"
                shutil.copy2(xgb_src, xgb_dst)
                print(f"    Copied {Path(xgb_src).name} -> {xgb_dst.name}")

        # Copy LightGBM
        if l_res:
            lgb_src = get_latest_model_file(models_dir, 'lgbm', horizon, 'txt')
            if lgb_src:
                lgb_dst = production_dir / f"lgbm_fee_{horizon}.txt"
                shutil.copy2(lgb_src, lgb_dst)
                print(f"    Copied {Path(lgb_src).name} -> {lgb_dst.name}")
                
        # Save metadata for both
        meta_file = production_dir / f"meta_fee_{horizon}.json"
        meta = {
            'horizon': horizon,
            'xgb_metrics': x_res,
            'lgb_metrics': l_res
        }
        with open(meta_file, 'w') as mf:
            json.dump(meta, mf, indent=2)

if __name__ == '__main__':
    promote_models()
