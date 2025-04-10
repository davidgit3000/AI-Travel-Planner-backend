from pydantic import BaseModel
from typing import List, Optional

class DestinationLocation(BaseModel):
    city: str
    country: str

class Destination(BaseModel):
    destination: DestinationLocation
    description: str
    highlights: List[str]
    imageUrl: Optional[str] = None

class TravelPreferences(BaseModel):
    tripStyles: List[str]
    accommodation: List[str]
    transportation: List[str]

class BasicInfo(BaseModel):
    isSpecificPlace: bool
    specificPlace: Optional[str] = None
    destination: Optional[str] = None
    startDate: str
    endDate: str
    travelers: int

class TravelRequest(BaseModel):
    basicInfo: BasicInfo
    travelPreferences: TravelPreferences
    diningPreferences: List[str]
    activities: List[str]

class DestinationsResponse(BaseModel):
    destinations: List[Destination]
