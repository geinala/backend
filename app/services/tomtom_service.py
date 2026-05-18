import requests
from typing import List, TypedDict
from app.configs.environment_configuration import get_environment_configuration
from enum import Enum
from app.lib.logging.logging import get_logger

env = get_environment_configuration()

logger = get_logger(__name__)

class STATE_ENUM(str, Enum):
    Submitted = "Submitted"
    Validated = "Validated"
    Completed = "Completed"
    Failed = "Failed"

class Point(TypedDict):
    latitude: float
    longitude: float


class LocationPayload(TypedDict):
    point: Point


class MatrixPayload(TypedDict):
    origins: List[LocationPayload]
    destinations: List[LocationPayload]
    options: dict[str, bool | str | int | list[str] | float]
    
class Statistics(TypedDict):
    totalCount: int
    successes: int
    failures: int

class RouteSummary(TypedDict):
    lengthInMeters: int
    travelTimeInSeconds: int
    trafficDelayInSeconds: int
    
class MatrixResponse(TypedDict):
    originIndex: int
    destinationIndex: int
    routeSummary: RouteSummary
    
class TomTomSubmitedMatrixResponse(TypedDict):
    jobId: str
    state: STATE_ENUM

class TomTomStatusResponse(TypedDict):
    jobId: str
    state: STATE_ENUM
    statistics: Statistics
    
class TomTomMatrixResultResponse(TypedDict):
    data: List[MatrixResponse]
    statistics: Statistics

class RoutingSummary(TypedDict):
    lengthInMeters: int
    travelTimeInSeconds: int
    trafficDelayInSeconds: int
    trafficLengthInMeters: int
    departureTime: str
    arrivalTime: str
    noTrafficTravelTimeInSeconds: int
    historicTrafficTravelTimeInSeconds: int
    liveTrafficIncidentsTravelTimeInSeconds: int
    originalWaypointIndexAtEndOfLeg: int | None
    
class RouteLeg(TypedDict):
    summary: RoutingSummary
    encodedPolyline: str
    encodedPolylinePrecision: int
    
class Route(TypedDict):
    summary: RoutingSummary
    legs: List[RouteLeg]
    
class TomTomRouteResultResponse(TypedDict):
    formatVersion: int
    routes: List[Route]

class RoutingPayload(TypedDict):
    computeBestOrder: bool
    traffic: bool
    avoid: List[str]
    travelMode: str
    vehicleMaxSpeed: int
    routeRepresentation: str
    computeTravelTimeFor: str
    departAt: str | None
    sectionType: list[str]
    routeType: str


class QuerySummary(TypedDict):
    query: str
    queryType: str
    queryTime: int
    numResults: int
    offset: int
    totalResults: int
    fuzzyLevel: int
    queryIntent: List[str]


class AddressData(TypedDict):
    streetName: str
    municipality: str
    municipalitySecondarySubdivision: str
    countrySubdivision: str
    countrySubdivisionName: str
    countrySubdivisionCode: str
    countryCode: str
    country: str
    countryCodeISO3: str
    freeformAddress: str
    localName: str


class LatLon(TypedDict):
    lat: float
    lon: float


class Viewport(TypedDict):
    topLeftPoint: LatLon
    btmRightPoint: LatLon


class FuzzySearchResult(TypedDict):
    type: str
    id: str
    score: float
    address: AddressData
    position: LatLon
    viewport: Viewport


class FuzzySearchResponse(TypedDict):
    summary: QuerySummary
    results: List[FuzzySearchResult] | None


