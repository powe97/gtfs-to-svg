# Ben Kotrc
# 1/26/2016
# This script takes an expanded GTFS file and generates a new file,
# route_shapes.json, that contains one geojson MultiLineString for each
# entry in the GTFS routes.txt table. This represents the map shape for
# each route, including possible variations/line branches/etc, simplified
# using the Douglas-Peucker algorithm for a minimal resulting file size.

# Approach:
# For each route,
# 1 - Get the set of shapes corresponding to the route;
# 2 - Select the longest shape (with the most coordinate pairs);
# 3 - Draw a buffer around this longest shape;
# 4 - For each remaining shape,
# a - Remove points from the shape within the buffered area,
# b - Add the remaining shape to the longest shape as an additional
#     LineString in the MultiLineString

import os
import sys
import json
import pathlib
import argparse
import pandas as pd
import geojson as gj
import shapely.geometry as sh


def read_gtfs(gtfs_dir):
    shapes = pd.read_csv(os.path.join(gtfs_dir, "shapes.txt"))
    routes = pd.read_csv(os.path.join(gtfs_dir, "routes.txt"))
    trips = pd.read_csv(os.path.join(gtfs_dir, "trips.txt"))
    # stops = pd.read_csv(os.path.join(gtfs_dir, "stops.txt"))
    # stop_times = pd.read_csv(os.path.join(gtfs_dir, "stop_times.txt"))

    routes_trips = pd.merge(routes, trips, on="route_id", how="inner")
    routes_trips_shapes = pd.merge(
        routes_trips, shapes, on="shape_id", how="inner"
    )

    return (
        shapes,
        routes,
        routes_trips_shapes.drop(
            routes_trips_shapes.columns.difference(
                set(routes.columns)
                | {
                    "shape_id",
                    "shape_pt_lat",
                    "shape_pt_lon",
                    "shape_pt_sequence",
                    "shape_dist_traveled",
                }
            ),
            axis=1,
        ).drop_duplicates(),
    )


def route_to_shape(route_id, shapes, routes_trip_shapes):
    # Get the set of shapes corresponding to this route_id
    route_trips_shapes = routes_trips_shapes[
        routes_trips_shapes["route_id"] == route_id
    ]
    shape_ids = set(route_trips_shapes["shape_id"])

    # First, find the longest shape for this route
    longest = max(
        shape_ids,
        key=lambda shape_id: shapes[shapes["shape_id"] == shape_id][
            "shape_pt_sequence"
        ].count(),
    )

    # Now that we have the longest shape for the route, create a shapely
    # LineString for this route ID
    shapes_longest = shapes[shapes["shape_id"] == longest]
    multiline = sh.LineString(
        zip(
            shapes_longest["shape_pt_lon"].tolist(),
            shapes_longest["shape_pt_lat"].tolist(),
        )
    )

    # Now to go through them, and add only the points from each shape that
    # aren't in the area.
    for shape_id in shape_ids - {longest}:
        area = multiline.buffer(0.0001)

        shape = shapes[shapes["shape_id"] == shape_id]
        this_shape = sh.LineString(
            zip(
                shape["shape_pt_lon"].tolist(),
                shape["shape_pt_lat"].tolist(),
            )
        )

        if not this_shape.within(area):
            new_part = this_shape.difference(area)
            multiline = multiline.union(new_part)

    simplified_multiline = multiline.simplify(0.00005, preserve_topology=False)

    return gj.Feature(
        geometry=simplified_multiline,
        properties={
            k: next(iter(v.values()))
            for (k, v) in route_trips_shapes.drop(
                set(route_trips_shapes.columns)
                & {
                    "shape_id",
                    "shape_pt_lat",
                    "shape_pt_lon",
                    "shape_pt_sequence",
                    "shape_dist_traveled",
                },
                axis=1,
            )
            .drop_duplicates()
            .to_dict()
            .items()
        },
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate GeoJSON from GTFS dir."
    )
    parser.add_argument("-i", "--in-dir", required=True)
    parser.add_argument("-o", "--out-dir", required=True)
    args = parser.parse_args()

    shapes, routes, routes_trips_shapes = read_gtfs(args.in_dir)
    pathlib.Path(args.out_dir).mkdir(parents=True, exist_ok=True)
    for route_id in routes_trips_shapes["route_id"].unique():
        with open(
            os.path.join(args.out_dir, f"{route_id}.geojson"), "w"
        ) as outfile:
            gj.dump(
                route_to_shape(route_id, shapes, routes_trips_shapes),
                outfile,
                indent=4,
            )
