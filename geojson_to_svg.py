import os
import json
import math
import argparse
import xml.etree.cElementTree as ET
import collections


def merc_x(lon):
    r_major = 6378137.000
    return r_major * math.radians(lon)


def merc_y(lat):
    if lat > 89.5:
        lat = 89.5
    if lat < -89.5:
        lat = -89.5
    r_major = 6378137.000
    r_minor = 6356752.3142
    temp = r_minor / r_major
    eccent = math.sqrt(1 - temp**2)
    phi = math.radians(lat)
    sinphi = math.sin(phi)
    con = eccent * sinphi
    com = eccent / 2
    con = ((1.0 - con) / (1.0 + con)) ** com
    ts = math.tan((math.pi / 2 - phi) / 2) / con
    y = 0 - r_major * math.log(ts)
    return y


def geojsons_to_svg(routes):
    # CDTA viewbox: -8267799.5 -5368096.5 91224.5 165737.5
    # Current: [(-8202113.25606219, -12346816.016656078), (4824075.10660079, 5333821.244428724)]
    svg = ET.Element(
        "svg",
        xmlns="http://www.w3.org/2000/svg",
        viewBox=" ".join(
            [
                str(flat)
                for N in zip(
                    *[
                        (min(L), max(L) - min(L))
                        for L in zip(
                            *[
                                (merc_x(coords[0]), -merc_y(coords[1]))
                                for route in routes
                                for line in (
                                    [route["geometry"]["coordinates"]]
                                    if route["geometry"]["type"] == "LineString"
                                    else route["geometry"]["coordinates"]
                                )
                                for coords in line
                            ]
                        )
                    ]
                )
                for flat in N
            ]
        ),
    )

    colors = collections.defaultdict(list)
    for route, color in {
        route["properties"]["route_id"]: route["properties"].get("route_color", "000000")
        for route in routes
    }.items():
        colors[color].append(route)

    style = ET.SubElement(svg, "style").text = (
        "g{stroke-width:100;fill:none;} "
        + " ".join(
            [
                (",".join([f"#r{route}" for route in routes]) + f"{{stroke:#{color};}}")
                for color, routes in colors.items()
            ]
        )
    )

    for route in routes:
        svg.append(route_geojson_to_g(route))

    return ET.ElementTree(svg)


def route_geojson_to_g(route_geojson):
    assert route_geojson["type"] == "Feature"

    group = ET.Element("g", id=f"r{route_geojson['properties']['route_id']}")

    geometry = route_geojson["geometry"]["coordinates"]
    if route_geojson["geometry"]["type"] == "LineString":
        geometry = [geometry]

    for segment in [
        [(merc_x(coord[0]), -merc_y(coord[1])) for coord in line] for line in geometry
    ]:
        ET.SubElement(
            group,
            "polyline",
            points=" ".join([",".join([str(x) for x in coord]) for coord in segment]),
        )

    return group


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate layered SVG from GeoJSON dir."
    )
    parser.add_argument("-i", "--in-dir", required=True)
    parser.add_argument("-o", "--out-file", required=True)
    args = parser.parse_args()

    jsons = []
    for filename in os.listdir(args.in_dir):
        with open(os.path.join(args.in_dir, filename)) as file:
            jsons.append(json.load(file))

    geojsons_to_svg(jsons).write(args.out_file)