class TomTomService:
    BASE_URL = "https://api.tomtom.com"
    
    def __init__(self):
        self.matrix_api_key = env.TOMTOM_MATRIX_API_KEY
        self.routing_api_key = env.TOMTOM_ROUTING_API_KEY
        self.search_api_key = env.TOMTOM_SEARCH_API_KEY
        self.session = requests.Session()

    def generate_routes(self, routes: str, depart_at: str | None) -> TomTomRouteResultResponse:
        options: RoutingPayload = {
            "computeBestOrder": True,
            "traffic": True,
            "avoid": ["tollRoads", "ferries"],
            "travelMode": "motorcycle",
            "vehicleMaxSpeed": 60,
            "routeRepresentation": "encodedPolyline",
            "computeTravelTimeFor": "all",
            "departAt": depart_at,
            "sectionType": ["travelMode", "traffic"],
            "routeType": "fastest"
        }
        
        params: list[tuple[str, str | int | float]] = [
            ("key", self.routing_api_key),
            ("computeBestOrder", str(options["computeBestOrder"]).lower()),
            ("traffic", str(options["traffic"]).lower()),
            ("travelMode", options["travelMode"]),
            ("vehicleMaxSpeed", options["vehicleMaxSpeed"]),
            ("routeRepresentation", options["routeRepresentation"]),
            ("computeTravelTimeFor", options["computeTravelTimeFor"]),
            ("routeType", options["routeType"]),
        ]

        params.extend(("avoid", avoid_value) for avoid_value in options["avoid"])
        params.extend(("sectionType", section_type) for section_type in options["sectionType"])
        
        if options["departAt"]:
            params.append(("departAt", options["departAt"]))
        
        try:
            response = self.session.get(
                f"{self.BASE_URL}/routing/1/calculateRoute/{routes}/json",
                params=params,
                timeout=30,
            )
            
            response.raise_for_status()
            
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"TomTom API request failed: {e}")
            raise RuntimeError(f"TomTom API request failed: {e}") from e 

    def submit_matrix(
        self,
        origins: list[LocationPayload],
        destinations: list[LocationPayload]
    ) -> TomTomSubmitedMatrixResponse:
        payload: MatrixPayload = {
            "origins": origins,
            "destinations": destinations,
            "options": {
                "routeType": "fastest",
                "traffic": "historical",
                "travelMode": "car",
                "vehicleMaxSpeed": 60,
                "vehicleWeight": 120,
                "vehicleAxleWeight": 120,
                "vehicleLength": 2,
                "vehicleWidth": 0.8,
                "vehicleHeight": 1.2,
                "vehicleCommercial": False,
                "avoid": ["tollRoads", "unpavedRoads"],
            },
        }
        
        PARAMS = {"key": self.matrix_api_key}

        try:
            response = self.session.post(
                f"{self.BASE_URL}/routing/matrix/2/async",
                json=payload,
                params=PARAMS,
                timeout=30,
            )
            
            response.raise_for_status()
            
            return {
                "jobId": response.json().get("jobId"),
                "state": response.json().get("state"),
            }

        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"TomTom API request failed: {e}") from e
    
    def get_matrix_status(self, job_id: str) -> TomTomStatusResponse:
        URL = f"{self.BASE_URL}/routing/matrix/2/async/{job_id}"
        PARAMS = {"key": self.matrix_api_key}

        try:
            response = self.session.get(URL, params=PARAMS, timeout=30)
            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"TomTom API request failed: {e}") from e
        
    def get_matrix_result(self, job_id: str) -> TomTomMatrixResultResponse:
        URL = f"{self.BASE_URL}/routing/matrix/2/async/{job_id}/result"
        PARAMS = {"key": self.matrix_api_key}

        try:
            response = self.session.get(URL, params=PARAMS, timeout=30)
            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"TomTom API request failed: {e}") from e
        
    async def fuzzy_search(self, query: str) -> FuzzySearchResponse:
        URL = f"{self.BASE_URL}/search/2/search/{query}.json"
        params: dict[str, str | int] = {
            "key": self.search_api_key,
            "minFuzzyLevel": 1,
            "maxFuzzyLevel": 2,
            "view": "Unified",
            "relatedPois": "off",
            "idxSet": "Addr,Str",
            "limit": 1,
            "lat": "-7.983908",
            "lon": "112.621391",
            "radius": 20000,
        }
        
        try:
            response = self.session.get(URL, params=params, timeout=30)
            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            logger.error(f"TomTom fuzzy search failed: {e}")
            raise RuntimeError(f"TomTom API request failed: {e}") from e