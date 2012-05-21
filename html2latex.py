# -*- coding: utf-8 -*-
#
# Convert html with special css classes to Customized LaTeX environments.
#
import sys
import os
import re, htmlentitydefs
import urllib

from lxml import etree
from jinja2 import Template, FileSystemLoader, Environment
from jinja2.exceptions import TemplateNotFound
import PIL

# Some boilerplate to use jinja more elegantly with LaTeX
# http://flask.pocoo.org/snippets/55/


LATEX_SUBS = (
    (re.compile(r'\\'), r'\\textbackslash'),
    (re.compile(r'([{}_#%&$])'), r'\\\1'),
    (re.compile(r'~'), r'\~{}'),
    (re.compile(r'\^'), r'\^{}'),
    (re.compile(r'"'), r"''"),
    (re.compile(r'\.\.\.+'), r'\\ldots'),
)

def escape_tex(value):
    newval = value
    for pattern, replacement in LATEX_SUBS:
        newval = pattern.sub(replacement, newval)
    return newval

loader = FileSystemLoader(os.path.dirname(os.path.realpath(__file__)) + '/templates/')
texenv = Environment(loader=loader)
texenv.block_start_string = '((*'
texenv.block_end_string = '*))'
texenv.variable_start_string = '((('
texenv.variable_end_string = ')))'
texenv.comment_start_string = '((='
texenv.comment_end_string = '=))'
texenv.filters['escape_tex'] = escape_tex



# Templates for each class here.
def delegate(element):
    '''>>> from lxml import etree
       >>> root = etree.HTML('<h1>Title</h1>')
       >>> print delegate(root[0][0])
       \chapter{Title}'''
    #print '%', element.tag, element.attrib
    # delegate the work to classes handling special cases
    if element.tag == 'div':
        if 'class' not in element.attrib:
            element.attrib['class'] = ''

        if element.attrib['class'] == 'keyconcepts':
            #import pdb; pdb.set_trace()
            myElement = div_keyconcepts(element)
        elif element.attrib['class'] == 'investigation':
            myElement = div_investigation(element)
        elif 'investigation-' in element.attrib['class']:
            myElement = div_investigation_header(element)
        else:
            myElement = html_element(element)

    elif element.tag == 'table':
        myElement = table(element)

    elif element.tag == 'img':
        myElement = img(element)
    else:
        # no special handling required
        myElement = html_element(element)

    return myElement.render()


class html_element(object):
    def __init__(self, element):
        self.element = element
        
        # we make a general dict to store the contents we send to the Jinja templates.
        self.content = {}
        self.content['text'] = self.element.text if self.element.text is not None else ''
        self.content['tail'] = self.element.tail if self.element.tail is not None else ''
 
        self.content['tag'] = self.element.tag

        try:
            self.content['class'] = self.element.attrib['class']
        except KeyError:
            self.content['class'] = ''
        
        try:
            self.template = texenv.get_template(self.element.tag + '.tex')
        except TemplateNotFound:
            self.template = texenv.get_template('not_implemented.tex')

        self.render_children()

        
    def render(self):
        return self.template.render(content=self.content)

    def render_children(self):
        for child in self.element:
            self.content['text'] += delegate(child)


class table(html_element):
    def __init__(self, element):
        html_element.__init__(self, element)
        # must get number of columns
        ncols = len(element.find('.//tr').findall('.//td')) + 1
        self.template = texenv.get_template('table.tex')
        self.content['ncols'] = ncols + 1
        self.content['cols'] = '|' + '|'.join(['c' for i in range(int(ncols))]) 


class img(html_element):
    def __init__(self, element):
        html_element.__init__(self, element)
        # get the link to the image and download it.
        src = element.attrib['src']
        name = src.rpartition('/')[-1]
        self.content['imagename'] = name
        if name not in os.listdir(os.curdir + '/images'):
            img = urllib.urlopen(src).read()
            # get mimetype
            open('images/%s'%name, 'wb').write(img)


class div_keyconcepts(html_element):
    def __init__(self, element):
        r'''Convert the div.keyconcepts element to LaTeX

        >>> from lxml import etree
        >>> root = etree.HTML('<div class="keyconcepts"></div>')
        >>> delegate(root[0][0])
        u'\n\\keyconcepts{}\n'
'''
        html_element.__init__(self, element)
        self.template = texenv.get_template('keyconcepts.tex')


class div_investigation(html_element):
    def __init__(self, element):
        r'''Convert the div.investigation element to LaTeX

'''
        html_element.__init__(self, element)
        self.template = texenv.get_template('investigation.tex')


class div_investigation_header(html_element):
    def __init__(self, element):
        r'''Convert the div.investigation element to LaTeX

'''
        html_element.__init__(self, element)
        self.content['title'] = self.content['class'].split('-')[1]
        self.template = texenv.get_template('investigation_header.tex')



##
# Removes HTML or XML character references and entities from a text string.
#
# @param text The HTML (or XML) source text.
# @return The plain text, as a Unicode string, if necessary.

def unescape(text):
    def fixup(m):
        text = m.group(0)
        if text[:2] == "&#":
            # character reference
            try:
                if text[:3] == "&#x":
                    return unichr(int(text[3:-1], 16))
                else:
                    return unichr(int(text[2:-1]))
            except ValueError:
                pass
        else:
            # named entity
            try:
                text = unichr(htmlentitydefs.name2codepoint[text[1:-1]])
            except KeyError:
                pass
        return text # leave as is
    return re.sub("&#?\w+;", fixup, text)



if __name__ == "__main__":
    root = etree.HTML(open(sys.argv[1], 'r').read())
    body = root.find('.//body')
     
    content = ''.join([delegate(element) for element in body])
    main_template = texenv.get_template('maindoc.tex')
    print unicode(unescape(main_template.render(content=content))).encode('utf-8')
    

