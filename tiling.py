import sys
import pdb
from lxml import etree
from shapely.geometry import Polygon, MultiLineString, LineString
from shapely.geometry import shape
from shapely.geometry import box
#from kml2geojson import convert
import matplotlib.pyplot as plt
import mercantile
import simplekml
from shapely.ops import unary_union
from math import cos, radians
import subprocess
import random
import datetime

import argparse
# -----------------------------------

def kml_to_shapes(kml_file, zoom_level):
    # Read KML as XML
    tree = etree.parse(kml_file)
    root = tree.getroot()

    # Find all placemark elements
    placemarks = root.findall(".//{http://www.opengis.net/kml/2.2}Placemark")

    polygon_storage = []


    for pm in placemarks:

        name = pm.find(".//{http://www.opengis.net/kml/2.2}name").text

        if not (
                (zoom_level == 14 and name == 'squadrats') 
                or 
                (zoom_level == 17 and name == 'squadratinhos')):
            continue

        # find the polygons
        polygons = pm.findall(".//{http://www.opengis.net/kml/2.2}Polygon")
        for polygon in polygons:
            # find the outer boundary => 1 pcs

            outer_boundary = polygon.find(".//{http://www.opengis.net/kml/2.2}outerBoundaryIs")
            ob_coordinates = outer_boundary.find(".//{http://www.opengis.net/kml/2.2}coordinates")

            ob_coordinates = [x.strip() for x in ob_coordinates.text.split(' ') if x]
            ob_coordinates = [[float(y) for y in x.split(',')] for x in ob_coordinates]

            hole_coordinates = []

            inner_boundaries = polygon.findall(".//{http://www.opengis.net/kml/2.2}innerBoundaryIs")
            for hole in inner_boundaries:
                in_coordinates = hole.find(".//{http://www.opengis.net/kml/2.2}coordinates")
                in_coordinates = [x.strip() for x in in_coordinates.text.split(' ') if x]
                in_coordinates = [[float(y) for y in x.split(',')] for x in in_coordinates]
                hole_coordinates.append(in_coordinates)

            # Create the polygon
            polygon_storage.append(Polygon(ob_coordinates, holes = hole_coordinates))
    return polygon_storage

# --------------------------

# TÄTÄ EI NYT OIKEASTAAN TARVITA MIHINKÄÄN, KOSKA TÄMÄ EI KUITENKAAN KELPAA
# SELLAISENAAN MKGMAP SOFTALLE.

def shapes_to_osm(shapes, multi_grid, output_file):
    osm = etree.Element("osm", version="0.6", generator="Python")
    
    node_id = 1
    way_id = 1
    nodes = {}  # Track nodes to avoid duplicates
    
    # Helper function to add nodes safely
    def add_node(lat, lon):
        nonlocal node_id
        node_key = (lat, lon)
        if node_key not in nodes:
            node = etree.SubElement(osm, "node", id=str(node_id), lat=str(lat), lon=str(lon), version="1")
            nodes[node_key] = node_id
            node_id += 1
        return nodes[node_key]

    # Process Polygon and LineString shapes
    for shape in shapes:
        if isinstance(shape, Polygon):
            way = etree.SubElement(osm, "way", id=str(way_id), version="1")
            for coord in shape.exterior.coords:
                node_ref = add_node(coord[1], coord[0])  # Store unique nodes
                etree.SubElement(way, "nd", ref=str(node_ref))
            way_id += 1

            for interior in shape.interiors:
                way = etree.SubElement(osm, "way", id=str(way_id), version="1")  # Separate way for holes
                for coord in interior.coords:
                    node_ref = add_node(coord[1], coord[0])
                    etree.SubElement(way, "nd", ref=str(node_ref))
                way_id += 1
        
        elif isinstance(shape, LineString):
            way = etree.SubElement(osm, "way", id=str(way_id), version="1")
            for coord in shape.coords:
                node_ref = add_node(coord[1], coord[0])
                etree.SubElement(way, "nd", ref=str(node_ref))
            way_id += 1
    
    # Process MultiLineString (Grid Lines)
    if isinstance(multi_grid, MultiLineString):
        for line in multi_grid.geoms:
            way = etree.SubElement(osm, "way", id=str(way_id), version="1")
            for coord in line.coords:
                node_ref = add_node(coord[1], coord[0])
                etree.SubElement(way, "nd", ref=str(node_ref))
            way_id += 1
    
    # Save to file
    tree = etree.ElementTree(osm)
    tree.write(output_file+'.osm', encoding="utf-8", xml_declaration=True)
    print(f"OSM file saved as {output_file}.osm")

