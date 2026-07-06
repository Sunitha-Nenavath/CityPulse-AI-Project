import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLASSIFIED_DATA_PATH = os.path.join(BASE_DIR, "data", "classified_complaints.csv")

class AnalyticsEngine:
    def __init__(self):
        self.use_bigquery = False
        self.client = None
        self.project_id = os.getenv("BIGQUERY_PROJECT")
        self.dataset_id = os.getenv("BIGQUERY_DATASET", "citypulse_dataset")
        self.table_id = os.getenv("BIGQUERY_TABLE", "complaints")
        
        # Check for GCP BigQuery setup
        use_bq_env = os.getenv("USE_BIGQUERY", "false").lower() == "true"
        cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if use_bq_env and cred_path and os.path.exists(cred_path) and self.project_id:
            try:
                from google.cloud import bigquery
                self.client = bigquery.Client()
                self.use_bigquery = True
                print(f"Connected to BigQuery. Using project: {self.project_id}")
            except Exception as e:
                print(f"Failed to connect to BigQuery: {e}. Falling back to Pandas/CSV.")
        else:
            print("BigQuery integration disabled or credentials missing. Using Pandas/CSV local database.")
            
    def _run_query_pandas(self, query_name):
        """
        Executes local pandas calculations equivalent to the BigQuery SQL queries.
        """
        df = pd.read_csv(CLASSIFIED_DATA_PATH)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df["complaint_week"] = df["timestamp"].dt.to_period("W").dt.start_time
        
        if query_name == "weekly_ward_complaints":
            # Count complaints per ward per week
            agg = df.groupby(["ward_name", "complaint_week"]).size().reset_index(name="complaint_count")
            return agg.sort_values(by=["complaint_week", "complaint_count"], ascending=[False, False])
            
        elif query_name == "category_trends":
            # Count complaints per category per week
            agg = df.groupby(["category_classified", "complaint_week"]).size().reset_index(name="complaint_count")
            agg = agg.rename(columns={"category_classified": "category"})
            return agg.sort_values(by=["complaint_week", "complaint_count"], ascending=[False, False])
            
        elif query_name == "wow_spikes":
            # WoW Spike Detection per ward and category
            # Group by ward, category, and week
            weekly = df.groupby(["ward_name", "category_classified", "complaint_week"]).size().reset_index(name="current_week_count")
            weekly = weekly.rename(columns={"category_classified": "category"})
            
            # Sort to apply lag
            weekly = weekly.sort_values(by=["ward_name", "category", "complaint_week"])
            
            # Compute lag
            weekly["prev_week_count"] = weekly.groupby(["ward_name", "category"])["current_week_count"].shift(1).fillna(0).astype(int)
            
            # Compute growth percentage
            def calc_growth(row):
                curr = row["current_week_count"]
                prev = row["prev_week_count"]
                if prev == 0 and curr > 0:
                    return 100.0
                elif prev == 0 and curr == 0:
                    return 0.0
                else:
                    return round(((curr - prev) / prev) * 100.0, 2)
                    
            weekly["wow_growth_percentage"] = weekly.apply(calc_growth, axis=1)
            return weekly.sort_values(by=["complaint_week", "wow_growth_percentage"], ascending=[False, False])
            
        return None

    def execute_query(self, query_name, raw_sql=None):
        """
        Executes query on BigQuery if active, otherwise runs local Pandas equivalents.
        """
        if self.use_bigquery and raw_sql:
            # Replace placeholder variables in SQL
            full_table = f"{self.project_id}.{self.dataset_id}.{self.table_id}"
            sql = raw_sql.replace("`YOUR_PROJECT.YOUR_DATASET.YOUR_TABLE`", f"`{full_table}`")
            try:
                query_job = self.client.query(sql)
                return query_job.to_dataframe()
            except Exception as e:
                print(f"BigQuery execution failed: {e}. Falling back to Pandas local execution.")
                
        return self._run_query_pandas(query_name)
        
    def get_weekly_complaints_per_ward(self):
        sql = """
        SELECT
          ward_name,
          DATE_TRUNC(DATE(timestamp), WEEK) AS complaint_week,
          COUNT(complaint_id) AS complaint_count
        FROM
          `YOUR_PROJECT.YOUR_DATASET.YOUR_TABLE`
        GROUP BY
          ward_name,
          complaint_week
        ORDER BY
          complaint_week DESC,
          complaint_count DESC;
        """
        return self.execute_query("weekly_ward_complaints", sql)
        
    def get_category_trends(self):
        sql = """
        SELECT
          category_classified AS category,
          DATE_TRUNC(DATE(timestamp), WEEK) AS complaint_week,
          COUNT(complaint_id) AS complaint_count
        FROM
          `YOUR_PROJECT.YOUR_DATASET.YOUR_TABLE`
        GROUP BY
          category,
          complaint_week
        ORDER BY
          complaint_week DESC,
          complaint_count DESC;
        """
        return self.execute_query("category_trends", sql)
        
    def get_wow_spikes(self):
        sql = """
        WITH WeeklyComplaints AS (
          SELECT
            ward_name,
            category_classified AS category,
            DATE_TRUNC(DATE(timestamp), WEEK) AS complaint_week,
            COUNT(complaint_id) AS current_week_count
          FROM
            `YOUR_PROJECT.YOUR_DATASET.YOUR_TABLE`
          GROUP BY
            ward_name,
            category,
            complaint_week
        ),
        WeeklyLags AS (
          SELECT
            ward_name,
            category,
            complaint_week,
            current_week_count,
            LAG(current_week_count, 1) OVER (
              PARTITION BY ward_name, category
              ORDER BY complaint_week
            ) AS prev_week_count
          FROM
            WeeklyComplaints
        )
        SELECT
          ward_name,
          category,
          complaint_week,
          current_week_count,
          COALESCE(prev_week_count, 0) AS prev_week_count,
          CASE
            WHEN COALESCE(prev_week_count, 0) = 0 AND current_week_count > 0 THEN 100.0
            WHEN COALESCE(prev_week_count, 0) = 0 AND current_week_count = 0 THEN 0.0
            ELSE ROUND(((current_week_count - prev_week_count) / prev_week_count) * 100.0, 2)
          END AS wow_growth_percentage
        FROM
          WeeklyLags
        ORDER BY
          complaint_week DESC,
          wow_growth_percentage DESC;
        """
        return self.execute_query("wow_spikes", sql)
        
    def get_ward_rankings(self):
        """
        Computes the weekly urgency_score per ward for the most recent week in the dataset.
        Rank wards from most to least urgent.
        Flags ward/category combos with WoW increase > 50% as anomalies.
        """
        df = pd.read_csv(CLASSIFIED_DATA_PATH)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df["complaint_week"] = df["timestamp"].dt.to_period("W").dt.start_time
        
        # Get the most recent week
        latest_week = df["complaint_week"].max()
        prev_week = latest_week - timedelta(weeks=1)
        
        # 1. Slice current week and previous week data
        df_latest = df[df["complaint_week"] == latest_week]
        df_prev = df[df["complaint_week"] == prev_week]
        
        # 2. Get open complaint counts per ward (latest week)
        open_counts = df_latest[df_latest["status"] == "open"].groupby("ward_name").size().to_dict()
        
        # 3. Get average urgency score per ward (latest week)
        avg_urgency = df_latest.groupby("ward_name")["urgency_score"].mean().to_dict()
        
        # 4. Get top category per ward (latest week)
        top_categories = {}
        for ward in df["ward_name"].unique():
            ward_df = df_latest[df_latest["ward_name"] == ward]
            if len(ward_df) > 0:
                top_cat = ward_df["category_classified"].mode()
                top_categories[ward] = top_cat.iloc[0] if len(top_cat) > 0 else "N/A"
            else:
                top_categories[ward] = "N/A"
                
        # 5. Compute WoW growth of total complaints per ward
        latest_ward_counts = df_latest.groupby("ward_name").size().to_dict()
        prev_ward_counts = df_prev.groupby("ward_name").size().to_dict()
        
        ward_wow_growth = {}
        for ward in df["ward_name"].unique():
            curr = latest_ward_counts.get(ward, 0)
            prev = prev_ward_counts.get(ward, 0)
            if prev == 0:
                ward_wow_growth[ward] = 100.0 if curr > 0 else 0.0
            else:
                ward_wow_growth[ward] = ((curr - prev) / prev) * 100.0
                
        # 6. Flag anomalies (any ward-category with > 50% increase)
        # Fetch WoW spikes
        wow_spikes_df = self.get_wow_spikes()
        # Filter for latest week and growth > 50%
        latest_spikes = wow_spikes_df[
            (pd.to_datetime(wow_spikes_df["complaint_week"]) == latest_week) &
            (wow_spikes_df["wow_growth_percentage"] > 50.0)
        ]
        
        anomaly_flags = {}
        for ward in df["ward_name"].unique():
            ward_anom = latest_spikes[latest_spikes["ward_name"] == ward]
            if len(ward_anom) > 0:
                # Store which categories are spiking and their percentages
                spikes_list = [f"{row['category']} (+{row['wow_growth_percentage']:.0f}%)" for _, row in ward_anom.iterrows()]
                anomaly_flags[ward] = ", ".join(spikes_list)
            else:
                anomaly_flags[ward] = ""
                
        # 7. Calculate Urgency Score
        # Formula: (open_complaints_count * 0.4) + (avg_urgency * 10) + (max(0.0, ward_wow_growth) * 0.2)
        rankings = []
        for ward in df["ward_name"].unique():
            op_cnt = open_counts.get(ward, 0)
            avg_urg = avg_urgency.get(ward, 0.0)
            wow_growth = ward_wow_growth.get(ward, 0.0)
            
            # Compute score
            score = (op_cnt * 0.4) + (avg_urg * 10) + (max(0.0, wow_growth) * 0.2)
            
            # Format outputs
            rankings.append({
                "ward_name": ward,
                "urgency_score": round(score, 2),
                "open_complaints": op_cnt,
                "average_urgency": round(avg_urg, 2),
                "wow_spike_percent": round(wow_growth, 2),
                "top_category": top_categories.get(ward, "N/A"),
                "anomaly_spike": anomaly_flags.get(ward, "None")
            })
            
        rankings_df = pd.DataFrame(rankings)
        return rankings_df.sort_values(by="urgency_score", ascending=False).reset_index(drop=True)

if __name__ == "__main__":
    engine = AnalyticsEngine()
    print("Testing Analytics calculations:")
    rankings = engine.get_ward_rankings()
    print("\nWard Urgency Rankings:")
    print(rankings.to_string(index=False))
    
    print("\nTesting spikes query (top 5 latest spikes):")
    spikes = engine.get_wow_spikes()
    print(spikes.head(5).to_string(index=False))
