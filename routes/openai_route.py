from fastapi import APIRouter, HTTPException
from openai import OpenAI
import os
from typing import Dict, Any
from models.destination import TravelRequest, DestinationsResponse
import json
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

router = APIRouter(
    prefix="/openai",
    tags=["openai"]
)

# Initialize OpenAI client with API key
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("OPENAI_API_KEY environment variable is not set")

myOpenAI = OpenAI(api_key=api_key)

def create_travel_prompt(request: TravelRequest) -> str:
    basic_info = request.basicInfo
    
    # Determine the initial prompt based on whether it's a specific place
    if basic_info.isSpecificPlace:
        location_prompt = f"provide detailed travel information for {basic_info.specificPlace}"
    else:
        location_suffix = f" located in {basic_info.destination}" if basic_info.destination else ""
        location_prompt = f"suggest 5 to 6 travel destinations{location_suffix}"
    
    # Build basic information section
    destination_type = 'Specific Place' if basic_info.isSpecificPlace else 'Country'
    location = basic_info.specificPlace if basic_info.isSpecificPlace else (basic_info.destination or 'Open to suggestions')
    basic_info_section = f"""Basic Information:
- Destination Type: {destination_type}
- Location: {location}
- Travel Dates: {basic_info.startDate} to {basic_info.endDate}
- Number of Travelers: {basic_info.travelers}"""

    # Build preferences section
    preferences_section = f"""Travel Preferences:
- Trip Styles: {', '.join(request.travelPreferences.tripStyles)}
- Accommodation Types: {', '.join(request.travelPreferences.accommodation)}
- Transportation: {', '.join(request.travelPreferences.transportation)}"""

    # Build dining and activities sections
    dining_section = f"Dining Preferences:\n{', '.join(request.diningPreferences)}"
    activities_section = f"Activities:\n{', '.join(request.activities)}"

    # Build destination count text
    dest_count = "exactly 1 destination" if basic_info.isSpecificPlace else "5-6 destinations"
    highlights_count = "7-10 specific highlights" if basic_info.isSpecificPlace else "5-7 highlights"

    # Combine all sections
    prompt = f"""As an AI travel planner, {location_prompt}:

{basic_info_section}

{preferences_section}

{dining_section}

{activities_section}

For each destination, provide:
1. City and Country name
2. A brief description (2-3 sentences) that includes:
   - The location (state/province/region and geographic position in the country)
   - Why it matches their preferences
3. 5-7 specific trip highlights or recommended activities

Format the response as a JSON object with the following structure:
{{
  "destinations": [  // Will contain {dest_count}]
    {{
      "destination": {{ "city": string, "country": string }},  // For specific places, use the exact location provided
      "description": string,  // Include detailed location information
      "highlights": string[]  // {highlights_count}
    }}
  ]
}}

Ensure the suggestions are highly personalized based on all preferences and provide specific, actionable recommendations."""
    return prompt

async def generate_destination_image(city: str, country: str) -> str:
    try:
        prompt = f"A beautiful, professional travel photograph of {city}, {country}. Show iconic landmarks or cityscapes that capture the essence of the destination. Style: high-quality travel photography, 4K, realistic."
        
        response = myOpenAI.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size="1024x1024",
            quality="standard",
            n=1,
            response_format="url"
        )
        
        return response.data[0].url
    except Exception as e:
        print(f"Failed to generate image for {city}: {str(e)}")
        return None

@router.post("/generate-recommendations", response_model=DestinationsResponse)
async def generate_recommendations(request: TravelRequest) -> Dict[str, Any]:
    try:
        print("Received request:", request.dict())
        print("API Key present:", bool(api_key))
        prompt = create_travel_prompt(request)
        print("Generated prompt:", prompt)

        try:
            completion = myOpenAI.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": "You are a travel planning assistant that provides personalized destination recommendations based on user preferences. Always respond in the exact JSON format specified in the prompt. Focus on providing specific, actionable recommendations that match the user's preferences.",
                    },
                    {"role": "user", "content": prompt},
                ],
                model="gpt-4-turbo-preview",
                response_format={"type": "json_object"},
                temperature=0.7,
                max_tokens=1500,
            )
        except Exception as openai_error:
            print("OpenAI API Error:", str(openai_error))
            raise HTTPException(
                status_code=500,
                detail=f"OpenAI API Error: {str(openai_error)}"
            )

        content = completion.choices[0].message.content
        if not content:
            raise HTTPException(status_code=500, detail="No content in response")

        destinations = json.loads(content)
        
        # Validate response structure
        if not destinations.get("destinations") or not isinstance(destinations["destinations"], list):
            raise HTTPException(status_code=500, detail="Invalid response format from OpenAI")

        # Generate images for each destination
        destinations_with_images = []
        for dest in destinations["destinations"]:
            if not all(key in dest for key in ["destination", "description", "highlights"]):
                raise HTTPException(status_code=500, detail="Invalid destination format in response")
            
            image_url = await generate_destination_image(
                dest["destination"]["city"],
                dest["destination"]["country"]
            )
            
            destinations_with_images.append({
                **dest,
                "imageUrl": image_url
            })

        return {"destinations": destinations_with_images}

    except HTTPException as he:
        raise he
    except Exception as e:
        print("Unexpected error:", str(e))
        error_message = "Failed to generate travel recommendations"
        status_code = 500

        if "api_key" in str(e).lower():
            error_message = "Invalid or missing API key"
            status_code = 401
        elif "rate_limit" in str(e).lower():
            error_message = "Too many requests, please try again later"
            status_code = 429
        elif "billing" in str(e).lower():
            error_message = "OpenAI billing error - please check your account"
            status_code = 402

        raise HTTPException(status_code=status_code, detail=error_message)