# -----------------------------------    

def create_tile_grid(bounding_box, zoom):

    minx=bounding_box[0]
    maxx=bounding_box[2]
    miny=bounding_box[1]
    maxy=bounding_box[3]

    grid_lines = []

    # Get tile coordinates for bounding box
    tile_min = mercantile.tile(minx, miny, zoom)
    tile_max = mercantile.tile(maxx, maxy, zoom)

    # Generate vertical lines (Longitude-based)
    if tile_min.x > tile_max.x +1:
        step = -1
    else:
        step = 1
    for x in range(tile_min.x, tile_max.x + 1, step):
        lon_left, lat_top = mercantile.bounds(x, tile_min.y, zoom)[:2]
        lon_right, lat_bottom = mercantile.bounds(x, tile_max.y, zoom)[:2]
        grid_lines.append(LineString([(lon_left, lat_bottom), (lon_left, lat_top)]))

    # Generate horizontal lines (Latitude-based)
    if tile_min.y > tile_max.y +1:
        step = -1
    else:
        step = 1
    for y in range(tile_min.y, tile_max.y + 1, step):
        lon_left, lat_top = mercantile.bounds(tile_min.x, y, zoom)[:2]
        lon_right, lat_bottom = mercantile.bounds(tile_max.x, y, zoom)[:2]
        grid_lines.append(LineString([(lon_left, lat_top), (lon_right, lat_top)]))

    return MultiLineString(grid_lines)


# --------------------------

def geometry_to_kml(shapes, multi_grid, output_file):
    kml = simplekml.Kml()
    if shapes is not None:
        for shape in shapes:
            if isinstance(shape, Polygon):  
                # Add polygon with outer boundary
                poly = kml.newpolygon(outerboundaryis=list(shape.exterior.coords))

                # Add ALL inner boundaries (holes)
                poly.innerboundaryis = [list(interior.coords) for interior in shape.interiors]
                
            elif isinstance(shape, MultiLineString):
                for line in shape.geoms:
                    kml.newlinestring(coords=list(line.coords))

            elif isinstance(shape, LineString):  
                kml.newlinestring(coords=list(shape.coords))

    # add the multigrid
    if multi_grid is not None:
        if isinstance(multi_grid, MultiLineString):
            for line in multi_grid.geoms:  # Iterate through each LineString in MultiLineString
                kml.newlinestring(coords=list(line.coords))

    kml.save(output_file+'.kml')
    print(f"KML saved as {output_file}")

#------------------------------
def km_to_degrees(km, lat):
    """Convert kilometers to degrees of latitude/longitude at a given latitude."""
    earth_radius_km = 6371  # Earth radius in kilometers
    deg_per_km_lat = 1 / (earth_radius_km * (2 * 3.141592653589793 / 360))  # Approx. degrees per km latitude
    deg_per_km_lon = deg_per_km_lat / cos(radians(lat))  # Adjust longitude based on latitude

    return km * deg_per_km_lat, km * deg_per_km_lon

#------------------------------

