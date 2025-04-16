from pydantic import BaseModel, model_validator
from typing import List, Optional

class DestinationLocation(BaseModel):
    city: str
    state: Optional[str] = None
    country: Optional[str] = None

    @model_validator(mode='after')
    def check_location_fields(self) -> 'DestinationLocation':
        if not self.state and not self.country:
            raise ValueError('Either state or country must be provided')
        if self.state and self.country:
            raise ValueError('Cannot provide both state and country')
        return self

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
