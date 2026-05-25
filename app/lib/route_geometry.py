import math
from collections.abc import Sequence


def decode_polyline(encoded_polyline: str, precision: int) -> list[tuple[float, float]]:
    if not encoded_polyline:
        return []

    scale = 10 ** max(precision, 0)
    index = 0
    latitude = 0
    longitude = 0
    coordinates: list[tuple[float, float]] = []

    while index < len(encoded_polyline):
        shift = 0
        result = 0

        while True:
            chunk = ord(encoded_polyline[index]) - 63
            index += 1
            result |= (chunk & 0x1F) << shift
            shift += 5
            if chunk < 0x20:
                break

        delta_latitude = ~(result >> 1) if result & 1 else (result >> 1)
        latitude += delta_latitude

        shift = 0
        result = 0

        while True:
            chunk = ord(encoded_polyline[index]) - 63
            index += 1
            result |= (chunk & 0x1F) << shift
            shift += 5
            if chunk < 0x20:
                break

        delta_longitude = ~(result >> 1) if result & 1 else (result >> 1)
        longitude += delta_longitude

        coordinates.append((latitude / scale, longitude / scale))

    return coordinates


def build_coordinate_points(coordinates: Sequence[Sequence[float]]) -> list[tuple[float, float]]:
    return [(float(latitude), float(longitude)) for longitude, latitude in coordinates]


def haversine_m(point_a: tuple[float, float], point_b: tuple[float, float]) -> float:
    latitude_one, longitude_one = point_a
    latitude_two, longitude_two = point_b

    earth_radius_m = 6_371_000
    phi_one = math.radians(latitude_one)
    phi_two = math.radians(latitude_two)
    delta_phi = math.radians(latitude_two - latitude_one)
    delta_lambda = math.radians(longitude_two - longitude_one)

    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi_one) * math.cos(phi_two) * math.sin(delta_lambda / 2) ** 2
    )
    return 2 * earth_radius_m * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def calculate_bearing_degrees(
    start_point: tuple[float, float],
    end_point: tuple[float, float],
) -> float:
    start_latitude_radians = math.radians(start_point[0])
    end_latitude_radians = math.radians(end_point[0])
    delta_longitude_radians = math.radians(end_point[1] - start_point[1])

    x_component = math.sin(delta_longitude_radians) * math.cos(end_latitude_radians)
    y_component = (
        math.cos(start_latitude_radians) * math.sin(end_latitude_radians)
        - math.sin(start_latitude_radians)
        * math.cos(end_latitude_radians)
        * math.cos(delta_longitude_radians)
    )

    return (math.degrees(math.atan2(x_component, y_component)) + 360.0) % 360.0


def _bearing_difference_degrees(first_bearing: float, second_bearing: float) -> float:
    return abs((first_bearing - second_bearing + 180.0) % 360.0 - 180.0)


def _polyline_bearing_degrees(points: list[tuple[float, float]]) -> float | None:
    if len(points) < 2:
        return None

    return calculate_bearing_degrees(points[0], points[-1])


def route_direction_matches_incident(
    route_points: list[tuple[float, float]],
    incident_points: list[tuple[float, float]],
    max_bearing_difference_degrees: float = 45.0,
) -> bool:
    route_bearing = _polyline_bearing_degrees(route_points)
    incident_bearing = _polyline_bearing_degrees(incident_points)

    if route_bearing is None or incident_bearing is None:
        return True

    return _bearing_difference_degrees(route_bearing, incident_bearing) <= max_bearing_difference_degrees


def _orientation(
    point_a: tuple[float, float],
    point_b: tuple[float, float],
    point_c: tuple[float, float],
) -> int:
    value = (
        (point_b[1] - point_a[1]) * (point_c[0] - point_b[0])
        - (point_b[0] - point_a[0]) * (point_c[1] - point_b[1])
    )

    if abs(value) < 1e-12:
        return 0

    return 1 if value > 0 else 2


def _on_segment(
    point_a: tuple[float, float],
    point_b: tuple[float, float],
    point_c: tuple[float, float],
) -> bool:
    return (
        min(point_a[0], point_c[0]) <= point_b[0] <= max(point_a[0], point_c[0])
        and min(point_a[1], point_c[1]) <= point_b[1] <= max(point_a[1], point_c[1])
    )