def round_bbox_to_osm_tiles(center_lon, center_lat, h_distance_km, v_distance_km, zoom):
    """
    Expands a bounding box centered at (lat, lon) to fit OSM tiles at a given zoom level,
    using distances provided in kilometers.
    
    Parameters:
        center_lat (float): Latitude of the center point.
        center_lon (float): Longitude of the center point.
        h_distance_km (float): Horizontal distance in km from the center.
        v_distance_km (float): Vertical distance in km from the center.
        zoom (int): Target OSM zoom level.

    Returns:
        rounded_bbox (tuple): (rounded_min_lon, rounded_min_lat, rounded_max_lon, rounded_max_lat)
    """

    # Convert distances to degrees
    v_distance_deg, h_distance_deg = km_to_degrees(v_distance_km, center_lat), km_to_degrees(h_distance_km, center_lat)

    # Compute initial bounding box
    min_lon, min_lat = center_lon - h_distance_deg[1], center_lat - v_distance_deg[0]
    max_lon, max_lat = center_lon + h_distance_deg[1], center_lat + v_distance_deg[0]

    # Get tile indices for bounding box corners at the given zoom level
    min_tile = mercantile.tile(min_lon, min_lat, zoom)
    max_tile = mercantile.tile(max_lon, max_lat, zoom)

    # Expand tiles to fully cover the bounding box
    rounded_min_lon, rounded_min_lat = mercantile.bounds(min_tile.x, min_tile.y, zoom)[:2]
    rounded_max_lon, rounded_max_lat = mercantile.bounds(max_tile.x + 1, max_tile.y + 1, zoom)[2:]

    return rounded_min_lon, rounded_min_lat, rounded_max_lon, rounded_max_lat

#############################################
# Generoidaan lennossa TYP file, johon koodaillaan viivan väri ja paksuus
def create_typ_file(map_type, args):

    COLOR_MAP = {
        "red":    "#AA0000",
        "blue":   "#0000FF",
        "green":  "#00AA00",
        "violet": "#8800AA",
        "black":  "#000000",
    }

    # small tiles
    if map_type == 'small_tiles':
        line_width = args.lws
        line_color=COLOR_MAP.get(args.lcs) 

    # small grid
    if map_type == 'small_grid':
        line_width = args.lwsg
        line_color=COLOR_MAP.get(args.lcsg) 

    # big tiles
    if map_type == 'big_tiles':
        line_width = args.lwb
        line_color=COLOR_MAP.get(args.lcb) 

    # big grid
    if map_type == 'big_grid':
        line_width = args.lwbg
        line_color=COLOR_MAP.get(args.lcbg) 

    # write the typ_generate.txt file
    with open('typ_generated.txt','w') as f:
        f.write(
            '\n'.join(
                [
                "[_line]",
                "Type=0x01",
                "UseOrientation=N",
                f"LineWidth={line_width}",
                'Xpm="0 0 1 0"',
                f'"1 c {line_color}"',
                "String=solid line",
                "FontStyle=NoLabel",
                "[end]"
                ]
            )
        )



# ---------------------------
def main(kml_file, zoom_level, center_point, extending_km, output_file_name, grid_only = False):
    # -----------------------------------

    def polygon_to_multilinestring(polygon):
        # Extract exterior and interior boundaries
        lines = [polygon.exterior] + list(polygon.interiors)
        # Convert to MultiLineString
        multilinestring = MultiLineString(lines)
        return multilinestring

    # lasketaan bounding boxit

    bounding_box = round_bbox_to_osm_tiles(
            center_point[0], center_point[1], 
            extending_km, extending_km, 14)


        
    # Generate grid lines
    print("gridviivaston luonti")
    multi_grid = create_tile_grid(bounding_box, zoom=zoom_level)
    
    
    if not grid_only:

        # halutaan laskea muutakin kuin pelkkä gridiviivasto

        print("parsitaan kml alueisiin")
        shapes = kml_to_shapes(kml_file, zoom_level)
        
        
        # Optimized: Union all shapes first
        print(f"Kasataan {len(shapes)} aluetta yhdeksi leikkausgeometriaksi")
        merged_shapes = unary_union(shapes)  # Combine all shapes into one
        
        # 🔥 Perform difference in one step
        print("Leikataan gridiviivat yhdellä operaatiolla")
        multi_grid = multi_grid.difference(merged_shapes)
        
    else:
        # korvataan kml:stä parsittu kuvia tyhjällä listalla
        shapes=[] 

    print("leikataan alueet bounding boxilla")
    bounding_shape = box(*bounding_box)
    shapes = [bounding_shape.intersection(polygon_to_multilinestring(x)) for x in shapes]
    multi_grid = multi_grid.intersection(bounding_shape)

    # poistetaan tyhjät elementit shapes listalta
    shapes = [x for x in shapes if not x.is_empty]
    linelist = []
    for shape in shapes:
        if isinstance(shape,LineString):
            linelist.append(shape)
        if isinstance(shape,MultiLineString):
            linelist.extend(list(shape.geoms))

    shapes = linelist

    print("kasataan KML file")
    geometry_to_kml(shapes, multi_grid, output_file=output_file_name)



