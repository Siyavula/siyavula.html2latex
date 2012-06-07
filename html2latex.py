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
from PIL import Image

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
            myElement = div_keyconcepts(element)
        
        elif element.attrib['class'] == 'keyquestions':
            myElement = div_keyquestions(element)
        
        elif element.attrib['class'] == 'investigation':
            myElement = div_investigation(element)
        
        elif element.attrib['class'] == 'activity':
            myElement = div_activity(element)
        
        elif element.attrib['class'] == 'newwords':
            myElement = div_newwords(element)

        elif element.attrib['class'] == 'questions':
            myElement = div_questions(element)

        elif 'investigation-' in element.attrib['class']:
            myElement = div_investigation_header(element)
        
        elif 'activity-' in element.attrib['class']:
            myElement = div_investigation_header(element)
        

        else:
            myElement = html_element(element)

    elif element.tag == 'table':
        myElement = table(element)

    elif element.tag == 'img':
        myElement = img(element)
    
    elif element.tag == 'h1':
        if 'class' not in element.attrib:
            element.attrib['class'] = ''

        if element.attrib['class'] == 'part':
            myElement = part(element)
        elif element.attrib['class'] == 'chapter':
            myElement = html_element(element)

    #
    # cnxmlplus tags 
    #

    elif element.tag == 'section':
        myElement = section(element)
    elif element.tag == '{http://www.w3.org/1998/Math/MathML}math':
        myElement = math(element)
    elif element.tag == 'worked_example':
        myElement = worked_example(element)
    elif element.tag == 'workstep':
        myElement = workstep(element)
    elif element.tag == 'list':
        myElement = listelement(element)
    elif element.tag == 'definition':
        myElement = definition(element)
    elif element.tag == 'figure':
        myElement = figure(element)
    elif element.tag == 'exercises':
        myElement = exercises(element)
    elif element.tag == 'exercise':
        myElement = exercise(element)
    elif element.tag == 'latex':
        myElement = latex(element)

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
        self.content['tail'] = self.element.tail.strip() if self.element.tail is not None else ''
 
        self.content['tag'] = self.element.tag

        try:
            self.content['class'] = self.element.attrib['class']
        except KeyError:
            self.content['class'] = ''
        
        try:
            self.template = texenv.get_template(self.element.tag + '.tex')
        except TemplateNotFound:
            self.template = texenv.get_template('not_implemented.tex')
        except TypeError:
            self.template = texenv.get_template('error.tex')

        for a in self.element.attrib:
            self.content[a] = self.element.attrib[a]

        #escape latex characters
        self.content['text'] = escape_latex(self.content['text'])
        self.content['tail'] = escape_latex(self.content['tail'])

        self.render_children()

        
    def render(self):
        return self.template.render(content=self.content)

    def render_children(self):
        for child in self.element:
            self.content['text'] += delegate(child)



class math(html_element):
    def __init__(self, element):
        html_element.__init__(self, element)
        # call the xslt transform to transform mathml to latex.
        xslt = etree.parse(os.path.dirname(os.path.realpath(__file__)) + '/templates/xslt/mmltex.xsl')
        transform = etree.XSLT(xslt)
        tex = transform(element)
        tex = unicode(tex).replace('$', '')
        self.template = texenv.get_template('math.tex')
        text = escape_latex(tex) 
        # fix some things
        text = text.replace('\&', '&')
       
        # fix the autosizing bracket issue. Must have matching brackets in every math environment.
        # If they don't match, remove the autosizing \left and \right
        if text.count(r'\left') != text.count(r'\right'):
            text = text.replace(r'\left', '').replace(r'\right', '')

        # mathml tables with display

        self.content['text'] = text        

class latex(html_element):
    def __init__(self, element):
        html_element.__init__(self, element)
        if 'begin{align' in self.content['text']:
            self.content['text'] = self.content['text'].replace('$', '')
       


class worked_example(html_element):
    def __init__(self, element):
        title = element.find('.//title')
        titletext = delegate(title)
        element.remove(title)
        html_element.__init__(self, element)
        self.template = texenv.get_template('worked_example.tex')
        self.content['title'] = titletext


class definition(html_element):
    def __init__(self, element):
        term = element.find('.//term')
        termtext = delegate(term)
        element.remove(term)
        meaning = element.find('.//meaning')
        meaningtext = delegate(meaning)
        element.remove(meaning)
        html_element.__init__(self, element)
        self.template = texenv.get_template('definition.tex')
        self.content['term'] = termtext
        self.content['meaning'] = meaningtext

class figure(html_element):
    def __init__(self, element):
        # basically a floating environment
        type_element = element.find('.//type')
        typetext = type_element.text 
        element.remove(type_element)
        html_element.__init__(self, element)
        self.template = texenv.get_template('figure.tex')
        self.content['type'] = typetext



class exercise(html_element):
    def __init__(self, element):
        title = element.find('.//title')
        titletext = delegate(title)
        element.remove(title)
        html_element.__init__(self, element)
        self.template = texenv.get_template('exercise.tex')
        self.content['title'] = titletext

class exercises(html_element):
    def __init__(self, element):
        title = element.find('.//title')
        titletext = delegate(title)
        element.remove(title)

        # change the entry children to ex_entry, they conflict with tables
        for e in element.findall('.//entry'):
            e.tag = 'ex_entry'

        html_element.__init__(self, element)
        self.template = texenv.get_template('exercise.tex')
        self.content['title'] = titletext


class workstep(html_element):
    def __init__(self, element):
        title = element.find('.//title')
        titletext = delegate(title)
        element.remove(title)
        html_element.__init__(self, element)
        self.template = texenv.get_template('workstep.tex')
        self.content['title'] = titletext

