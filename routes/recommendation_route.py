from fastapi import APIRouter, HTTPException
from openai import OpenAI
import os
import json
from typing import Dict, Any, List
from datetime import datetime
from models.trip import TripCreate as Trip
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

router = APIRouter(
    prefix="/recommendations",
    tags=["recommendations"]
)

# Initialize OpenAI client with API key
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("OPENAI_API_KEY environment variable is not set")

myOpenAI = OpenAI(api_key=api_key)

def create_recommendation_prompt(past_trips: List[Trip]) -> str:
    # Get today's date
    today = datetime.now().strftime('%Y-%m-%d')
    
    # Extract unique destinations and their frequencies
    destination_counts = {}
    for trip in past_trips:
        destination = trip.destinationName
        destination_counts[destination] = destination_counts.get(destination, 0) + 1
    
    # Format trip history for the prompt
    trip_history = "\n".join([
        f"- {dest} (visited {count} times)" 
        for dest, count in destination_counts.items()
    ])

    prompt = f"""As an AI travel planner, analyze this user's travel history and recommend a new destination:

Travel History:
{trip_history}

Today's date is {today}. Based on these past trips, suggest a NEW and DIFFERENT destination that:
1. Has some similarities to their past preferences but offers unique experiences
2. Is NOT one of their previously visited places
3. Could be in a different region or country while maintaining similar interests
4. Provides a fresh perspective on their preferred travel style

IMPORTANT: Plan the trip to start at least one week after today's date. Do not suggest dates in the immediate future or past dates.

Provide your recommendation in this JSON format:
{{
  "data": {{  // Recommendation data
    "destination": {{  // Location details
      "city": string,     // City name
      "state": string,    // State name (for US locations)
      "country": string   // Country name (for non-US locations)
    }},
    "isSpecificPlace": true,
    "startDate": string,    // Suggest a good time to visit (YYYY-MM-DD)
    "endDate": string,      // Suggest trip duration (YYYY-MM-DD)
    "travelers": 1,         // Default to 1
    "accommodations": {{
      "hotel": boolean,
      "hotel_and_resort": boolean,
      "boutique_hotel": boolean,
      "local_homestay": boolean,
      "vacation_rental": boolean,
      "hostel": boolean
    }},
    "tripStyles": {{
      "relaxation": boolean,
      "adventure": boolean,
      "cultural": boolean,
      "shopping": boolean,
      "luxury": boolean,
      "beach": boolean,
      "hiking": boolean,
      "budget-friendly": boolean,
      "outdoor": boolean,
      "urban": boolean,
      "foodWine": boolean,
      "historical": boolean
    }},
    "activities": {{
      "hiking": boolean,
      "sightseeing": boolean,
      "museums": boolean,
      "local_markets": boolean,
      "adventure_sports": boolean,
      "beach_activities": boolean,
      "nightlife": boolean,
      "photography": boolean,
      "cooking_classes": boolean,
      "wildlife": boolean
    }},
    "dining": {{
      "restaurant": boolean,
      "localCuisine": boolean,
      "streetFood": boolean,
      "fineDining": boolean,
      "vegetarianVegan": boolean,
      "seafood": boolean,
      "dairyFree": boolean,
      "bar": boolean,
      "cafe": boolean,
      "pub": boolean,
      "vietnamese": boolean,
      "italian": boolean,
      "mexican": boolean,
      "thai": boolean,
      "indian": boolean,
      "japanese": boolean,
      "chinese": boolean,
      "korean": boolean
    }},
    "transportation": {{
      "car_rental": boolean,
      "public_transport": boolean,
      "taxi": boolean,
      "walking": boolean,
      "biking": boolean,
      "train": boolean,
      "bus": boolean,
      "boat": boolean
    }}
  }},
  "explanation": {{  // Reasoning for the recommendation
    "summary": string,  // Brief summary of why this destination was chosen
    "travelHistory": string,  // How it relates to past trips
    "highlights": string[]  // Key points about the recommendation
  }}
}}
"""

    return prompt

@router.post("/suggest-trip/{user_id}")
async def suggest_trip(user_id: str, past_trips: List[Trip]) -> Dict[str, Any]:
    try:
        prompt = create_recommendation_prompt(past_trips)
        
        completion = myOpenAI.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": f"You are a creative travel planning assistant that suggests diverse and unique destinations. While considering the user's preferences from their travel history, always recommend somewhere NEW and DIFFERENT from their past trips. Today's date is {datetime.now().strftime('%Y-%m-%d')}. Always plan trips to start at least one week in the future from today's date.",
                },
                {"role": "user", "content": prompt},
            ],
            model="gpt-4-turbo-preview",
            response_format={"type": "json_object"},
            temperature=1.0,  # Maximum creativity
            presence_penalty=0.9,  # Strongly encourage mentioning new topics
            max_tokens=1000,
        )

        content = completion.choices[0].message.content
        if not content:
            raise HTTPException(status_code=500, detail="No content in response")

        # Parse and validate the JSON response
        try:
            response_data = json.loads(content)
            
            # Validate required fields
            required_fields = [
                ('data', dict),
                ('data.destination', dict),
                ('data.destination.city', str),
                ('data.startDate', str),
                ('data.endDate', str),
                ('explanation', dict),
                ('explanation.summary', str),
                ('explanation.highlights', list)
            ]
            
            for path, expected_type in required_fields:
                value = response_data
                for key in path.split('.'):
                    if not isinstance(value, dict) or key not in value:
                        raise ValueError(f"Missing required field: {path}")
                    value = value[key]
                if not isinstance(value, expected_type):
                    raise ValueError(f"Invalid type for {path}: expected {expected_type.__name__}, got {type(value).__name__}")
            
            return response_data
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=500, detail=f"Failed to parse response: {str(e)}")

    except Exception as e:
        print("Error generating recommendation:", str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate recommendation: {str(e)}"
        )
