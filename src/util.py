import matplotlib.patches as patches


# border margin
DM = 1.0

# inch to point
ITP = 72.0

def getColor(i):
	colors = ['r', 'g', 'b', 'c', 'm', 'y']
	return colors[int(i)%len(colors)]

def rectangle(bbox, linewidth=0.5, linecolor='r', fillcolor='none'):
	x0, y0, x1, y1 = bbox
	return patches.Rectangle((x0, y0), x1-x0, y1-y0, linewidth=linewidth, edgecolor=linecolor, facecolor=fillcolor)

def is_end_sentence(text):
	'''simple rule to check the completence of text
	   - sentence delimiter at the end of a sentence
	'''
	text = text.strip()
	if not text:
		return True # keep empy line

	return text[-1].endswith(('.', '?', '!', ':'))

def is_start_sentence(text):
	text = text.strip()
	if not text:
		return True

	# generally not starts with a digit 
	elif text[0].isdigit():
		return False		

	# not starts with a low case alphabet
	else:
		return not text[0].islower() # conservatively

def is_vertical_aligned(bbox1, bbox2, horizontal=True, factor=0.5):
	'''check whether two boxes have enough intersection in vertical direction.
	   vertical direction is perpendicular to reading direction

	   an enough intersection is defined based on the minimum width of two boxes:
	   L1+L2-L>factor*min(L1,L2)
	'''
	if horizontal: # reading direction: x
		L1 = bbox1[2]-bbox1[0]
		L2 = bbox2[2]-bbox2[0]
		L = max(bbox1[2], bbox2[2]) - min(bbox1[0], bbox2[0])
	else:
		L1 = bbox1[3]-bbox1[1]
		L2 = bbox2[3]-bbox2[1]
		L = max(bbox1[3], bbox2[3]) - min(bbox1[1], bbox2[1])

	return L1+L2-L>factor*min(L1,L2)


def is_horizontal_aligned(bbox1, bbox2, horizontal=True):
	'''it is opposite to vertical align situation'''
	return is_vertical_aligned(bbox1, bbox2, not horizontal)
