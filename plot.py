import matplotlib.patches as patches
import matplotlib.pyplot as plt

def getColor(i):
	colors = ['r', 'g', 'b', 'c', 'm', 'y']
	return colors[int(i)%len(colors)]

def Rectangle(bbox, linewidth=0.5, linecolor='r', fillcolor='none'):
	x0, y0, x1, y1 = bbox
	return patches.Rectangle((x0, y0), x1-x0, y1-y0, linewidth=linewidth, edgecolor=linecolor, facecolor=fillcolor)

def plot_page(pdf):
	width, height = pdf['width'], pdf['height']
	blocks = pdf['blocks']

	# figure
	fig, ax = plt.subplots(figsize=(5.0, 5*height/width))
	ax.set_xticks([])
	ax.set_yticks([])
	ax.set_xlim(0, width)
	ax.set_ylim(0, height)
	ax.xaxis.set_ticks_position('top')
	ax.yaxis.set_ticks_position('left')
	ax.invert_yaxis()
	ax.set_aspect('equal')	

	# plot block position
	for i, block in enumerate(blocks):		

		# lines in current block
		for line in block.get('lines', []):
			patch = Rectangle(line['bbox'], linecolor='w', fillcolor=getColor(i))
			ax.add_patch(patch)

		# block border
		patch = Rectangle(block['bbox'], linecolor='k')
		ax.add_patch(patch)

	plt.show()


