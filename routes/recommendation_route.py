from fastapi import APIRouter, HTTPException
from google import genai
from google.genai import types
import os
import json
from typing import Dict, Any, List
from datetime import datetime
from models.trip import TripCreate as Trip
from dotenv import load_dotenv
import random

# Load environment variables from .env file
load_dotenv()

router = APIRouter(
    prefix="/recommendations",
    tags=["recommendations"]
)

# Initialize Gemini client with API key
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise ValueError("GEMINI_API_KEY environment variable is not set")

client = genai.Client(api_key=api_key)

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
    
     # Add random variation instructions
    random_style = random.choice([
        "be bold and suggest a very different vibe",
        "be slightly adventurous and suggest a hidden gem",
        "think globally and suggest a destination far from past trips",
        "suggest a location with a similar culture but in a different country",
        "recommend a famous underrated travel spot",
        "favor a place that tourists often miss",
        "think outside the box and suggest lesser-known destinations",
        "surprise the user with an unexpected but wonderful location"
    ])

    prompt = f"""As an AI travel planner, analyze this user's travel history and recommend a new destination:

Travel History:
{trip_history}

Today's date is {today}. Based on these past trips, {random_style}. Also, suggest a NEW and DIFFERENT destination that:
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
        if not prompt:
            print("Failed to generate prompt. No prompt generated.")
            raise HTTPException(status_code=500, detail="Failed to generate prompt")
        print("--- Gemini prompt ---\n", prompt)

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.9,
                top_p=0.8,
                top_k=40
            )
        )

        if not response or not response.candidates or not response.candidates[0].content:
            print("Failed to generate prompt. No content in response.")
            raise HTTPException(status_code=500, detail="No content in response")

        content = response.candidates[0].content.parts[0].text
        if not content:
            print("Failed to generate prompt. Empty content in response.")
            raise HTTPException(status_code=500, detail="Empty content in response")
        
        # Clean up the content to ensure it's valid JSON
        content = content.strip()
        if content.startswith('```json'):
            content = content[7:]
        if content.endswith('```'):
            content = content[:-3]
        content = content.strip()
        print(content)

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