class listelement(html_element):
    def __init__(self, element):
        html_element.__init__(self, element)
        try:
            list_type = element.attrib['list-type']
        except KeyError:
            list_type = 'bulleted'

        if list_type == 'enumerated':
            self.template = texenv.get_template('enumerated.tex')
        elif list_type == 'bulleted':
            self.template = texenv.get_template('bulleted.tex')
        else:
            self.template = texenv.get_template('not_implemented.tex')



class section(html_element):
    def __init__(self, element):
        title = element.find('.//title')
        titletext = delegate(title)
        element.remove(title)
        html_element.__init__(self, element)
        try:
            self.template = texenv.get_template('%s.tex'%element.attrib['type'])
        except KeyError:
            # We're likely inside an activity or similar
            self.template = texenv.get_template('generic_section.tex')

        self.content['title'] = titletext


class part(html_element):
    def __init__(self, element):
        r'''Convert the h1.part element to LaTeX

'''
        html_element.__init__(self, element)
        self.template = texenv.get_template('part.tex')



class table(html_element):
    def __init__(self, element):
        html_element.__init__(self, element)
        # check whether its html or cnxml table
        if element.find('.//tr'):
            # html table
            # must get number of columns
            ncols = len(element.find('.//tr').findall('.//td')) + 1
            self.content['ncols'] = ncols + 1
            self.content['cols'] = '|' + '|'.join(['c' for i in range(int(ncols))]) + '|'
        else:
            #cnxml table
            if 'latex-column-spec' in element.attrib:
                self.content['columnspec'] = element.attrib['latex-column-spec']
            elif element.find('.//tgroup') is not None:
                tgroup = element.find('.//tgroup')
                if 'cols' in tgroup.attrib['cols']:
                    ncols = int(tgroup.attrib['cols'])
                else:
                    ncols = None

            # remove the last & in the row.
            self.content['text'] = self.content['text'].replace(r'& \\', r' \\')


        
        self.template = texenv.get_template('table.tex')

class img(html_element):
    def __init__(self, element):
        image_types = {'JPEG':'.jpg', 'PNG':'.png'}
        html_element.__init__(self, element)
        # get the link to the image and download it.
        src = element.attrib['src']
        name = src.rpartition('/')[-1]
        self.content['imagename'] = name

        downloaded = any([name in imname for imname in os.listdir(os.curdir + '/images')])

        if not downloaded: 
            img = urllib.urlopen(src).read()
            open('images/%s'%name, 'wb').write(img)
            # now open the file and read the mimetpye
            try:
                im = Image.open('images/%s'%name)
                extension = image_types[im.format]
                os.system('mv images/%s images/%s'%(name, name+extension))
                # update the image name that the template will see
                self.content['imagename'] = name + extension
            except:
                print "Cannot open image: %s"%name
            



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


class div_keyquestions(html_element):
    def __init__(self, element):
        r'''convert the div.keyquestions element to latex

'''
        html_element.__init__(self, element)
        self.template = texenv.get_template('keyquestions.tex')


class div_questions(html_element):
    def __init__(self, element):
        r'''convert the div.questions element to latex

'''
        html_element.__init__(self, element)
        self.template = texenv.get_template('questions.tex')

class div_investigation(html_element):
    def __init__(self, element):
        r'''Convert the div.investigation element to LaTeX

'''
        html_element.__init__(self, element)
        self.template = texenv.get_template('investigation.tex')

class div_newwords(html_element):
    def __init__(self, element):
        r'''Convert the div.newwords element to LaTeX

'''
        html_element.__init__(self, element)
        self.template = texenv.get_template('newwords.tex')


class div_activity(html_element):
    def __init__(self, element):
        r'''Convert the div.activity element to LaTeX

'''
        # we need to prepare the title
        title_element = element.find('.//div[@class="activity-title"]')
        # get all the title text and remove from DOM
        title = title_element.text + ''.join([t.text for t in title_element.findall('.//')])
        element.remove(title_element)

        html_element.__init__(self, element)
        self.content['title'] = title 
        self.template = texenv.get_template('activity.tex')


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

def escape_latex(text):
    '''Escape some latex special characters'''
#    text = text.replace('&', '\&')
#   text = text.replace('_', '\_')
    text = text.replace('%', '\%')
    return text


def setup_texenv(loader):
    texenv = Environment(loader=loader)
    texenv.block_start_string = '((*'
    texenv.block_end_string = '*))'
    texenv.variable_start_string = '((('
    texenv.variable_end_string = ')))'
    texenv.comment_start_string = '((='
    texenv.comment_end_string = '=))'
    texenv.filters['escape_tex'] = escape_tex

    return texenv


if __name__ == "__main__":

    extension = sys.argv[1].rsplit('.')[-1]

    if extension == 'html':
        root = etree.HTML(open(sys.argv[1], 'r').read())
        loader = FileSystemLoader(os.path.dirname(os.path.realpath(__file__)) + '/templates/html')
        texenv = setup_texenv(loader)
        body = root.find('.//body')
    elif extension == 'cnxmlplus':
        root = etree.XML(open(sys.argv[1], 'r').read())
        loader = FileSystemLoader(os.path.dirname(os.path.realpath(__file__)) + '/templates/cnxmlplus')
        texenv = setup_texenv(loader)
        body = root.find('.//content')
    else:
        print 'Unknown extension on input file type!!'
        sys.exit()



    content = ''.join([delegate(element) for element in body])

    main_template = texenv.get_template('maindoc.tex')

    print unicode(unescape(main_template.render(content=content))).encode('utf-8')
    

