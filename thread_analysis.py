#!/usr/bin/env python

import plumbum, lxml.html, re, pprint, copy, yaml
from plumbum.cmd import curl, dos2unix, readability, pandoc, tr, less, echo, elinks, pip
from functools import reduce

CURRENT_TERM = '201308'

getter = lambda url: (
  curl['http://www.catalog.gatech.edu'+url] | dos2unix['--d2u'] | pandoc['-r','html','-w','markdown'] | tr['\xa0',' ']
)()

threads = set()
threadclasses = dict()
threadpairs = set()
threadpairclasses = dict()

def details_url(subject,code):
  return 'https://oscar.gatech.edu/pls/bprod/bwckctlg.p_disp_course_detail?cat_term_in={}&subj_code_in={}&crse_numb_in={}'.format(CURRENT_TERM,subject,code)

class Class:
  def __init__(self,hours,tag):
    self.hours = hours
    self.tag = tag
    self.alternatives = list(tag.split(' or '))
    for i in range(len(self.alternatives)):
      if ' and ' in self.alternatives[i]: self.alternatives[i] = list(self.alternatives[i].strip('()').split(' and '))
    self.urlled_alternatives = copy.deepcopy(self.alternatives)
    assert self.urlled_alternatives
    self.urlify(self.urlled_alternatives)
  @classmethod
  def urlify(cls,ell):
    def operate(l):
      for i in range(len(l)):
        if type(l[i]) == str:
          if l[i].split()[0].isupper():
            l[i] = '<a href="{}">{}</a>'.format(details_url(*l[i].split()),l[i])
          else:
            pass
        elif type(l[i]) == type([]):
          l[i] = '<br />'.join(operate(l[i]))
        else:
          raise TypeError('Value "{}" is of type "{}"'.format(l[i],type(l[i])))
      return l
    return operate(ell)
  def __str__(self):
    return '{} hours of {}'.format(self.hours,self.tag)
  def __repr__(self):
    return 'Class({},"{}")'.format(self.hours,self.tag)
  def __hash__(self):
    return str(self).__hash__()
  def __eq__(self,other):
    return str(self) == str(other)
  def __gt__(self,other):
    return self.tag.split()[1] > other.tag.split()[1]

def course_representer(dumper, data):
  return dumper.represent_scalar('!course',str(data))

yaml.add_representer(Class, course_representer)

# parse
for url,text in ({link:getter(link) for element, attribute, link, pos in lxml.html.document_fromstring(curl('http://www.catalog.gatech.edu/colleges/coc/ugrad/comsci/threads.php')).iterlinks() if re.search(r'/threads/degreq/.*[^2]\.php$',link)}).items():
  text = text.split('\nBachelor of Science in Computer Science THREAD: ')[1].lstrip().split('\n  TOTAL:   ')[0]
  lines = text.splitlines()
  assert len(lines)
  name = lines[0].upper()
  pair = name.split(' & ')
  threads |= set(pair)
  threadpairs.add(frozenset(pair))
  columns = lines[4]
  #pprint.pprint(lines[5])
  format = lambda line: ('{:<'+str(len(columns))+'}').format(line)
  columns_pattern = re.sub(r' (\.+)',lambda match: ' ({})'.format(match.group(1)),re.sub(r'-','.',columns))
  requirements = map(lambda line: map(lambda col:col.strip() or '--',re.match(columns_pattern,format(line)).groups()), filter(lambda s: s.startswith('  '),lines[5:]))
  threadpairclasses[frozenset(pair)] = frozenset(Class(req[1],req[2]) for req in map(list,requirements))
  #(echo[name+'\n'+pprint.pformat(threadpairclasses[frozenset(pair)])] | less) & plumbum.FG


U = lambda: reduce(lambda a,b:a.union(b),(classlist for classlist in threadpairclasses.values()))

# distill each thread from its pairings
for thread in list(threads):
  threadclasses[thread] = U()
  for pair in list(threadpairs):
    if thread in pair:
      #pprint.pprint(pair)
      threadclasses[thread] &= threadpairclasses[pair]

# separate the threads from one another
commons = reduce(lambda a,b: a.intersection(b),(classlist for classlist in threadclasses.values()))
for thread in threadclasses.keys():
  threadclasses[thread] = sorted(list(threadclasses[thread] - commons))
commons = sorted(list(commons))
## this way of doing it seems not to work whereas the above "dumber" way does; quite mysterious
#finalthreadclasses = {}
#for thread in list(threads):
#  finalthreadclasses[thread] = threadclasses[thread]
#  for other_thread in list(threads):
#    if thread != other_thread:
#      finalthreadclasses[thread] -= threadclasses[other_thread]

#print(yaml.dump(threadclasses, default_flow_style=False))

from lxml.html import builder as E

report_page = E.HTML(
  E.HEAD(E.TITLE('BSCS Threads Analysis')),
  E.BODY(
    E.H1('BSCS Threads Analysis'),
    E.H3('Common classes'),
    E.TABLE(
      *[E.TR(E.TD(cls.hours),*[E.TD(lxml.html.fromstring(req)) for req in cls.urlled_alternatives]) for cls in commons]
    ,border="1"),
    *[E.DIV(E.H3(thread), E.TABLE(
      *[E.TR(E.TD(cls.hours),*[E.TD(lxml.html.fromstring(req)) for req in cls.urlled_alternatives]) for cls in threadclasses[thread]]
,border="1"
    )) for thread in list(threads)]
  )
)

# TODO: use gtmob.gatech.edu to add course-description tooltips to the report

(pip['-Ii','firefox','-.html'] << lxml.html.tostring(report_page))()