if __name__ == '__main__':

	pdf = {
		'width': 612.0, 
		'height': 792.0, 
		'blocks': [
			{
				'type': 0, 
				'bbox': (90.0479965209961, 38.060028076171875, 185.92503356933594, 49.10002517700195), 
				'lines': [
					{
						'wmode': 0, 
						'dir': (1.0, 0.0), 
						'bbox': (90.0479965209961, 38.060028076171875, 185.92503356933594, 49.10002517700195), 
						'spans': [
							{
								'size': 11.039999961853027, 
								'flags': 0, 
								'font': 'Calibri', 
								'text': 'This is a page header '
							}
						]
					}
				]
			}, 

			{
				'type': 0, 'bbox': (414.4100036621094, 731.615966796875, 524.7150268554688, 742.656005859375), 
				'lines': [
					{
						'wmode': 0, 'dir': (1.0, 0.0), 'bbox': (414.4100036621094, 731.615966796875, 488.4450378417969, 742.656005859375), 
						'spans': [
							{
								'size': 11.039999961853027, 
								'flags': 0, 
								'font': 'Calibri', 
								'text': 'Unrestricted 1 | '
							}
						]
					}, 

					{
						'wmode': 0, 'dir': (1.0, 0.0), 'bbox': (522.219970703125, 731.615966796875, 524.7150268554688, 742.656005859375), 
						'spans': [{'size': 11.039999961853027, 'flags': 0, 'font': 'Calibri', 'text': ' '}]
					}, 

					{
						'wmode': 0, 'dir': (1.0, 0.0), 'bbox': (488.3500061035156, 731.615966796875, 519.2509155273438, 742.656005859375), 
						'spans': [{'size': 11.039999961853027, 'flags': 0, 'font': 'Calibri', 'text': 'P a g e'}]
					}
				]
			}, 

			{
				'type': 0, 'bbox': (90.0479965209961, 744.8159790039062, 92.54303741455078, 755.8560180664062), 
				'lines': [
					{
						'wmode': 0, 'dir': (1.0, 0.0), 'bbox': (90.0479965209961, 744.8159790039062, 92.54303741455078, 755.8560180664062), 
						'spans': [{'size': 11.039999961853027, 'flags': 0, 'font': 'Calibri', 'text': ' '}]
					}
				]
			}, 

			{
				'type': 0, 'bbox': (92.09000396728516, 75.28498840332031, 103.1300048828125, 232.3900146484375), 
				'lines': [
					{
						'wmode': 0, 'dir': (-3.999999886872274e-09, -1.0), 'bbox': (92.09000396728516, 75.28498840332031, 103.1300048828125, 232.3900146484375), 
						'spans': [{'size': 11.039999961853027, 'flags': 0, 'font': 'Calibri', 'text': 'Convert a PDF to a DOC in seconds '}]
					}
				]
			}, 

			{
				'type': 0, 'bbox': (135.88999938964844, 74.06002807617188, 500.1814880371094, 152.3300018310547), 
				'lines': [
					{
						'wmode': 0, 'dir': (1.0, 0.0), 'bbox': (135.88999938964844, 74.06002807617188, 494.2597961425781, 85.10002899169922), 
						'spans': [{'size': 11.039999961853027, 'flags': 0, 'font': 'Calibri', 'text': 'With just a simple drag-and-drop, you can convert PDF to Word within seconds. '}]
					}, 

					{
						'wmode': 0, 'dir': (1.0, 0.0), 'bbox': (135.88999938964844, 87.50003051757812, 482.20501708984375, 98.54003143310547), 
						'spans': [{'size': 11.039999961853027, 'flags': 0, 'font': 'Calibri', 'text': 'There’s neither file size limit nor even the need to register to use our service. '}]
					},

					{
						'wmode': 0, 'dir': (1.0, 0.0), 'bbox': (135.88999938964844, 100.93997192382812, 138.38504028320312, 111.97997283935547), 
						'spans': [{'size': 11.039999961853027, 'flags': 0, 'font': 'Calibri', 'text': ' '}]
					}, 

					{
						'wmode': 0, 'dir': (1.0, 0.0), 'bbox': (135.88999938964844, 114.37997436523438, 500.1814880371094, 125.41997528076172), 
						'spans': [{'size': 11.039999961853027, 'flags': 0, 'font': 'Calibri', 'text': 'We care about privacy. All files will be deleted from our servers forever after one '}]
					}, 

					{
						'wmode': 0, 'dir': (1.0, 0.0), 'bbox': (135.88999938964844, 127.85000610351562, 454.6050109863281, 138.88999938964844), 
						'spans': [{'size': 11.039999961853027, 'flags': 0, 'font': 'Calibri', 'text': 'hour. To know more about how much we care, read our privacy policy. '}]
					}, 

					{
						'wmode': 0, 'dir': (1.0, 0.0), 'bbox': (135.88999938964844, 141.29000854492188, 138.38504028320312, 152.3300018310547), 
						'spans': [{'size': 11.039999961853027, 'flags': 0, 'font': 'Calibri', 'text': ' '}]
					}
				]
			}, 

			{
				'type': 0, 'bbox': (394.010009765625, 315.5799865722656, 396.5050354003906, 326.6199951171875), 
				'lines': [
					{
						'wmode': 0, 'dir': (1.0, 0.0), 'bbox': (394.010009765625, 315.5799865722656, 396.5050354003906, 326.6199951171875), 
						'spans': [{'size': 11.039999961853027, 'flags': 0, 'font': 'Calibri', 'text': ' '}]
					}
				]
			}, 

			{
				'type': 0, 'bbox': (90.0479965209961, 326.1400146484375, 92.54303741455078, 337.1800231933594), 
				'lines': [
					{
						'wmode': 0, 'dir': (1.0, 0.0), 'bbox': (90.0479965209961, 326.1400146484375, 92.54303741455078, 337.1800231933594), 
						'spans': [{'size': 11.039999961853027, 'flags': 0, 'font': 'Calibri', 'text': ' '}]
					}
				]
			}, 

			{
				'type': 0, 'bbox': (90.0479965209961, 351.82000732421875, 461.32501220703125, 362.8600158691406), 
				'lines': [
					{
						'wmode': 0, 'dir': (1.0, 0.0), 'bbox': (90.0479965209961, 351.82000732421875, 131.42503356933594, 362.8600158691406), 
						'spans': [{'size': 11.039999961853027, 'flags': 0, 'font': 'Calibri', 'text': 'Features '}]
					}, 

					{
						'wmode': 0, 'dir': (1.0, 0.0), 'bbox': (158.47000122070312, 351.82000732421875, 315.57501220703125, 362.8600158691406), 
						'spans': [{'size': 11.039999961853027, 'flags': 0, 'font': 'Calibri', 'text': 'Convert a PDF to a DOC in seconds '}]
					}, 

					{
						'wmode': 0, 'dir': (1.0, 0.0), 'bbox': (325.0799865722656, 351.82000732421875, 461.32501220703125, 362.8600158691406), 
						'spans': [{'size': 11.039999961853027, 'flags': 0, 'font': 'Calibri', 'text': 'Magic conversion in the cloud '}]
					}
				]
			}, 

			{
				'type': 0, 'bbox': (90.0479965209961, 361.9119873046875, 316.2950134277344, 402.54095458984375), 
				'lines': [
					{
						'wmode': 0, 'dir': (1.0, 0.0), 'bbox': (90.0479965209961, 365.739990234375, 143.6650390625, 376.7799987792969), 
						'spans': [{'size': 11.039999961853027, 'flags': 0, 'font': 'Calibri', 'text': 'Description '}]
					}, 

					{
						'wmode': 0, 'dir': (1.0, 0.0), 'bbox': (158.47000122070312, 361.9119873046875, 308.96722412109375, 377.0809631347656), 
						'spans': [{'size': 11.039999961853027, 'flags': 0, 'font': 'Helvetica', 'text': 'It is seriously ridiculously easy '}]
					}, 

					{
						'wmode': 0, 'dir': (1.0, 0.0), 'bbox': (158.47000122070312, 374.6519775390625, 294.7808532714844, 389.8209533691406), 
						'spans': [{'size': 11.039999961853027, 'flags': 0, 'font': 'Helvetica', 'text': 'with our tool to convert files '}]
					}, 

					{
						'wmode': 0, 'dir': (1.0, 0.0), 'bbox': (158.47000122070312, 387.3719787597656, 316.2950134277344, 402.54095458984375), 
						'spans': [
							{'size': 11.039999961853027, 'flags': 0, 'font': 'Helvetica', 'text': 'online. Try it and you will love it.'}, 
							{'size': 11.039999961853027, 'flags': 0, 'font': 'Calibri', 'text': ' '}
						]
					}
				]
			}, 

			{
				'type': 0, 'bbox': (325.0799865722656, 361.9119873046875, 523.0381469726562, 415.0209655761719), 
				'lines': [
					{
						'wmode': 0, 'dir': (1.0, 0.0), 'bbox': (325.0799865722656, 361.9119873046875, 499.7768859863281, 377.0809631347656), 
						'spans': [{'size': 11.039999961853027, 'flags': 0, 'font': 'Helvetica', 'text': 'We have many servers in the cloud '}]
					}, 

					{
						'wmode': 0, 'dir': (1.0, 0.0), 'bbox': (325.0799865722656, 374.6519775390625, 512.2189331054688, 389.8209533691406), 
						'spans': [{'size': 11.039999961853027, 'flags': 0, 'font': 'Helvetica', 'text': 'which do nothing else than converting '}]
					}, 

					{
						'wmode': 0, 'dir': (1.0, 0.0), 'bbox': (325.0799865722656, 387.3719787597656, 523.0381469726562, 402.54095458984375), 
						'spans': [{'size': 11.039999961853027, 'flags': 0, 'font': 'Helvetica', 'text': 'PDF to Word files. So, lean back and let '}]
					}, 

					{
						'wmode': 0, 'dir': (1.0, 0.0), 'bbox': (325.0799865722656, 399.85198974609375, 414.9850158691406, 415.0209655761719), 
						'spans': [
							{'size': 11.039999961853027, 'flags': 0, 'font': 'Helvetica', 'text': 'them do the work.'}, 
							{'size': 11.039999961853027, 'flags': 0, 'font': 'Calibri', 'text': ' '}
						]
					}
				]
			}, 

			{
				'type': 0, 'bbox': (90.0479965209961, 417.1199951171875, 92.54303741455078, 428.1600036621094), 
				'lines': [
					{
						'wmode': 0, 'dir': (1.0, 0.0), 'bbox': (90.0479965209961, 417.1199951171875, 92.54303741455078, 428.1600036621094), 
						'spans': [{'size': 11.039999961853027, 'flags': 0, 'font': 'Calibri', 'text': ' '}]
					}
				]
			}, 

			{
				'type': 0, 'bbox': (487.6300048828125, 442.55999755859375, 524.7150268554688, 453.6000061035156), 
				'lines': [
					{
						'wmode': 0, 'dir': (1.0, 0.0), 'bbox': (487.6300048828125, 442.55999755859375, 524.7150268554688, 453.6000061035156), 
						'spans': [{'size': 11.039999961853027, 'flags': 18, 'font': 'Calibri,BoldItalic', 'text': 'Sign off '}]
					}
				]
			}, 

			{
				'type': 0, 'bbox': (501.30999755859375, 468.0199890136719, 524.7150268554688, 479.05999755859375), 
				'lines': [
					{
						'wmode': 0, 'dir': (1.0, 0.0), 'bbox': (501.30999755859375, 468.0199890136719, 524.7150268554688, 479.05999755859375), 
						'spans': [{'size': 11.039999961853027, 'flags': 18, 'font': 'Calibri,BoldItalic', 'text': 'date '}]
					}
				]
			}, 

			{
				'type': 1, 'bbox': (135.89999389648438, 152.5699920654297, 393.7699890136719, 323.7699890136719), 'width': 943, 'height': 626, 'ext': 'png', 'image': b'\x89PNG'
			}
		]
	}

	plot_page(pdf)