def segments_intersect(
    first_start: tuple[float, float],
    first_end: tuple[float, float],
    second_start: tuple[float, float],
    second_end: tuple[float, float],
) -> bool:
    orientation_one = _orientation(first_start, first_end, second_start)
    orientation_two = _orientation(first_start, first_end, second_end)
    orientation_three = _orientation(second_start, second_end, first_start)
    orientation_four = _orientation(second_start, second_end, first_end)

    if orientation_one != orientation_two and orientation_three != orientation_four:
        return True

    if orientation_one == 0 and _on_segment(first_start, second_start, first_end):
        return True
    if orientation_two == 0 and _on_segment(first_start, second_end, first_end):
        return True
    if orientation_three == 0 and _on_segment(second_start, first_start, second_end):
        return True
    if orientation_four == 0 and _on_segment(second_start, first_end, second_end):
        return True

    return False


def route_intersects_incident(
    route_points: list[tuple[float, float]],
    incident_points: list[tuple[float, float]],
) -> bool:
    if len(route_points) < 2 or len(incident_points) < 2:
        return False

    route_segments = list(zip(route_points, route_points[1:]))
    incident_segments = list(zip(incident_points, incident_points[1:]))

    for route_start, route_end in route_segments:
        for incident_start, incident_end in incident_segments:
            if segments_intersect(route_start, route_end, incident_start, incident_end):
                return True

    return False


def densify_polyline(
    points: list[tuple[float, float]],
    max_step_m: float = 20.0,
) -> list[tuple[float, float]]:
    if len(points) < 2:
        return points

    densified_points: list[tuple[float, float]] = [points[0]]

    for start_point, end_point in zip(points, points[1:]):
        segment_length_m = haversine_m(start_point, end_point)
        step_count = max(int(math.ceil(segment_length_m / max_step_m)), 1)

        for step_index in range(1, step_count + 1):
            interpolation_ratio = step_index / step_count
            interpolated_point = (
                start_point[0] + (end_point[0] - start_point[0]) * interpolation_ratio,
                start_point[1] + (end_point[1] - start_point[1]) * interpolation_ratio,
            )
            densified_points.append(interpolated_point)

    return densified_points


def compute_route_overlap_ratio(
    route_points: list[tuple[float, float]],
    incident_points: list[tuple[float, float]],
    threshold_m: float = 30.0,
) -> float:
    if not route_points or not incident_points:
        return 0.0

    close_route_points = 0
    for route_point in route_points:
        nearest_distance_m = min(haversine_m(route_point, incident_point) for incident_point in incident_points)
        if nearest_distance_m <= threshold_m:
            close_route_points += 1

    return close_route_points / len(route_points)


def incident_matches_route(
    route_points: list[tuple[float, float]],
    incident_points: list[tuple[float, float]],
    overlap_threshold_ratio: float = 0.20,
    proximity_threshold_m: float = 30.0,
    strict_mode: bool = False,
) -> tuple[bool, float, bool]:
    route_intersects = route_intersects_incident(route_points, incident_points)
    densified_route_points = densify_polyline(route_points)
    densified_incident_points = densify_polyline(incident_points)
    overlap_ratio = compute_route_overlap_ratio(
        route_points=densified_route_points,
        incident_points=densified_incident_points,
        threshold_m=proximity_threshold_m,
    )
    direction_matches = route_direction_matches_incident(
        route_points=densified_route_points,
        incident_points=densified_incident_points,
    )

    if strict_mode:
        is_valid_congestion = direction_matches and (
            route_intersects or overlap_ratio >= overlap_threshold_ratio
        )
    else:
        is_valid_congestion = route_intersects or (
            overlap_ratio >= overlap_threshold_ratio and direction_matches
        )

    return is_valid_congestion, overlap_ratio, route_intersects


def build_incident_bbox(
    route_points: list[tuple[float, float]],
    origin_latitude: float,
    origin_longitude: float,
    destination_latitude: float,
    destination_longitude: float,
    padding: float = 0.0025,
) -> tuple[float, float, float, float]:
    if route_points:
        latitudes = [point[0] for point in route_points]
        longitudes = [point[1] for point in route_points]

        min_longitude = min(longitudes) - padding
        min_latitude = min(latitudes) - padding
        max_longitude = max(longitudes) + padding
        max_latitude = max(latitudes) + padding

        return (min_longitude, min_latitude, max_longitude, max_latitude)

    min_longitude = min(origin_longitude, destination_longitude) - padding
    min_latitude = min(origin_latitude, destination_latitude) - padding
    max_longitude = max(origin_longitude, destination_longitude) + padding
    max_latitude = max(origin_latitude, destination_latitude) + padding

    return (min_longitude, min_latitude, max_longitude, max_latitude)