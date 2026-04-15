import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

# Paths
INPUT_CSV = "/home/chelo/antigravity/btc/bitcoin-onchain-framework/predictions/ensemble_predictions.csv"
OUTPUT_DIR = "."

Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)

def create_plot():
    if not Path(INPUT_CSV).exists():
        print(f"Error: {INPUT_CSV} not found.")
        return

    df = pd.read_csv(INPUT_CSV)
    df['timestamp_pred'] = pd.to_datetime(df['timestamp_pred'], format='mixed')
    
    # Filter for 1_block only to make the plot clean, or plot them in subplots
    df_1block = df[df['horizon_blocks'] == 1].dropna(subset=['actual_fee'])
    
    if len(df_1block) == 0:
        print("No validated predictions (actual_fee) available in 1_block to plot.")
        return

    plt.figure(figsize=(12, 6))
    
    # Plot true fee
    plt.plot(df_1block['timestamp_pred'], df_1block['actual_fee'], label='Actual Fee (sat/vB)', color='black', linewidth=2, marker='o')
    
    # Plot Ensemble Fee
    # Depending on the version of the file, check columns
    if 'predicted_fee_exact' in df_1block.columns:
        plt.plot(df_1block['timestamp_pred'], df_1block['predicted_fee_exact'], label='Ensemble Prediction', color='blue', linestyle='--')
    elif 'predicted_fee_sat_vb' in df_1block.columns:
        plt.plot(df_1block['timestamp_pred'], df_1block['predicted_fee_sat_vb'], label='Ensemble Prediction', color='blue', linestyle='--')
    
    if 'xgb_pred' in df_1block.columns:
        plt.plot(df_1block['timestamp_pred'], df_1block['xgb_pred'], label='XGBoost Prediction', color='red', alpha=0.7)
    elif 'xgb_fee_exact' in df_1block.columns:
        plt.plot(df_1block['timestamp_pred'], df_1block['xgb_fee_exact'], label='XGBoost Prediction', color='red', alpha=0.7)
        
    if 'lgb_pred' in df_1block.columns:
        plt.plot(df_1block['timestamp_pred'], df_1block['lgb_pred'], label='LightGBM Prediction', color='green', alpha=0.7)
    elif 'lgb_fee_exact' in df_1block.columns:
        plt.plot(df_1block['timestamp_pred'], df_1block['lgb_fee_exact'], label='LightGBM Prediction', color='green', alpha=0.7)
        
    plt.title("Model Predictions vs Actual Fee (1 Block Horizon)")
    plt.xlabel("Time")
    plt.ylabel("Fee (sat/vB)")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.xticks(rotation=45)
    plt.tight_layout()
    
    output_path = f"{OUTPUT_DIR}/predictions_vs_actual.png"
    plt.savefig(output_path)
    print(f"Plot saved to {output_path}")

if __name__ == '__main__':
    create_plot()
