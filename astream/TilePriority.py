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

if __name__ == '__main__':
    l1 = [  48, 49, 50, 51, 52,
            68, 69, 70, 71, 72,
            87, 88, 89, 90, 91, 92,
            107, 108, 109, 110, 111, 112,
            128, 129, 130, 131, 132,
            148, 149, 150, 151, 152,]

    print(linePriority(l1))
