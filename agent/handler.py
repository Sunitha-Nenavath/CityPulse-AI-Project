import os
import sys
import re
import pandas as pd

# Add project root to sys.path to allow absolute imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
import google.generativeai as genai
from analytics.engine import AnalyticsEngine, CLASSIFIED_DATA_PATH
from rag.indexer import CivicRAG

# Load environment variables
load_dotenv()

class ConversationalAgent:
    def __init__(self):
        self.analytics = AnalyticsEngine()
        self.rag = CivicRAG()
        self.rag.load_index()
        
        self.use_gemini = False
        api_key = os.getenv("GEMINI_API_KEY")
        if api_key and api_key.strip() and not api_key.startswith("your_"):
            try:
                genai.configure(api_key=api_key)
                self.use_gemini = True
                print("Gemini API key configured for Conversational Agent.")
            except Exception as e:
                print(f"Failed to configure Gemini API for Agent: {e}. Using local rule-based responder.")
        else:
            print("GEMINI_API_KEY not configured. Using local rule-based grounded responder.")
            
    def _retrieve_grounding_context(self, query):
        """
        Gathers analytics tables and RAG resolved cases based on query.
        """
        # 1. Fetch current rankings and spikes
        rankings_df = self.analytics.get_ward_rankings()
        latest_spikes_df = self.analytics.get_wow_spikes()
        
        # Get latest week date
        df_all = pd.read_csv(CLASSIFIED_DATA_PATH)
        df_all["timestamp"] = pd.to_datetime(df_all["timestamp"])
        latest_week = df_all["timestamp"].dt.to_period("W").dt.start_time.max().strftime("%Y-%m-%d")
        
        # 2. Get top spikes for latest week
        latest_spikes = latest_spikes_df[
            (pd.to_datetime(latest_spikes_df["complaint_week"]).dt.strftime("%Y-%m-%d") == latest_week) &
            (latest_spikes_df["wow_growth_percentage"] > 0)
        ].head(5)
        
        # 3. Retrieve relevant resolved complaints via RAG
        rag_results = self.rag.search(query, k=3)
        
        # Build context string
        context = []
        context.append(f"CURRENT DATE/WEEK: Week of {latest_week}")
        
        context.append("\nWARD URGENCY RANKINGS:")
        for idx, row in rankings_df.iterrows():
            anom = f" (ANOMALY SPIKES: {row['anomaly_spike']})" if row['anomaly_spike'] != "" else ""
            context.append(
                f"Rank {idx+1}: {row['ward_name']} | Urgency Score: {row['urgency_score']} | "
                f"Open Complaints: {row['open_complaints']} | Avg Urgency: {row['average_urgency']} | "
                f"WoW Complaint Growth: {row['wow_spike_percent']}% | Top Category: {row['top_category']}{anom}"
            )
            
        context.append("\nRECENT WEEK-OVER-WEEK SPIKES:")
        for _, row in latest_spikes.iterrows():
            context.append(
                f"- {row['ward_name']} | Category: {row['category']} | "
                f"Count: {row['current_week_count']} (was {row['prev_week_count']}) | "
                f"Growth: +{row['wow_growth_percentage']}%"
            )
            
        context.append("\nSIMILAR PAST RESOLVED COMPLAINTS (RAG Grounding):")
        for i, res in enumerate(rag_results):
            context.append(
                f"Example {i+1}:\n"
                f"- Ward: {res['ward_name']} | Category: {res['category']} | Match Similarity: {res['score']:.2f}\n"
                f"- Citizen Complaint: {res['description_text']}\n"
                f"- How it was Resolved: {res['resolution_notes']}"
            )
            
        return "\n".join(context), rankings_df, latest_spikes, rag_results, latest_week

    def _generate_rule_based_response(self, query, context_str, rankings_df, spikes_df, rag_results, latest_week):
        """
        Creates a rich, dynamic, grounded response using Python logic if Gemini is offline.
        """
        query_lower = query.lower()
        response = []
        
        # Heading
        response.append(f"🤖 **CityPulse AI (Local Analytics Engine)** - Grounded Response for *Week of {latest_week}*\n")
        
        # 1. Handle requests about urgent wards
        if any(kw in query_lower for kw in ["urgent", "attention", "priority", "worst", "ranking", "rank"]):
            top_ward = rankings_df.iloc[0]
            second_ward = rankings_df.iloc[1]
            response.append(f"Based on our latest analytics, **{top_ward['ward_name']}** requires the most **urgent attention** with an Urgency Score of **{top_ward['urgency_score']}**.\n")
            response.append(f"**Key Drivers for {top_ward['ward_name']}:**")
            response.append(f"- **Open Complaints:** {top_ward['open_complaints']} active cases.")
            response.append(f"- **Average Severity:** {top_ward['average_urgency']}/5.")
            response.append(f"- **WoW Trend:** A sharp spike of **+{top_ward['wow_spike_percent']:.1f}%** in complaints.")
            if top_ward['anomaly_spike']:
                response.append(f"- **Anomalies:** Significant spikes detected in: *{top_ward['anomaly_spike']}*.")
                
            response.append(f"\nSecond in priority is **{second_ward['ward_name']}** (Urgency Score: {second_ward['urgency_score']}), which has {second_ward['open_complaints']} open complaints.")
            
            # Add general RAG recommendations
            if rag_results:
                response.append("\n**Past Resolution Reference for High-Priority Cases:**")
                best_match = rag_results[0]
                response.append(f"> *Complaint:* \"{best_match['description_text']}\"")
                response.append(f"> *Successful Action:* {best_match['resolution_notes']} (Match score: {best_match['score']:.2f})")
        
        # 2. Handle requests about a specific ward (e.g. Ward 4)
        elif "ward" in query_lower:
            # Extract ward number
            match = re.search(r'ward\s*(\d+)', query_lower)
            ward_name = f"Ward {match.group(1)}" if match else None
            
            if ward_name and ward_name in rankings_df["ward_name"].values:
                ward_data = rankings_df[rankings_df["ward_name"] == ward_name].iloc[0]
                response.append(f"### Status Report for **{ward_name}**")
                response.append(f"- **Priority Rank:** #{rankings_df[rankings_df['ward_name'] == ward_name].index[0] + 1} of 10")
                response.append(f"- **Urgency Score:** **{ward_data['urgency_score']}**")
                response.append(f"- **Open Cases:** {ward_data['open_complaints']} complaints currently active.")
                response.append(f"- **Trend:** Complaint volume grew by **{ward_data['wow_spike_percent']:.1f}%** week-over-week.")
                response.append(f"- **Primary Issue Area:** Category *{ward_data['top_category']}* represents the highest frequency.")
                
                # Check for anomalies
                if ward_data['anomaly_spike']:
                    response.append(f"- **⚠️ Critical Anomalies:** {ward_data['anomaly_spike']}")
                else:
                    response.append("- **Anomalies:** No critical WoW spikes detected this week.")
                    
                # Add RAG cases matching the query/ward
                response.append("\n#### Recommended Resolutions (RAG matches):")
                relevant_rag = [r for r in rag_results if r['category'].lower() == ward_data['top_category'].lower()]
                if not relevant_rag:
                    relevant_rag = rag_results[:2]
                for r in relevant_rag:
                    response.append(f"- **Category: {r['category'].title()}**")
                    response.append(f"  *Sample Complaint:* \"{r['description_text']}\"")
                    response.append(f"  *Action Taken:* **{r['resolution_notes']}**")
            else:
                response.append("I couldn't identify the specific ward you asked about. Please request details by stating 'Ward 1' through 'Ward 10'.")
                
        # 3. Handle requests about category spikes (potholes, water leaks, etc.)
        elif any(cat in query_lower for cat in ["pothole", "garbage", "water", "leak", "streetlight", "lamp"]):
            detected_cats = [cat for cat in ["pothole", "garbage", "water_leak", "streetlight"] if cat in query_lower or (cat == "water_leak" and "water" in query_lower)]
            cat = detected_cats[0] if detected_cats else "complaints"
            
            response.append(f"### Spike & Resolution Analysis for **{cat.replace('_', ' ').title()}**")
            
            # Find wards with spikes in this category
            cat_spikes = spikes_df[spikes_df["category"] == cat]
            if len(cat_spikes) > 0:
                response.append(f"Wards showing active week-over-week growth in **{cat}**:")
                for _, row in cat_spikes.iterrows():
                    response.append(f"- **{row['ward_name']}**: +{row['wow_growth_percentage']:.0f}% growth ({row['current_week_count']} reports vs {row['prev_week_count']} last week)")
            else:
                response.append(f"No abnormal spikes detected for **{cat}** in the latest week.")
                
            # RAG suggestions
            if rag_results:
                response.append("\n#### Verified Past Resolutions for this Category:")
                for r in rag_results[:2]:
                    response.append(f"- **Complaint:** \"{r['description_text']}\"")
                    response.append(f"  **Resolution:** {r['resolution_notes']}")
        
        # 4. Default response (Overview)
        else:
            total_open = rankings_df["open_complaints"].sum()
            top_ward = rankings_df.iloc[0]
            response.append("Hello! I am CityPulse AI, your civic intelligence assistant. Here is an overview of municipal operations:")
            response.append(f"- **Total Open Complaints:** {total_open} across all 10 wards.")
            response.append(f"- **Critical Area:** **{top_ward['ward_name']}** is ranked highest in urgency (Score: {top_ward['urgency_score']}) due to a **{top_ward['wow_spike_percent']:.1f}%** WoW increase.")
            response.append("\nTry asking me questions like:")
            response.append("1. *'Which wards need urgent attention this week?'*")
            response.append("2. *'What is causing the spike in Ward 4?'*")
            response.append("3. *'How did we resolve similar water leak complaints?'*")
            
        return "\n".join(response)

    def generate_response(self, query):
        """
        Retrieves context, formats a prompt, and generates a response.
        If Gemini is offline, falls back to the smart rule-based generator.
        """
        # 1. Retrieve grounding data
        context_str, rankings_df, spikes_df, rag_results, latest_week = self._retrieve_grounding_context(query)
        
        if not self.use_gemini:
            return self._generate_rule_based_response(query, context_str, rankings_df, spikes_df, rag_results, latest_week)
            
        # 2. Use Gemini
        try:
            model = genai.GenerativeModel("gemini-1.5-flash")
            
            prompt = f"""
You are "CityPulse AI", a conversational civic intelligence platform assistant designed for municipal ward officers.
Your role is to help ward officers prioritize response and spot patterns in citizen complaints using real-time data analysis.

You MUST answer the user's query using ONLY the grounding context provided below.
The context contains ward rankings, active spikes (Week-over-Week), and relevant past resolutions from the RAG index.

Instructions:
1. Be data-backed, concise, and professional.
2. Cite specific numbers, ward names, and percentages directly from the context.
3. If the user asks about how to fix an issue, refer to the "SIMILAR PAST RESOLVED COMPLAINTS" section and describe the successful action taken.
4. If there is a spike in a ward, identify the category of complaint causing the spike.
5. If the context does not contain enough information to answer a question, state that clearly rather than inventing facts.

Grounding Context:
{context_str}

User Query:
{query}
"""
            
            response = model.generate_content(
                prompt,
                generation_config={"temperature": 0.2}
            )
            return response.text
            
        except Exception as e:
            print(f"Gemini generation failed: {e}. Falling back to rule-based response.")
            return self._generate_rule_based_response(query, context_str, rankings_df, spikes_df, rag_results, latest_week)

if __name__ == "__main__":
    import sys
    import io
    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        
    agent = ConversationalAgent()
    print("\n--- Testing Agent Query: Wards needing urgent attention ---")
    print(agent.generate_response("Which wards need urgent attention this week?"))
    print("\n--- Testing Agent Query: Ward 4 spike details ---")
    print(agent.generate_response("what is causing the spike in Ward 4 and how should we fix it?"))
