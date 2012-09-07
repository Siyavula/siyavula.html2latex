from plasTeX.Base import Environment, Command
#
# Some definitions for the environments we used in latex coming from community.siyavula.com html.
#
#
class activity(Environment):
    args = "title:str text"

class definition(Environment):
    pass

class newwords(Command):
    args = "text:str"

class keyconcepts(Command):
    pass

class visit(Environment):
    pass

class includegraphics(Command):
    args = "[options:str] src"
