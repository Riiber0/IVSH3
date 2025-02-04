import config_dash

def get_tile_matriz(tileList):
    tileMatriz =  {}
    lineCount = -1

    lastTile = -2
    for tile in tileList:
        if tile - lastTile > 1:
            lineCount += 1
            tileMatriz[lineCount] = [tile]

        else:
            tileMatriz[lineCount].append(tile)

        lastTile = tile

    return tileMatriz, lineCount

def linePriority(tileList):

    tileMatriz =  {}
    lineCount = -1

    lastTile = -2
    for tile in tileList:
        if tile - lastTile > 1:
            lineCount += 1
            tileMatriz[lineCount] = [tile]

        else:
            tileMatriz[lineCount].append(tile)

        lastTile = tile

    lowP = tileMatriz[0] + tileMatriz[lineCount]
    highP = []
    for i in range(1, lineCount+1):
        highP += tileMatriz[i]

    return lowP ,highP

def outer_zone_percentage(tileList, total_tiles, zone_size):
    current_coverage = len(tileList)/total_tiles * 100
    zone_tiles = []
    new_list = tileList.copy()

    while current_coverage < zone_size:
        tile_m, line_count = get_tile_matriz(new_list)

        for i in range(0, len(tile_m)):
            if i == 0:
                for tile in tile_m:
                    if tile > config_dash.TILE_LINE_SIZE:
                        zone_tiles.append(tile - config_dash.TILE_LINE_SIZE)

            elif i == line_count:
                for tile in tile_m:
                    if tile + config_dash.TILE_LINE_SIZE < total_tiles:
                        zone_tiles.append(tile + config_dash.TILE_LINE_SIZE)

            if tile_m[i][0] > 1:
                zone_tiles.append(tile_m[i][0] - 1)

            if tile_m[i][len(tile_m[i])-1] < total_tiles:
                zone_tiles.append(tile_m[i][0] + 1)

        new_list += [tile for tile in zone_tiles if tile not in new_list]
        new_list.sort()
        current_coverage = len(new_list)/total_tiles * 100

    zone_tiles = list(set(zone_tiles))
    zone_tiles.sort()

    return zone_tiles

def outer_zone_fixed(tileList, total_tiles, zone_size):
    current_coverage = len(tileList)/total_tiles * 100
    zone_tiles = []
    new_list = tileList.copy()

    for i in range(0, zone_size):
        tile_m, line_count = get_tile_matriz(new_list)

        for i in range(0, len(tile_m)):
            if i == 0:
                for tile in tile_m:
                    if tile > config_dash.TILE_LINE_SIZE:
                        zone_tiles.append(tile - config_dash.TILE_LINE_SIZE)

            elif i == line_count:
                for tile in tile_m:
                    if tile + config_dash.TILE_LINE_SIZE < total_tiles:
                        zone_tiles.append(tile + config_dash.TILE_LINE_SIZE)

            if tile_m[i][0] > 1:
                zone_tiles.append(tile_m[i][0] - 1)

            if tile_m[i][len(tile_m[i])-1] < total_tiles:
                zone_tiles.append(tile_m[i][0] + 1)

        new_list += [tile for tile in zone_tiles if tile not in new_list]
        new_list.sort()
        current_coverage = len(new_list)/total_tiles * 100

    zone_tiles = list(set(zone_tiles))
    zone_tiles.sort()

    return zone_tiles

if __name__ == '__main__':
    l1 = [  48, 49, 50, 51, 52,
            68, 69, 70, 71, 72,
            87, 88, 89, 90, 91, 92,
            107, 108, 109, 110, 111, 112,
            128, 129, 130, 131, 132,
            148, 149, 150, 151, 152,]

    print(linePriority(l1))
    r = outer_zone_percentage(l1, 200, 40)
    print(r)
    print(len(r)+len(l1))

    r = outer_zone_fixed(l1, 200, 1)
    print(r)
    print(len(r)+len(l1))