# ---------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process a KML file.")
    parser.add_argument(
        "--kml",
        nargs="?",
        default="squadrats.kml",
        help="Path to the KML file (default: squadrats.kml)"
    )

    parser.add_argument(
        "--suffix",
        nargs="?",
        default="",
        help="Person name added to filename and garmin name"
    )

    # ---------------------------
    # small tile properties

    parser.add_argument(
        "--lcs",
        nargs="?",
        default="red",
        help="Line color for small tiles (red, blue, green, violet, black)"
    )

    parser.add_argument(
        "--lws",
        nargs="?",
        default=4,
        help="Line width for small tiles"
    )

    parser.add_argument(
        "--dps",
        nargs="?",
        default=30,
        help="Draw priority for small tiles, highest number gets on the top of the maps"
    )

    parser.add_argument(
        "--fis",
        nargs="?",
        default=97,
        help="Family-ID for small tiles"
    )


    # ---------------------------
    # big tile properties

    parser.add_argument(
        "--lcb",
        nargs="?",
        default="blue",
        help="Line color for big tiles (red, blue, green, violet, black)"
    )

    parser.add_argument(
        "--lwb",
        nargs="?",
        default=6,
        help="Line width for big tiles"
    )

    parser.add_argument(
        "--dpb",
        nargs="?",
        default=31,
        help="Draw priority for big tiles, highest number gets on the top of the maps"
    )

    parser.add_argument(
        "--fib",
        nargs="?",
        default=99,
        help="Family-ID for big tiles"
    )


    # ---------------------------
    # small grid map properties

    parser.add_argument(
        "--lcsg",
        nargs="?",
        default="black",
        help="Line color for small grid lines (red, blue, green, violet, black)"
    )

    parser.add_argument(
        "--lwsg",
        nargs="?",
        default=2,
        help="Line width for small grid lines"
    )

    parser.add_argument(
        "--dpsg",
        nargs="?",
        default=28,
        help="Draw priority for small grid lines, highest number gets on the top of the maps"
    )

    # ---------------------------
    # big grid map properties

    parser.add_argument(
        "--lcbg",
        nargs="?",
        default="green",
        help="Line color for big grid lines (red, blue, green, violet, black)"
    )

    parser.add_argument(
        "--lwbg",
        nargs="?",
        default=4,
        help="Line width for big grid lines"
    )

    parser.add_argument(
        "--dpbg",
        nargs="?",
        default=29,
        help="Draw priority for big grid lines, highest number gets on the top of the maps"
    )


    parser.add_argument(
        "--calculate_gridlines",
        action="store_true",
        help = "Use if you want to calculate gridlines"
    )



    args = parser.parse_args()

    # draw-priority on oltava välillä 0-31 tai muuten tekee ihan mitä sattuu
    if max([args.dps, args.dpb, args.dpsg, args.dpgb]) > 31 or min([args.dps, args.dpb, args.dpsg, args.dpgb]) < 0:
        print("Parameter draw-priority must be between 0-31, check configuration")
        sys.exit()




    kml_file = args.kml
    suffix = args.suffix

    print(f"Processing KML file: {kml_file}")


    center_point = [23.7636959, 61.5]  # Tampere
    # center_point = [23.87336, 61.47317] # Kaukajärvi
    # center_point = [24.34371, 61.67986] # Orivesi
    # center_point =[23.54808, 61.71656]   #kyrönlahti
    # center_point = [24.072,61.4692] #kirkkojärvin kangasala
    # center_point = [23.8410,61.4763] #nekala
    # center_point = [23.91804,61.52993] # Niihaman lahti
    # center_point = [23.95257, 61.45039]  # itäpuoli
    # center_point =[23.59057,61.47413] #rajasalmen silta 
    # center_point = [-15.5944, 27.9603]   # Gran Canaria
    # center_point = [23.75124, 61.31184]  #lempäälä
    # center_point = [24.9060031, 60.2411758]  # Helsinki
    #center_point = [2.9430, 39.6115]  # Mallorca
    
    
    # small_extending_km = 10 # 10 kilometriä toimii brouterin kanssa
    # small_extending_km = 20  
    small_extending_km = 15
    big_extending_km = 100



    # temp file names

    small_output_file_name = 'small_tiles'
    big_output_file_name = 'big_tiles'
    small_grid_file_name = 'small_grid'
    big_grid_file_name = 'big_grid'

    ################################################
    # KML tiedostojen laskenta geometrioista
    ################################################

    # pikkuruutujen laskenta
    print("LASKETAAN PIENET RUUDUT")
    main(kml_file, 17, center_point, small_extending_km, small_output_file_name)
    
    # isojen ruutujen laskenta
    print("LASKETAAN ISO RUUDUT")
    main(kml_file, 14, center_point, big_extending_km, big_output_file_name)


    if args.calculate_gridlines:
        # pienien ruutujen gridiviivaston laskenta
        print("LASKETAAN PIENET GRIDIVIIVAT")
        main(kml_file, 17, center_point, small_extending_km, small_grid_file_name, grid_only = True)

        print("LASKETAAN ISOT GRIDIVIIVAT")
        # ison ruutujen gridiviivaston laskenta
        main(kml_file, 14, center_point, big_extending_km, big_grid_file_name, grid_only = True)




    ##########################3
    # KML => OSM
    ##########################3


    # ajetaan gpsbabelilla KML tiedoston muunnos OSM fileeksi
    result = subprocess.run(["gpsbabel", 
                            "-i",
                            "kml",
                            "-f",
                            f"{small_output_file_name}.kml",
                            "-o",
                            "osm,tag=highway:primary",
                            "-F",
                            "small_missing_tiles.osm"
                            ], capture_output=True, text=True)
    print(result.stdout)
    print(result.stderr)

    # ajetaan gpsbabelilla KML tiedoston muunnos OSM fileeksi
    result = subprocess.run(["gpsbabel", 
                            "-i",
                            "kml",
                            "-f",
                            f"{big_output_file_name}.kml",
                            "-o",
                            "osm,tag=highway:primary",
                            "-F",
                            "big_missing_tiles.osm"
                            ], capture_output=True, text=True)
    print(result.stdout)
    print(result.stderr)


    if args.calculate_gridlines:
        # ajetaan gpsbabelilla KML tiedoston muunnos OSM fileeksi
        result = subprocess.run(["gpsbabel", 
                                "-i",
                                "kml",
                                "-f",
                                f"{small_grid_file_name}.kml",
                                "-o",
                                "osm,tag=highway:primary",
                                "-F",
                                "small_grid.osm"
                                ], capture_output=True, text=True)
        print(result.stdout)
        print(result.stderr)

        # ajetaan gpsbabelilla KML tiedoston muunnos OSM fileeksi
        result = subprocess.run(["gpsbabel", 
                                "-i",
                                "kml",
                                "-f",
                                f"{big_grid_file_name}.kml",
                                "-o",
                                "osm,tag=highway:primary",
                                "-F",
                                "big_grid.osm"
                                ], capture_output=True, text=True)
        print(result.stdout)
        print(result.stderr)










    ##########################
    # garmin tiedoston luonti
    ##########################

    datestr = (
        datetime.datetime.now().strftime("%Y")+
        datetime.datetime.now().strftime("%m")+
        datetime.datetime.now().strftime("%d")
    )
    # luodaan garmin img fileet mkgmap:lla
    # arvotaan mapname jokaiselle kartalle
    mapname_small_tiles = str(random.randint(1000000, 9999999)+40000000)
    mapname_small_grid = str(random.randint(1000000, 9999999)+50000000)
    mapname_big_tiles = str(random.randint(1000000, 9999999)+60000000)
    mapname_big_grid = str(random.randint(1000000, 9999999)+70000000)


    ### SMALL tiles
    # ----------------------

    print("GENERATING GARMIN MAP FILES")

    create_typ_file(map_type='small_tiles', args=args)

    result = subprocess.run(['mkgmap',
                            f'--family-id={args.fis}',
                            '--product-id=1',
                            '--latin1',
                            f'--draw-priority={args.dps}',
                            '--style-file=mkgmap_tiles.style',
                            '--transparent',
                            '--gmapsupp',
                            '--output-dir=output',
                            f'--mapname={mapname_small_tiles}',
                            f'--description={suffix}-small-tiles-{datestr}',
                            'typ_generated.txt',
                            'small_missing_tiles.osm'
                            ], capture_output=True, text=True)
    print(result.stdout)
    print(result.stderr)


    result = subprocess.run(['mv', 
                            'output/gmapsupp.img',
                            f'output/{suffix}-small-tiles-{datestr}.img',
                            ], capture_output=True, text=True)
    print(result.stdout)
    print(result.stderr)



    ### BIG tiles
    # ----------------------


    create_typ_file(map_type='big_tiles', args=args)

    result = subprocess.run(['mkgmap',
                            f'--family-id={args.fib}',
                            '--product-id=1',
                            '--latin1',
                            f'--draw-priority={args.dpb}',
                            '--style-file=mkgmap_tiles.style',
                            '--transparent',
                            '--gmapsupp',
                            '--output-dir=output',
                            f'--mapname={mapname_big_tiles}',
                            f'--description={suffix}-big-tiles-{datestr}',
                            'typ_generated.txt',
                            'big_missing_tiles.osm'
                            ], capture_output=True, text=True)
    print(result.stdout)
    print(result.stderr)


    result = subprocess.run(['mv', 
                            'output/gmapsupp.img',
                            f'output/{suffix}-big-tiles-{datestr}.img',
                            ], capture_output=True, text=True)
    print(result.stdout)
    print(result.stderr)


    if args.calculate_gridlines:

        ### SMALL grid lines
        # ----------------------

        create_typ_file(map_type='small_grid', args=args)

        result = subprocess.run(['mkgmap',
                                '--family-id=98',
                                '--product-id=1',
                                '--latin1',
                                f'--draw-priority={args.dpsg}',
                                '--style-file=mkgmap_grid.style',
                                '--transparent',
                                '--gmapsupp',
                                '--output-dir=output',
                                f'--mapname={mapname_small_grid}',
                                f'--description={suffix}-small-grid-{datestr}',
                                'typ_generated.txt',
                                'small_grid.osm'
                                ], capture_output=True, text=True)
        print(result.stdout)
        print(result.stderr)


        result = subprocess.run(['mv', 
                                'output/gmapsupp.img',
                                f'output/{suffix}-small-grid-{datestr}.img',
                                ], capture_output=True, text=True)
        print(result.stdout)
        print(result.stderr)



        ### BIG grid lines
        # ----------------------

        create_typ_file(map_type='big_grid', args=args)

        result = subprocess.run(['mkgmap',
                                '--family-id=100',
                                '--product-id=1',
                                '--latin1',
                                f'--draw-priority={args.dpbg}',
                                '--style-file=mkgmap_grid.style',
                                '--transparent',
                                '--gmapsupp',
                                '--output-dir=output',
                                f'--mapname={mapname_big_grid}',
                                f'--description={suffix}-big-grid-{datestr}',
                                'typ_generated.txt',
                                'big_grid.osm'
                                ], capture_output=True, text=True)
        print(result.stdout)
        print(result.stderr)


        result = subprocess.run(['mv', 
                                'output/gmapsupp.img',
                                f'output/{suffix}-big-grid-{datestr}.img',
                                ], capture_output=True, text=True)
        print(result.stdout)
        print(result.stderr)




    """

    KML tiedostosta eteenpäin kohden Garmin IMG filettä
    
    # KML => OSM tiedostoksi
    gpsbabel -i kml -f small_output.kml -o osm,tag=highway:primary -F small_missing_tiles.osm
    gpsbabel -i kml -f big_output.kml -o osm,tag=highway:primary -F big_missing_tiles.osm

    # OSM => Garmin IMG file

    mkgmap --read-config=config.txt --mapname=49847386 --description="SMALL_tiles" typ.txt small_missing_tiles.osm 
    mv output/gmapsupp.img output/gmapsupp-small.img
    
    mkgmap -c config.txt --mapname=59847386 --description="BIG_tiles" typ.txt big_missing_tiles.osm 
    mv output/gmapsupp.img output/gmapsupp-big.img


    


    """

