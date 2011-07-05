import httplib
import Image, ImageEnhance
from StringIO import StringIO
from pn.ws import settings
 
POSITION = ('LEFTTOP', 'RIGHTTOP', 'CENTER', 'LEFTBOTTOM', 'RIGHTBOTTOM')  
PADDING = 5

def reduce_opacity(im, opacity):  
    """Returns an image with reduced opacity."""  
    assert opacity >= 0 and opacity <= 1
    if im.mode != 'RGBA':  
        im = im.convert('RGBA')  
    else:  
        im = im.copy()  
        alpha = im.split()[3]  
        alpha = ImageEnhance.Brightness(alpha).enhance(opacity)  
        im.putalpha(alpha)  
    return im

def watermark(imagefile, markfile, position=POSITION[4], opacity=1):  
    """Adds a watermark to an image."""     
    im = Image.open(imagefile)
    mark = Image.open(markfile)    
    if opacity < 1:  
        mark = reduce_opacity(mark, opacity)  
    #if im.mode != 'RGBA':
    im = im.convert('RGBA')
    layer = Image.new('RGBA', im.size, (0, 0, 0, 0))
    if position == 'title':
        for y in range(0, im.size[1], mark.size[1]):
            for x in range(0, im.size[0], mark.size[0]):
                layer.paste(mark, (x, y))
    elif position == 'scale':
        ratio = min(float(im.size[0]) / mark.size[0], float(im.size[1]) / mark.size[1])
        w = int(mark.size[0] * ratio)
        h = int(mark.size[1] * ratio)
        mark = mark.resize((w, h))
        layer.paste(mark, ((im.size[0] - w) / 2, (im.size[1] - h) / 2))
    elif position == POSITION[0]:
        #lefttop  
        position = (PADDING, PADDING)
        layer.paste(mark, position)  
    elif position == POSITION[1]:  
        #righttop  
        position = (im.size[0] - mark.size[0] - PADDING, PADDING)  
        layer.paste(mark, position)  
    elif position == POSITION[2]:  
        #center  
        position = ((im.size[0] - mark.size[0]) / 2, (im.size[1] - mark.size[1]) / 2)  
        layer.paste(mark, position)  
    elif position == POSITION[3]:  
        #left bottom  
        position = (PADDING, im.size[1] - mark.size[1] - PADDING,)  
        layer.paste(mark, position)  
    else:  
        #right bottom (default)  
        position = (im.size[0] - mark.size[0] - PADDING, im.size[1] - mark.size[1] - PADDING,)  
        layer.paste(mark, position)  
           
        #composite the watermark with the layer
    return Image.composite(layer, im, layer)
     
class ImageFileIO(StringIO):

    ##
    # Adds buffering to a stream file object, in order to
    # provide <b>seek</b> and <b>tell</b> methods required
    # by the <b>Image.open</b> method. The stream object must
    # implement <b>read</b> and <b>close</b> methods.
    #
    # @param fp Stream file handle.
    # @see Image#open

    def __init__(self, fp):
        data = fp.read()
        StringIO.__init__(self, data)     

