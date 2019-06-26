import fitz
import re
from page_plot import plot_page



pdf_file = 'D:/WorkSpace/TestSpace/PDFTranslation/examples/example.pdf'

doc = fitz.open(pdf_file)

'''
    # get all text
    # for page in doc:
    #     blocks = page.getTextBlocks()
    #     blocks = sorted(blocks, key = itemgetter(1, 0))
    #     for block in blocks:
    #         print(block)

    # get all text
    # for page in doc:
    #     blocks = page.getText('dict')
    #     print(blocks)

    # for page in doc:
    #     for xref in page._getContents():
    #         print(doc._getXrefStream(xref).decode())

    # get images
    # [xref, smask, width, height, bpc, colorspace, alt. colorspace, name, filter]
    # for i in range(len(doc)):
    #     for img in doc.getPageImageList(i):
    #         print(img)


    # checkXO = r"/Type(?= */XObject)"       # finds "/Type/XObject"   
    # checkIM = r"/Subtype(?= */Image)"      # finds "/Subtype/Image"
    # lenXREF = doc._getXrefLength()
    # for i in range(1, lenXREF):            # scan through all objects
    #     try:
    #         text = doc._getXrefString(i)   # PDF object definition string
    #     except:
    #         print("xref %i " % i + doc._getGCTXerrmsg())
    #         continue                       # skip the error
            
    #     isXObject = re.search(checkXO, text)    # tests for XObject
    #     isImage   = re.search(checkIM, text)    # tests for Image
    #     is_an_image = isXObject and isImage     # both must be True for an image

    #     print(text)
'''


# for page in doc:
#     layout = page.getText('dict')
#     plot_page(layout)
#     break

page = doc[0]
layout = page.getText('dict')
layout['blocks'].sort(key=lambda item: (item['bbox'][1], item['bbox'][0]))

# original layout
plot_page(layout)

# combine lines in a block
combined_lines = layout['blocks'].copy()


    
