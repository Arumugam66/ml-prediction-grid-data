import ast
import json
import logging
import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("update_grid_data")

def parse_metric(val):
    if isinstance(val, dict):
        return val
    if not val or not isinstance(val, str):
        return {}
    try:
        return json.loads(val)
    except Exception:
        try:
            return ast.literal_eval(val)
        except Exception:
            return {}

def main():
    logger.info("Loading grid_data.parquet.bak...")
    df = pd.read_parquet("grid_data.parquet.bak")
    logger.info(f"Original shape: {df.shape}")

    # Ensure received_on is datetime
    df["received_on"] = pd.to_datetime(df["received_on"])
    df["created_at"] = pd.to_datetime(df["created_at"])
    df["site_code"] = df["site_code"].astype(str).str.strip()
    df["slave_id"] = df["slave_id"].astype(str).str.strip()

    # Sort data
    df = df.sort_values(["site_code", "received_on"]).reset_index(drop=True)

    max_id = int(df["id"].max())

    processed_site_dfs = []

    for site_code in ["RAMS001", "RAMS002", "EMS000182"]:
        site_df = df[df["site_code"] == site_code].copy().reset_index(drop=True)
        logger.info(f"Processing site {site_code}: existing records = {len(site_df)}, min_date = {site_df['received_on'].min()}, max_date = {site_df['received_on'].max()}")
        
        sample_row = site_df.iloc[-1]
        slave_id = sample_row["slave_id"]
        site_id_val = sample_row["site_id"]

        # Parse metrics for existing rows and reconstruct cumulative EBKwh / DGKwh smoothly
        metrics_list = [parse_metric(m) for m in site_df["metric_json"]]
        
        # Reconstruct smooth cumulative meter series based on TotalKw
        eb_cumsum = 10000.0 if site_code == "RAMS001" else (20000.0 if site_code == "RAMS002" else 5000.0)
        dg_cumsum = 500.0 if site_code == "RAMS001" else (1000.0 if site_code == "RAMS002" else 200.0)
        eb_run = 100.0
        dg_run = 20.0

        updated_json_strings = []

        np.random.seed(42 + hash(site_code) % 1000)

        for i, row in site_df.iterrows():
            m = metrics_list[i]
            t = row["received_on"]
            
            raw_kw = m.get("TotalKw", None)
            try:
                total_kw = float(raw_kw) if raw_kw is not None else 15.0
            except (ValueError, TypeError):
                total_kw = 15.0

            if total_kw <= 0 or np.isnan(total_kw) or total_kw > 150.0:
                hour_factor = 1.0 + 0.3 * np.sin(2 * np.pi * t.hour / 24)
                total_kw = round(float(np.random.normal(18.0, 4.0) * hour_factor), 3)
                total_kw = max(2.0, total_kw)

            # Check if outage
            dg_run_val = m.get("DGRunhour", 0.0)
            try:
                dg_run_float = float(dg_run_val)
            except (ValueError, TypeError):
                dg_run_float = 0.0

            prev_dg_run = 0.0
            if i > 0:
                try:
                    prev_dg_run = float(metrics_list[i-1].get("DGRunhour", 0.0))
                except (ValueError, TypeError):
                    prev_dg_run = 0.0

            is_outage = (dg_run_float > prev_dg_run and dg_run_float > 0.0)

            if is_outage:
                dg_inc = total_kw * 0.5
                eb_inc = 0.0
                dg_run += 0.5
            else:
                eb_inc = total_kw * 0.5
                dg_inc = 0.0
                eb_run += 0.5

            eb_cumsum += eb_inc
            dg_cumsum += dg_inc

            m["EBKwh"] = round(eb_cumsum, 3)
            m["DGKwh"] = round(dg_cumsum, 3)
            m["EBRunhour"] = round(eb_run, 2)
            m["DGRunhour"] = round(dg_run, 2)
            m["slave_ID"] = slave_id

            # Ensure numeric fields are cast properly
            m["TotalKw"] = float(total_kw)
            try:
                m["TotalPF"] = float(m.get("TotalPF", 0.95))
            except (ValueError, TypeError):
                m["TotalPF"] = 0.95

            m["TotalKVA"] = float(m["TotalKw"] / max(0.1, m["TotalPF"]))
            
            try:
                m["AverageCurrent"] = float(m.get("AverageCurrent", 10.0))
            except (ValueError, TypeError):
                m["AverageCurrent"] = 10.0

            try:
                m["AveragePhasevoltage"] = float(m.get("AveragePhasevoltage", 230.0))
            except (ValueError, TypeError):
                m["AveragePhasevoltage"] = 230.0

            try:
                m["AverageLinevoltage"] = float(m.get("AverageLinevoltage", 400.0))
            except (ValueError, TypeError):
                m["AverageLinevoltage"] = 400.0

            try:
                m["Frequency"] = float(m.get("Frequency", 50.0))
            except (ValueError, TypeError):
                m["Frequency"] = 50.0

            updated_json_strings.append(json.dumps(m))

        site_df["metric_json"] = updated_json_strings

        # Check for date extension up to 2026-08-28
        last_time = site_df["received_on"].max()
        target_time = pd.Timestamp("2026-08-28 00:00:00")

        if last_time < target_time:
            logger.info(f"Extending time series for {site_code} from {last_time} to {target_time}...")
            future_times = pd.date_range(start=last_time + pd.Timedelta(minutes=30), end=target_time, freq="30min")

            new_rows = []
            for t in future_times:
                max_id += 1
                is_outage = np.random.rand() < 0.05
                hour_factor = 1.0 + 0.3 * np.sin(2 * np.pi * t.hour / 24)
                total_kw = round(float(np.random.normal(18.0, 4.0) * hour_factor), 3)
                total_kw = max(2.0, total_kw)
                
                total_pf = round(float(np.clip(np.random.normal(0.95, 0.03), 0.85, 0.99)), 3)
                total_kva = round(total_kw / total_pf, 3)
                avg_volt = round(float(np.random.normal(230.0, 5.0)), 2)
                avg_curr = round(total_kw * 1000 / (3 * avg_volt * total_pf), 3)
                freq = round(float(np.random.normal(50.0, 0.1)), 2)

                if is_outage:
                    dg_inc = total_kw * 0.5
                    eb_inc = 0.0
                    dg_run += 0.5
                else:
                    eb_inc = total_kw * 0.5
                    dg_inc = 0.0
                    eb_run += 0.5

                eb_cumsum += eb_inc
                dg_cumsum += dg_inc

                metric_dict = {
                    "EBKwh": round(eb_cumsum, 3),
                    "DGKwh": round(dg_cumsum, 3),
                    "TotalKw": total_kw,
                    "TotalPF": total_pf,
                    "TotalKVA": total_kva,
                    "AverageCurrent": avg_curr,
                    "AveragePhasevoltage": avg_volt,
                    "AverageLinevoltage": round(avg_volt * 1.732, 2),
                    "Frequency": freq,
                    "EBRunhour": round(eb_run, 2),
                    "DGRunhour": round(dg_run, 2),
                    "R_Kw": round(total_kw / 3, 3),
                    "Y_Kw": round(total_kw / 3, 3),
                    "B_Kw": round(total_kw / 3, 3),
                    "R_PF": total_pf,
                    "Y_PF": total_pf,
                    "B_PF": total_pf,
                    "R_KVA": round(total_kva / 3, 3),
                    "Y_KVA": round(total_kva / 3, 3),
                    "B_KVA": round(total_kva / 3, 3),
                    "slave_ID": slave_id
                }

                new_rows.append({
                    "id": max_id,
                    "site_id": site_id_val,
                    "metric_json": json.dumps(metric_dict),
                    "received_on": t,
                    "created_at": t + pd.Timedelta(seconds=4),
                    "slave_id": slave_id,
                    "site_code": site_code
                })

            if new_rows:
                ext_df = pd.DataFrame(new_rows)
                site_df = pd.concat([site_df, ext_df], ignore_index=True)

        processed_site_dfs.append(site_df)

    final_df = pd.concat(processed_site_dfs, ignore_index=True)
    final_df = final_df.sort_values(["site_code", "received_on"]).reset_index(drop=True)

    logger.info("Saving updated clean dataset to grid_data.parquet...")
    final_df.to_parquet("grid_data.parquet", index=False)

    logger.info("Checking final site breakdown in grid_data.parquet:")
    print(final_df.groupby("site_code").agg({"id": "count", "received_on": ["min", "max"]}))
    logger.info("Done!")

if __name__ == "__main__":
    main()
