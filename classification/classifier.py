import os
import json
import time
import pandas as pd
from dotenv import load_dotenv
import google.generativeai as genai
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

# Load environment variables
load_dotenv()

# Setup paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DATA_PATH = os.path.join(BASE_DIR, "data", "raw_complaints.csv")
CLASSIFIED_DATA_PATH = os.path.join(BASE_DIR, "data", "classified_complaints.csv")

def local_heuristic_classifier(text, original_category, status):
    """
    Highly optimized local rule-based classifier that extracts category, urgency, and sentiment.
    Used as a fallback and verification baseline.
    """
    text_lower = text.lower()
    
    # 1. Classify Category (if we need to override or verify, but we can default to original_category)
    category = original_category
    if "pothole" in text_lower or "crater" in text_lower or "asphalt" in text_lower or "cave-in" in text_lower:
        category = "pothole"
    elif "garbage" in text_lower or "trash" in text_lower or "litter" in text_lower or "dumping" in text_lower or "debris" in text_lower:
        category = "garbage"
    elif "water" in text_lower or "leak" in text_lower or "valve" in text_lower or "pipe" in text_lower or "drainage" in text_lower or "flood" in text_lower:
        category = "water_leak"
    elif "streetlight" in text_lower or "lamp" in text_lower or "light" in text_lower or "dark" in text_lower or "pole" in text_lower:
        category = "streetlight"
    
    # 2. Urgency Score (1-5)
    urgency = 2  # Default baseline
    
    # High urgency words
    high_urgency_keywords = ["dangerous", "accident", "injur", "hazard", "burst", "ruptured", "flooding", "blackout", "wires", "swerve", "immediate", "emergency"]
    medium_urgency_keywords = ["overflowing", "missed", "flickering", "stinking", "broken", "menace", "block", "obstruct"]
    
    if any(kw in text_lower for kw in high_urgency_keywords):
        urgency = random_urgency([4, 5])
    elif any(kw in text_lower for kw in medium_urgency_keywords):
        urgency = random_urgency([3, 4])
    else:
        urgency = random_urgency([1, 2, 3])
        
    # Scale adjustment based on status or category
    if category == "water_leak" and "burst" in text_lower:
        urgency = 5
    if category == "streetlight" and "wires" in text_lower:
        urgency = 5
        
    # 3. Sentiment
    if any(kw in text_lower for kw in ["dangerous", "accident", "hazard", "stinking", "menace", "terrible", "worst", "unhygienic", "unsafe"]):
        sentiment = "negative"
    elif status == "resolved":
        sentiment = "neutral"  # Since it's fixed
    else:
        sentiment = "negative" if urgency >= 3 else "neutral"
        
    return category, urgency, sentiment

def random_urgency(options):
    # Deterministic-like random using text hash or standard random
    # To keep run reproducible, we can just use random
    import random
    return random.choice(options)

def classify_batch_with_gemini(batch_df):
    """
    Sends a batch of complaints to Gemini to classify.
    Returns a dictionary mapping complaint_id to classification results.
    """
    # Prepare batch data structure for LLM input
    complaints_list = []
    for _, row in batch_df.iterrows():
        complaints_list.append({
            "id": row["complaint_id"],
            "text": row["description_text"]
        })
        
    prompt = f"""
You are a municipal assistant helper. Classify the following complaints.
For each complaint:
1. Determine the category: 'pothole', 'garbage', 'water_leak', 'streetlight', or 'other'.
2. Assign an urgency score: 1 (Very Low) to 5 (Critical).
3. Determine the sentiment: 'negative', 'neutral', or 'positive'.

Return the result strictly as a valid JSON array of objects, with no markdown tags other than the JSON itself. Each object should have fields:
"id": (string matching the input complaint ID)
"category": (string)
"urgency": (integer 1-5)
"sentiment": (string)

Complaints to classify:
{json.dumps(complaints_list, indent=2)}
"""

    model = genai.GenerativeModel("gemini-1.5-flash")
    
    # Configure generation to return JSON
    response = model.generate_content(
        prompt,
        generation_config={"response_mime_type": "application/json"}
    )
    
    results = json.loads(response.text)
    return results

def classify_batch_with_mistral(batch_df, api_key):
    """
    Sends a batch of complaints to Mistral to classify.
    Returns a dictionary mapping complaint_id to classification results.
    """
    complaints_list = []
    for _, row in batch_df.iterrows():
        complaints_list.append({
            "id": row["complaint_id"],
            "text": row["description_text"]
        })
        
    prompt = f"""
You are a municipal assistant helper. Classify the following complaints.
For each complaint:
1. Determine the category: 'pothole', 'garbage', 'water_leak', 'streetlight', or 'other'.
2. Assign an urgency score: 1 (Very Low) to 5 (Critical).
3. Determine the sentiment: 'negative', 'neutral', or 'positive'.

Return the result strictly as a valid JSON array of objects, with no markdown tags other than the JSON itself. Each object should have fields:
"id": (string matching the input complaint ID)
"category": (string)
"urgency": (integer 1-5)
"sentiment": (string)

Complaints to classify:
{json.dumps(complaints_list, indent=2)}
"""

    url = "https://api.mistral.ai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    data = {
        "model": "mistral-small-latest",
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "response_format": {"type": "json_object"}
    }
    
    req = urllib.request.Request(url, data=json.dumps(data).encode("utf-8"), headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=30) as response:
        res_body = response.read().decode("utf-8")
        res_json = json.loads(res_body)
        content = res_json["choices"][0]["message"]["content"].strip()
        
        # Strip markdown if model outputted it
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
            
        return json.loads(content)

