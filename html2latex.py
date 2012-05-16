
#
# Convert html with special css classes to Customized LaTeX environments.
#
import sys
import os
import re

from lxml import etree
from jinja2 import Template, FileSystemLoader, Environment
from jinja2.exceptions import TemplateNotFound

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

    # delegate the work to classes handling special cases
    if element.tag =='div':
        if element.attrib['class'] == 'keyconcepts':
            myElement = div_keyconcepts(element)
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



class div_keyconcepts(html_element):
    def __init__(self, element):
        u'''Convert the div.keyconcepts element to LaTeX

>>> from lxml import etree
>>> root = etree.HTML('<div class="keyconcepts"></div>')
>>> delegate(root[0][0])
u'\\n\\\\keyconcepts{}\\n'
'''
        html_element.__init__(self, element)
        self.template = texenv.get_template('keyconcepts.tex')


if __name__ == "__main__":
    root = etree.HTML(open(sys.argv[1], 'r').read())
    body = root.find('.//body')
    
    content = ''.join([delegate(element) for element in body])
    print content

