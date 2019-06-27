import matplotlib.patches as patches
import matplotlib.pyplot as plt

def getColor(i):
	colors = ['r', 'g', 'b', 'c', 'm', 'y']
	return colors[int(i)%len(colors)]

def rectangle(bbox, linewidth=0.5, linecolor='r', fillcolor='none'):
	x0, y0, x1, y1 = bbox
	return patches.Rectangle((x0, y0), x1-x0, y1-y0, linewidth=linewidth, edgecolor=linecolor, facecolor=fillcolor)
