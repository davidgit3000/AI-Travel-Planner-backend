from fastapi import APIRouter, HTTPException
from google import genai
from google.genai import types
import os
from typing import Dict, Any
from models.destination import TravelRequest, DestinationsResponse
import json
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

router = APIRouter(
    prefix="/gemini",
    tags=["gemini"]
)

# Initialize Gemini client with API key
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise ValueError("GEMINI_API_KEY environment variable is not set")

client = genai.Client(api_key=api_key)

def create_travel_prompt(request: TravelRequest) -> str:
    basic_info = request.basicInfo
    
    # List of US states for checking
    us_states = [
        'Alabama', 'Alaska', 'Arizona', 'Arkansas', 'California', 'Colorado', 'Connecticut',
        'Delaware', 'Florida', 'Georgia', 'Hawaii', 'Idaho', 'Illinois', 'Indiana', 'Iowa',
        'Kansas', 'Kentucky', 'Louisiana', 'Maine', 'Maryland', 'Massachusetts', 'Michigan',
        'Minnesota', 'Mississippi', 'Missouri', 'Montana', 'Nebraska', 'Nevada', 'New Hampshire',
        'New Jersey', 'New Mexico', 'New York', 'North Carolina', 'North Dakota', 'Ohio',
        'Oklahoma', 'Oregon', 'Pennsylvania', 'Rhode Island', 'South Carolina', 'South Dakota',
        'Tennessee', 'Texas', 'Utah', 'Vermont', 'Virginia', 'Washington', 'West Virginia',
        'Wisconsin', 'Wyoming'
    ]
    is_us_state = basic_info.specificPlace in us_states
    # Determine the initial prompt based on whether it's a specific place
    if basic_info.isSpecificPlace:
        if is_us_state:
            location_prompt = f"suggest 5-6 top travel destinations in {basic_info.specificPlace}"
        else:
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
    if basic_info.isSpecificPlace:
        dest_count = "5-6 destinations" if is_us_state else "exactly 1 destination"
    else:
        dest_count = "5-6 destinations"
    highlights_count = "7-10 specific highlights" if basic_info.isSpecificPlace else "5-7 highlights"

    destination = '{"city": string, "state": string}' if is_us_state else '{"city": string, "country": string}'
    
    # Combine all sections
    prompt = f"""As an AI travel planner, {location_prompt}:

{basic_info_section}

{preferences_section}

{dining_section}

{activities_section}

For each destination, provide:
1. Location details (format depends on destination type)
2. A brief description (2-3 sentences) that includes:
   - The location's geographic position
   - Why it matches their preferences
3. 5-7 specific trip highlights or recommended activities

Format the response as a JSON object with the following structure:
{{
  "destinations": [  // Will contain {dest_count}
    {{
      "destination": {destination},  // Format depends on location type
      "description": string,  // Brief overview of the destination
      "highlights": string[]  // Array of {highlights_count}
    }}
  ]
}}

IMPORTANT: Ensure the response is a valid JSON object with all required fields."""

    return prompt

