# Put doctests in here
def test():
    r'''

    >>> from lxml import etree
    >>> from html2latex import *
    >>> root = etree.HTML('<h1>Title</h1>')
    >>> print delegate(root[0][0])
    \chapter{Title}



    >>> from lxml import etree
    >>> from html2latex import *
    >>> root = etree.HTML('<div class="keyconcepts"></div>')
    >>> delegate(root[0][0])
    u'\n\\keyconcepts{}\n'

    '''
    pass
