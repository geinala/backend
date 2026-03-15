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

class TomTomService:
    BASE_URL = "https://api.tomtom.com/routing/matrix/2/async"
    
    def __init__(self):
        self.matrix_api_key = env.TOMTOM_MATRIX_API_KEY
        self.routing_api_key = env.TOMTOM_ROUTING_API_KEY
        self.session = requests.Session()

    def generate_routes(self, routes: str, depart_at: str | None) -> TomTomRouteResultResponse:
        options: RoutingPayload = {
            "computeBestOrder": True,
            "traffic": True,
            "avoid": ["tollRoads", "ferries"],
            "travelMode": "motorcycle",
            "vehicleMaxSpeed": 100,
            "routeRepresentation": "encodedPolyline",
            "computeTravelTimeFor": "all",
            "departAt": depart_at,
            "sectionType": ["travelMode", "traffic"],
        }
        
        params: list[tuple[str, str | int | float]] = [
            ("key", self.routing_api_key),
            ("computeBestOrder", str(options["computeBestOrder"]).lower()),
            ("traffic", str(options["traffic"]).lower()),
            ("travelMode", options["travelMode"]),
            ("vehicleMaxSpeed", options["vehicleMaxSpeed"]),
            ("routeRepresentation", options["routeRepresentation"]),
            ("computeTravelTimeFor", options["computeTravelTimeFor"]),
        ]

        params.extend(("avoid", avoid_value) for avoid_value in options["avoid"])
        params.extend(("sectionType", section_type) for section_type in options["sectionType"])
        
        if options["departAt"]:
            params.append(("departAt", options["departAt"]))
        
        try:
            response = self.session.get(
                f"https://api.tomtom.com/routing/1/calculateRoute/{routes}/json",
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
                "vehicleMaxSpeed": 100,
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
                self.BASE_URL,
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
        URL = f"{self.BASE_URL}/{job_id}"
        PARAMS = {"key": self.matrix_api_key}

        try:
            response = self.session.get(URL, params=PARAMS, timeout=30)
            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"TomTom API request failed: {e}") from e
        
    def get_matrix_result(self, job_id: str) -> TomTomMatrixResultResponse:
        URL = f"{self.BASE_URL}/{job_id}/result"
        PARAMS = {"key": self.matrix_api_key}

        try:
            response = self.session.get(URL, params=PARAMS, timeout=30)
            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"TomTom API request failed: {e}") from e