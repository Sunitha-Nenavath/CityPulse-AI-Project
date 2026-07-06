import os
import random
import uuid
import pandas as pd
from datetime import datetime, timedelta

def generate_synthetic_data(output_path="raw_complaints.csv", num_records=5000):
    print(f"Generating {num_records} synthetic citizen complaints...")
    
    # 10 Wards
    wards = [f"Ward {i}" for i in range(1, 11)]
    
    # Categories
    categories = ["pothole", "garbage", "water_leak", "streetlight", "other"]
    
    # Description templates
    templates = {
        "pothole": [
            "A huge pothole has opened up near {location}. It is causing traffic delays and is dangerous for two-wheelers.",
            "Deep crater in the middle of the road on {location}. Several cars have suffered tire damage.",
            "Multiple potholes have formed along {location} after the recent heavy rainfall.",
            "Dangerous pothole right at the active intersection of {location}. Needs immediate patching.",
            "Large asphalt cave-in on {location} causing vehicles to swerve unpredictably.",
            "Road surface is completely eroded and full of potholes near {location}."
        ],
        "garbage": [
            "The community garbage bin at {location} is overflowing. Street dogs are spreading waste everywhere.",
            "Illegal dumping of commercial and plastic waste at the vacant plot near {location}.",
            "Municipal collection truck skipped {location} for three consecutive days. Garbage is piling up.",
            "Stinking garbage pile on the sidewalk at {location} is attracting flies and pests.",
            "Piles of construction debris left on the roadside near {location}, obstructing pedestrians.",
            "Overflowing trash cans and plastic litter scattered all over {location}."
        ],
        "water_leak": [
            "Clean drinking water is spraying out from a ruptured underground pipe near {location}.",
            "A water main valve is leaking continuously on {location}, flooding the footpath.",
            "Severe waterlogging on {location} caused by a blocked drainage channel and pipeline leak.",
            "Water supply line has a major crack near {location}, leading to low water pressure in the neighborhood.",
            "Continuous drainage water overflow onto {location}, causing unhygienic conditions.",
            "Drinking water pipeline leak has been bubbling up from the pavement on {location} for days."
        ],
        "streetlight": [
            "Streetlight is completely dark near {location}. The entire stretch is unsafe at night.",
            "Flickering street lamp at {location} is causing constant distraction and needs replacement.",
            "Three consecutive street lamps are out of order along {location}, making the road pitch black.",
            "Broken streetlight pole near {location} after a vehicle collision. Exposed wires are visible.",
            "The timer for streetlights at {location} seems broken. Lights are off during dark hours.",
            "No working streetlights on the walkway near {location}, making it dangerous for evening walkers."
        ],
        "other": [
            "Stray dog menace near {location}. A pack of dogs is chasing kids and pedestrians.",
            "Public park benches and playground swings are broken and rusted at {location}.",
            "Illegal commercial hoarding erected near the traffic junction at {location}, blocking the signals.",
            "High noise levels from a commercial event/party near {location} violating night curfew rules.",
            "Encroachment on the public sidewalk by vendors near {location}, forcing pedestrians onto the road.",
            "Tree branch is broken and hanging dangerously over the power lines near {location}."
        ]
    }
    
    # Resolution notes templates
    resolutions = {
        "pothole": [
            "Pothole filled with cold-mix asphalt, leveled, and compacted. Normal traffic flow restored.",
            "Road repair crew patched the craters on this road section. Inspection completed.",
            "Asphalt layering completed over the damaged spots. The stretch is now safe.",
            "Repaired the cave-in area and reinforced with gravel base before final paving."
        ],
        "garbage": [
            "Sanitation truck dispatched to clear the overflowing bin. The area has been sanitized.",
            "Cleared the illegal dumping site. Warned local shopkeepers and put up a 'No Littering' sign.",
            "Missed garbage collection route completed. Regular scheduling resumed.",
            "Cleared the construction debris from the sidewalk using a JCB loader. Path is now clear."
        ],
        "water_leak": [
            "Maintenance team isolated the pipe line, welded the joint crack, and restored standard pressure.",
            "Repaired the leaking main supply valve and replaced the damaged washer.",
            "Cleared the drainage blockage and repaired the cracked water main. Waterlogging resolved.",
            "Plumbing crew repaired the pavement leak. Restored the footpath surface."
        ],
        "streetlight": [
            "Electrical team replaced the fused LED bulb. Street lamp is now working properly.",
            "Repaired the flickering light controller unit and wiring connections.",
            "Replaced bulbs on all three dark streetlight poles. Illumination levels verified.",
            "Removed the damaged pole and installed a new streetlight assembly. Made wires safe."
        ],
        "other": [
            "Stray dog control team visited the area. Conducted vaccination/sterilization drive.",
            "Public works team replaced the broken park benches and repaired the swings.",
            "Unauthorized hoarding removed. Fined the advertising agency for illegal setup.",
            "Patrolling team warned the organizers. Noise level brought down to legal limits."
        ]
    }
    
    # Street names for realistic locations
    streets = [
        "Main Street", "Market Road", "Elm Avenue", "Oak Street", "Pine Road", 
        "Broadway", "Link Road", "Station Road", "Park Lane", "Church Street",
        "Temple Road", "Lakeview Drive", "MG Road", "Hill Road", "Ring Road"
    ]
    landmarks = [
        "the Metro Station", "the Public Library", "Government School", "the Post Office",
        "the Sector 4 Park", "City Hospital", "the Shopping Complex", "the Bus Stand"
    ]
    
    def get_location():
        if random.random() < 0.5:
            return f"{random.choice(streets)}"
        else:
            return f"near {random.choice(landmarks)} on {random.choice(streets)}"
            
    # We want complaints spanning the last 12 weeks.
    # Current date is 2026-07-04. We'll generate from 2026-04-12 to 2026-07-04.
    start_date = datetime(2026, 4, 12)
    end_date = datetime(2026, 7, 4)
    total_days = (end_date - start_date).days
    
    records = []
    
    # In order to make it look realistic, we want to inject deliberate spikes in certain weeks.
    # Let's say:
    # Spike 1: Ward 3 has a huge water_leak spike in week 6 (around May 24 - May 30)
    # Spike 2: Ward 7 has a huge garbage spike in week 9 (around June 14 - June 20)
    # Spike 3: Ward 4 has a massive pothole spike in week 11 (around June 28 - July 4)
    
    # We will generate base complaints distributed across days.
    # Base: roughly 350-400 complaints per week across all wards (~50 complaints/day total)
    base_count = 4300
    for _ in range(base_count):
        cat = random.choice(categories)
        ward = random.choice(wards)
        
        # Random date in the 12 weeks
        random_days = random.randint(0, total_days)
        timestamp = start_date + timedelta(days=random_days, 
                                           hours=random.randint(0, 23), 
                                           minutes=random.randint(0, 59))
        
        # Decide status (older complaints are much more likely to be resolved, newer might be open)
        days_old = (end_date - timestamp).days
        # If it is in the last 7 days, 60% chance it is open. If > 30 days old, 95% resolved.
        if days_old <= 7:
            status = "open" if random.random() < 0.6 else "resolved"
        elif days_old <= 21:
            status = "open" if random.random() < 0.25 else "resolved"
        else:
            status = "open" if random.random() < 0.05 else "resolved"
            
        location = get_location()
        desc = random.choice(templates[cat]).format(location=location)
        
        if status == "resolved":
            res = random.choice(resolutions[cat])
        else:
            res = ""
            
        records.append({
            "complaint_id": str(uuid.uuid4())[:8].upper(),
            "ward_name": ward,
            "category": cat,
            "description_text": desc,
            "timestamp": timestamp,
            "status": status,
            "resolution_notes": res
        })
        
    # Now let's inject Spikes to guarantee we have spikes (>50% increase) in data:
    # Spike 1: Ward 3, water_leak, Week of May 24th (Week 6) -> Let's add 250 complaints
    # Spike 2: Ward 7, garbage, Week of June 14th (Week 9) -> Let's add 200 complaints
    # Spike 3: Ward 4, pothole, Week of June 28th (Week 11 - latest) -> Let's add 250 complaints
    
    spikes = [
        {"ward": "Ward 3", "cat": "water_leak", "start_day": 42, "count": 250}, # 42 days from April 12 is May 24
        {"ward": "Ward 7", "cat": "garbage", "start_day": 63, "count": 200},   # 63 days is June 14
        {"ward": "Ward 4", "cat": "pothole", "start_day": 77, "count": 250}    # 77 days is June 28 (latest week)
    ]
    
    for spike in spikes:
        for _ in range(spike["count"]):
            # Random time during that week
            offset_days = random.randint(0, 6)
            timestamp = start_date + timedelta(days=spike["start_day"] + offset_days,
                                               hours=random.randint(0, 23),
                                               minutes=random.randint(0, 59))
            
            # Status resolution profile
            days_old = (end_date - timestamp).days
            if days_old <= 7:
                status = "open" if random.random() < 0.7 else "resolved"
            else:
                status = "open" if random.random() < 0.1 else "resolved"
                
            location = get_location()
            desc = random.choice(templates[spike["cat"]]).format(location=location)
            res = random.choice(resolutions[spike["cat"]]) if status == "resolved" else ""
            
            records.append({
                "complaint_id": str(uuid.uuid4())[:8].upper(),
                "ward_name": spike["ward"],
                "category": spike["cat"],
                "description_text": desc,
                "timestamp": timestamp,
                "status": status,
                "resolution_notes": res
            })
            
    # If the number of generated records is slightly off, adjust to exactly num_records
    # But dynamic generation with ~5000 is perfectly fine as well. Let's make sure it's around 5,000.
    print(f"Generated {len(records)} total records (with spikes).")
    
    df = pd.DataFrame(records)
    # Sort by timestamp
    df = df.sort_values(by="timestamp").reset_index(drop=True)
    
    # Save to file
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df.to_csv(output_path, index=False)
    print(f"Successfully saved complaints to {output_path}")
    return df

if __name__ == "__main__":
    import sys
    output_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(output_dir)
    target_path = os.path.join(project_dir, "data", "raw_complaints.csv")
    generate_synthetic_data(target_path)