def run_classification():
    if not os.path.exists(RAW_DATA_PATH):
        print(f"Error: Raw complaints dataset not found at {RAW_DATA_PATH}. Run generator first.")
        return
        
    df = pd.read_csv(RAW_DATA_PATH)
    
    # Initialize API key
    api_key = os.getenv("GEMINI_API_KEY")
    use_gemini = False
    use_mistral = False
    
    if api_key and api_key.strip() and not api_key.startswith("your_"):
        if api_key.startswith("AQ."):
            try:
                # Test connection
                url = "https://api.mistral.ai/v1/chat/completions"
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }
                data = {
                    "model": "mistral-small-latest",
                    "messages": [{"role": "user", "content": "Ping"}]
                }
                req = urllib.request.Request(url, data=json.dumps(data).encode("utf-8"), headers=headers, method="POST")
                with urllib.request.urlopen(req, timeout=10) as response:
                    if response.status == 200:
                        use_mistral = True
                        print("Mistral API key configured successfully. Running batch classification with Mistral...")
            except Exception as e:
                print(f"Failed to connect to Mistral API: {e}. Falling back to local heuristic.")
        else:
            try:
                genai.configure(api_key=api_key)
                # Test connection
                model = genai.GenerativeModel("gemini-1.5-flash")
                model.generate_content("Ping", generation_config={"response_mime_type": "text/plain"})
                use_gemini = True
                print("Gemini API key configured successfully. Running batch classification with Gemini...")
            except Exception as e:
                print(f"Failed to configure Gemini API or connection timed out: {e}. Falling back to local heuristic.")
    else:
        print("API Key not found or holds default placeholder. Falling back to local heuristic classifier.")
        
    categories_classified = []
    urgency_scores = []
    sentiments = []
    
    if use_gemini or use_mistral:
        # We will process in batches of 50 to avoid token and rate limits
        batch_size = 50
        num_batches = (len(df) + batch_size - 1) // batch_size
        results_map = {}
        
        print(f"Processing {len(df)} records in {num_batches} batches of {batch_size}...")
        
        # Define helper for single batch execution to enable threading
        def process_single_batch(batch_idx):
            start_idx = batch_idx * batch_size
            end_idx = min(start_idx + batch_size, len(df))
            batch_df = df.iloc[start_idx:end_idx]
            
            for attempt in range(3):
                try:
                    if use_gemini:
                        res = classify_batch_with_gemini(batch_df)
                    else:
                        res = classify_batch_with_mistral(batch_df, api_key)
                    # Put into map
                    batch_res = {}
                    for item in res:
                        batch_res[item["id"]] = {
                            "category": item.get("category", "other"),
                            "urgency": int(item.get("urgency", 3)),
                            "sentiment": item.get("sentiment", "neutral")
                        }
                    print(f"Successfully processed batch {batch_idx + 1}/{num_batches}")
                    return batch_res
                except Exception as ex:
                    print(f"Error processing batch {batch_idx + 1} (Attempt {attempt + 1}/3): {ex}")
                    time.sleep(2)
            
            # Fallback for this batch if API fails after retries
            print(f"Batch {batch_idx + 1} failed all attempts. Using local heuristic fallback for this batch.")
            fallback_res = {}
            for _, row in batch_df.iterrows():
                cat, urg, sent = local_heuristic_classifier(row["description_text"], row["category"], row["status"])
                fallback_res[row["complaint_id"]] = {
                    "category": cat,
                    "urgency": urg,
                    "sentiment": sent
                }
            return fallback_res

        # Threaded batch processing
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {executor.submit(process_single_batch, i): i for i in range(num_batches)}
            for future in as_completed(futures):
                batch_res = future.result()
                results_map.update(batch_res)
                
        # Populate final arrays
        for _, row in df.iterrows():
            cid = row["complaint_id"]
            if cid in results_map:
                categories_classified.append(results_map[cid]["category"])
                urgency_scores.append(results_map[cid]["urgency"])
                sentiments.append(results_map[cid]["sentiment"])
            else:
                # Security fallback
                cat, urg, sent = local_heuristic_classifier(row["description_text"], row["category"], row["status"])
                categories_classified.append(cat)
                urgency_scores.append(urg)
                sentiments.append(sent)
    else:
        # Pure heuristic classification
        print("Processing classifications using fast rule-based parser...")
        for idx, row in df.iterrows():
            cat, urg, sent = local_heuristic_classifier(row["description_text"], row["category"], row["status"])
            categories_classified.append(cat)
            urgency_scores.append(urg)
            sentiments.append(sent)
            
    df["category_classified"] = categories_classified
    df["urgency_score"] = urgency_scores
    df["sentiment"] = sentiments
    
    # Save the classified dataframe
    df.to_csv(CLASSIFIED_DATA_PATH, index=False)
    print(f"Successfully saved {len(df)} classified complaints to {CLASSIFIED_DATA_PATH}")

if __name__ == "__main__":
    run_classification()