async def generate_destination_image(city: str, location: str, is_us_state: bool = False) -> str | None:
    max_retries = 3
    retry_count = 0

    while retry_count < max_retries:
        try:
            # Enhanced prompt engineering for better image quality
            location_text = f"{city}, {location}, USA" if is_us_state else f"{city}, {location}"
            prompt = f"""Generate a stunning, professional travel photograph of {location_text}.
                      Focus: Iconic landmarks, beautiful cityscapes, or natural wonders.
                      Style: High-quality travel photography, photorealistic, cinematic.
                      Composition: Wide angle, dramatic lighting, perfect exposure.
                      Resolution: 1024x1024, sharp details, vibrant colors."""
            
            # Configure image generation with specific parameters
            response = client.models.generate_content(
                model="gemini-2.0-flash-exp-image-generation",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_modalities=['TEXT', 'IMAGE'],
                    temperature=0.7,  # Lower temperature for more realistic results
                    top_p=0.9,
                    top_k=40
                )
            )

            if not response or not response.candidates or not response.candidates[0].content:
                print(f"Attempt {retry_count + 1}: Failed to generate image. No content in response.")
                retry_count += 1
                continue

            content = response.candidates[0].content
            if not content or not content.parts:
                print(f"Attempt {retry_count + 1}: Failed to generate image. No parts in content.")
                retry_count += 1
                continue

            # Process image data
            for part in content.parts:
                if part.inline_data and part.inline_data.mime_type.startswith('image/'):
                    mime_type = part.inline_data.mime_type
                    image_data = part.inline_data.data

                    # Handle different image data formats
                    import base64
                    if isinstance(image_data, bytes):
                        # If it's already bytes, encode it directly to base64
                        try:
                            image_data = base64.b64encode(image_data).decode('ascii')
                        except Exception as e:
                            print(f"Failed to encode bytes to base64: {str(e)}")
                            retry_count += 1
                            continue
                    elif isinstance(image_data, str):
                        # Try to parse the string as base64
                        try:
                            # First, try to decode it as base64 to validate it
                            base64.b64decode(image_data)
                        except:
                            # If it's not valid base64, it might be a string representation of bytes
                            # Remove any b' prefix and ' suffix if present
                            if image_data.startswith("b'") and image_data.endswith("'"):
                                image_data = image_data[2:-1]
                            # Remove any double encoding
                            if image_data.startswith("'b'") and image_data.endswith("''"):
                                image_data = image_data[3:-2]
                    
                    # Verify the base64 data is valid
                    try:
                        import base64
                        base64.b64decode(image_data)
                        return f"data:{mime_type};base64,{image_data}"
                    except Exception as e:
                        print(f"Invalid base64 data: {str(e)}")
                        retry_count += 1
                        continue

            print(f"Attempt {retry_count + 1}: No image found in response parts")
            retry_count += 1
            
        except Exception as e:
            print(f"Attempt {retry_count + 1}: Failed to generate image for {city}: {str(e)}")
            retry_count += 1
            
    print(f"Failed to generate image after {max_retries} attempts")
    return None

@router.post("/generate-recommendations", response_model=DestinationsResponse)
async def generate_recommendations(request: TravelRequest) -> Dict[str, Any]:
    try:
        print("Received request:", request.dict())
        print("API Key present:", bool(api_key))
        prompt = create_travel_prompt(request)
        print("Generated prompt:", prompt)

        try:
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
                raise HTTPException(status_code=500, detail="No content in response")

            content = response.candidates[0].content.parts[0].text
            if not content:
                raise HTTPException(status_code=500, detail="Empty content in response")

            # Clean up the content to ensure it's valid JSON
            content = content.strip()
            if content.startswith('```json'):
                content = content[7:]
            if content.endswith('```'):
                content = content[:-3]
            content = content.strip()

        except Exception as gemini_error:
            print("Gemini API Error:", str(gemini_error))
            raise HTTPException(
                status_code=500,
                detail=f"Gemini API Error: {str(gemini_error)}"
            )

        destinations = json.loads(content)
        
        # Validate response structure
        if not destinations.get("destinations") or not isinstance(destinations["destinations"], list):
            raise HTTPException(status_code=500, detail="Invalid response format from Gemini")

        # Generate images for each destination (currently returns None as Gemini doesn't support image generation)
        destinations_with_images = []
        for dest in destinations["destinations"]:
            if not all(key in dest for key in ["destination", "description", "highlights"]):
                raise HTTPException(status_code=500, detail="Invalid destination format in response")
            
            # Check if the destination has a state (US location) or country
            is_us_location = "state" in dest["destination"]
            location = dest["destination"].get("state") or dest["destination"].get("country")
            
            image_url = await generate_destination_image(
                dest["destination"]["city"],
                location,
                is_us_location
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
            error_message = "Gemini billing error - please check your account"
            status_code = 402

        raise HTTPException(status_code=status_code, detail=error_message)
