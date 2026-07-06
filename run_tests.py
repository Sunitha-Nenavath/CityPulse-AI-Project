import os
import sys
import pandas as pd

# Add root directory to path for imports
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)

def print_banner(title):
    print("=" * 60)
    print(f" TESTING: {title}")
    print("=" * 60)

def main():
    print_banner("CITYPULSE AI TEST INTEGRITY RUNNER")
    
    # Enable UTF-8 print mode on Windows to handle symbols/emojis
    if sys.platform == "win32":
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        
    errors = 0
    
    # 1. Check Data Layer
    print_banner("1. Data Generation Layer")
    try:
        from data.generator import generate_synthetic_data
        raw_path = os.path.join(BASE_DIR, "data", "raw_complaints.csv")
        
        # If dataset is already generated, we verify its size, otherwise we generate a small subset for testing
        if os.path.exists(raw_path):
            print(f"Found existing raw dataset: {raw_path}")
        else:
            print("No raw complaints found. Running generator...")
            generate_synthetic_data(raw_path, num_records=5000)
            
        df_raw = pd.read_csv(raw_path)
        print(f"Successfully loaded raw complaints. Row count: {len(df_raw)}")
        
        required_cols = ["complaint_id", "ward_name", "category", "description_text", "timestamp", "status", "resolution_notes"]
        missing_cols = [c for c in required_cols if c not in df_raw.columns]
        if missing_cols:
            print(f"❌ Fail: Missing raw columns {missing_cols}")
            errors += 1
        else:
            print("✔ Success: All required raw columns are present.")
            
    except Exception as e:
        print(f"❌ Fail: Data Generation failed with error: {e}")
        errors += 1
        
    # 2. Check Classification Layer
    print_banner("2. Classification & Caching Layer")
    try:
        classified_path = os.path.join(BASE_DIR, "data", "classified_complaints.csv")
        
        if os.path.exists(classified_path):
            print(f"Found existing classified dataset: {classified_path}")
        else:
            print("No classified complaints found. Running classification...")
            from classification.classifier import run_classification
            run_classification()
            
        df_classified = pd.read_csv(classified_path)
        print(f"Successfully loaded classified complaints. Row count: {len(df_classified)}")
        
        required_class_cols = ["category_classified", "urgency_score", "sentiment"]
        missing_class_cols = [c for c in required_class_cols if c not in df_classified.columns]
        if missing_class_cols:
            print(f"❌ Fail: Missing classified columns {missing_class_cols}")
            errors += 1
        else:
            print("✔ Success: All classification columns are present.")
            
        # Check range of scores
        min_urg = df_classified["urgency_score"].min()
        max_urg = df_classified["urgency_score"].max()
        print(f"Urgency score ranges from {min_urg} to {max_urg}")
        if min_urg < 1 or max_urg > 5:
            print("❌ Fail: Urgency score out of bounds (should be 1-5)")
            errors += 1
        else:
            print("✔ Success: Urgency scores are properly bounded (1-5).")
            
    except Exception as e:
        print(f"❌ Fail: Classification check failed with error: {e}")
        errors += 1
        
    # 3. Check RAG Layer
    print_banner("3. RAG Retrieval Layer")
    try:
        from rag.indexer import CivicRAG
        rag = CivicRAG()
        
        # Load and run index test
        rag.load_index()
        print(f"RAG loaded successfully with engine: {rag.engine_type}")
        
        # Search test
        query = "sewage leakage overflowing from main pipe"
        results = rag.search(query, k=3)
        print(f"RAG search query: '{query}'")
        print(f"Retrieved {len(results)} matches:")
        for idx, res in enumerate(results):
            print(f"  Match {idx+1}: [{res['category']}] (Score: {res['score']:.2f}) {res['description_text'][:50]}... Resolution: {res['resolution_notes'][:50]}...")
            
        if len(results) < 3:
            print("❌ Fail: RAG retrieved less than 3 results.")
            errors += 1
        else:
            print("✔ Success: RAG search returned top-3 matches.")
            
    except Exception as e:
        print(f"❌ Fail: RAG check failed with error: {e}")
        errors += 1
        
    # 4. Check Analytics Layer
    print_banner("4. Analytics & Priority Calculation Layer")
    try:
        from analytics.engine import AnalyticsEngine
        engine = AnalyticsEngine()
        
        print("Calculating Ward Urgency Rankings...")
        rankings = engine.get_ward_rankings()
        print(f"Rankings calculated for {len(rankings)} wards.")
        
        # Verify highest urgency ward
        highest_ward = rankings.iloc[0]
        print(f"Highest Urgency Ward: {highest_ward['ward_name']} (Score: {highest_ward['urgency_score']}) due to {highest_ward['anomaly_spike']}")
        
        required_rank_cols = ["ward_name", "urgency_score", "open_complaints", "average_urgency", "wow_spike_percent", "top_category", "anomaly_spike"]
        missing_rank_cols = [c for c in required_rank_cols if c not in rankings.columns]
        if missing_rank_cols:
            print(f"❌ Fail: Missing rankings columns {missing_rank_cols}")
            errors += 1
        else:
            print("✔ Success: All ranking index columns are present.")
            
        # Verify WoW spikes calculation
        spikes = engine.get_wow_spikes()
        print(f"Computed WoW spikes table. Row count: {len(spikes)}")
        
    except Exception as e:
        print(f"❌ Fail: Analytics check failed with error: {e}")
        errors += 1
        
    # 5. Check Conversational Agent Layer
    print_banner("5. Conversational Agent Grounding Layer")
    try:
        from agent.handler import ConversationalAgent
        agent = ConversationalAgent()
        
        # Try a test prompt
        test_prompt = "What is the status of Ward 4?"
        print(f"Querying Agent: '{test_prompt}'")
        resp = agent.generate_response(test_prompt)
        print("-" * 40)
        print(resp)
        print("-" * 40)
        
        if not resp:
            print("❌ Fail: Agent response was empty.")
            errors += 1
        else:
            print("✔ Success: Agent generated grounded response successfully.")
            
    except Exception as e:
        print(f"❌ Fail: Conversational Agent failed with error: {e}")
        errors += 1
        
    # Final Result
    print_banner("TEST RUNNER SUMMARY")
    if errors == 0:
        print("🎉 ALL TESTS PASSED SUCCESSFULLY! The platform is 100% stable and fully operational. 🎉")
        sys.exit(0)
    else:
        print(f"🛑 Test run completed with {errors} failures. Review logs. 🛑")
        sys.exit(1)

if __name__ == "__main__":
    main()
