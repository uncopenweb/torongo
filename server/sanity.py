'''Attempt to sanitize strings in objects to avoid XSS and other foolishness

HTML parts adapted from http://stackoverflow.com/questions/16861/sanitising-user-input-using-python


'''

import re
from urlparse import urljoin
from BeautifulSoup import BeautifulSoup, Comment

def sanitize(obj, html=False):
    '''Walk an object sanitizing each part.'''
    if type(obj) == dict:
        for key in obj.keys():
            obj[key] = sanitize(obj[key], key.endswith('HTML'))
    elif type(obj) == list:
        for i,val in enumerate(obj):
            obj[i] = sanitize(obj[i], html)
    elif type(obj) in [str, unicode]:
        if html:
            try:
                obj = sanitizeHTML(obj)
            except:
                raise ValueError
        else:
            obj = sanitizeText(obj)

    return obj

# this should not replace & in an entity
targets = re.compile('(&(?!([a-zA-Z0-9]+|#[0-9]+|#x[0-9a-fA-F]+);)|[<>"\'])')
# recommended by Mark Pilgrim
replacements = { '&': '&amp;',
                 '<': '&lt;',
                 '>': '&gt;',
                 '"': '&quot;',
                 "'": '&#39;' }

def sanitizeTextHelper(match):
    '''Handle simple markup embeded in strings.'''
    return replacements[match.group(1)]
        
def sanitizeText(txt):
    '''Sanitize non-html strings'''
    return targets.sub(sanitizeTextHelper, txt)
    
validTags = set((
    'a', 'abbr', 'address', 'article', 'aside', 'audio', 
    'b', 'big', 'blockquote', 'br', 
    'caption', 'cite', 'code', 'col','colgroup', 
    'dd', 'del', 'dfn', 'dir', 'div', 'dl', 'dt', 
    'em', 
    'figcaption', 'figure', 'font',
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'hr', 
    'i', 'img', 'ins', 
    'kbd', 
    'legend', 'li', 
    'ol', 
    'p', 'pre', 
    'q', 
    's', 'samp', 'small', 'span', 'strike', 'strong', 'sub', 'sup', 
    'table', 'tbody', 'td', 'tfoot', 'th', 'thead','tr', 'tt', 
    'u', 'ul', 
    'var',
    ))

validAttrs = set((
    'alt',
    'cellpadding', 'cellspacing', 'color', 'cols', 'colspan', 
    'datetime', 'dir', 
    'face', 'frame', 
    'headers', 'height', 'hreflang', 'hspace', 
    'lang', 
    'name', 'noshade', 'nowrap', 
    'rel', 'rev', 'rows', 'rowspan', 'rules', 
    'scope', 'size', 'span', 'start', 'summary', 
    'title', 'type', 
    'valign', 'vspace',
    'width',
    ))
    
urlAttrs = set(('href', 'src'))

validUrl = re.compile(r'^https?://')

# I'm trying to include the "safe" ones that Rich Text editor or M$ seem to use
validStyles = set((
    'background',
    'color', 
    'font-family', 
    'font-size', 
    'font-style', 
    'font-variant', 
    'font-weight', 
    'letter-spacing',
    'line-height', 
    'orphans', 
    'text-align',
    'text-indent', 
    'white-space', 
    'widows', 
    'word-spacing',
))

# I'm allowing only simple values or rgb()
stylePattern = re.compile("([-a-z]+)\s*:\s*([a-z0-9' #%]+|rgb\s*\([0-9, ]+\))\s*;")

def sanitizeHTML(value):
    soup = BeautifulSoup(value)
    for comment in soup.findAll(text=lambda text: isinstance(text, Comment)):
        # Get rid of comments
        comment.extract()
    for tag in soup.findAll(True):
        if tag.name not in validTags:
            tag.hidden = True
        attrs = tag.attrs
        tag.attrs = []
        for attr, val in attrs:
            if attr in validAttrs:
                tag.attrs.append((attr, sanitizeText(val)))
            elif attr in urlAttrs and validUrl.match(val):
                tag.attrs.append((attr, val))
            elif attr == 'style':
                styles = [ (cssAttr, cssVal) for cssAttr, cssVal in stylePattern.findall(val)
                           if cssAttr in validStyles ]
                if styles:
                    val = ';'.join('%s:%s' % style for style in styles)
                    tag.attrs.append((attr, val))
                
    return soup.renderContents().decode('utf8')

if __name__ == '__main__':
    t1 = { 'a': 1,
           'b': [ 2, 3 ],
           'c': 'hi there',
           'd': '1 < 2 &amp; 3 &gt; 4 > 5 " 6 \' foo \'',
           'eHTML': '<b>FOO</b>',
           'fHTML': '<script type="text/javascript">alert("what?");</script>',
           'gHTML': "<span class=\"Apple-style-span\" style=\"border-collapse: separate; color: rgb(0, 0, 0); font-family: 'Times New Roman'; font-style: normal; font-variant: normal; font-weight: normal; letter-spacing: normal; line-height: normal; orphans: 2; text-indent: 0px; text-transform: none; white-space: normal; widows: 2; word-spacing: 0px; font-size: medium;\"><span class=\"Apple-style-span\" style=\"color: rgb(68, 68, 68); font-family: Arial,Verdana,sans-serif; font-size: 13px; line-height: 20px; text-align: left;\">Example: The letters p-l-a-n-e-t-s spell the word,<span class=\"Apple-converted-space\">\u00a0</span><i>planets</i><span style=\"font-style: normal;\">. From that set of letters, you could make these words: plan, plans, set, ape, apes, net, nets, nest.\u00a0 Those are just a few of the possibilities.<br /></span></span></span>",
           'hHTML': '<a href="http://wwww.cs.unc.edu/~gb" rel="me">Gary</a>',
           'iHTML': '''<a href="javascript:alert('gotcha')">Bad</a>''',
         }
    for key in sorted(t1.keys()):
        print key, t1[key]
    st1 = sanitize(t1)
    for key in sorted(st1.keys()):
        print key, st1[key]

