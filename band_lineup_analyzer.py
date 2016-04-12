import urllib
import re
import xml
from string import maketrans
from enum import Enum
from bs4 import BeautifulSoup
import HTMLParser
import simplejson
import cStringIO
import urllib2

url = "https://en.wikipedia.org/wiki/{0}"

band="Metallica"

tokens = []

sentences = []

#~ url = url.format(band.replace(" ", "_"))

tags = ["function", "name", "date", "formation", "meta", "undef", "tlinker", "clinker"]

function_tags=["sing", "bass", "guitar", "vocal", "drum", "percussion"]

formation_tags=["comprise", "form", "lineup", "found", "join", "hir", "depart", "member"]

nodes={}

temporal_link=["in", "since", "when"]

conjonction=["but", "or", "and", "so"]


for t in tags:
    nodes[t]=[]

class Node:
    
    def __init__(self, t, v, relation_nodes=[]):
        self.ntype=t
        self.value=v
        self.relation_nodes=relation_nodes
    
    def __str__(self):
        if self.ntype=="undef":
            return  "{0}({1})".format("?", self.value)
        if self.ntype=="meta":
            out = "meta {0}\n".format(self.value)
            for r in self.relation_nodes:
                out += r.__repr__() + "\n"
            return out
        return "{0}({1})".format(self.ntype, self.value)
    
    def __repr__(self):
        return self.__str__()

class FST_STATUS(Enum):
    ready=1
    running=2
    fail=3
    success=4

class FST_State:
    
    def __init__(self, tag, children=[], confidence_decay=1):
        self.tag=tag
        self.children = children
        self.cdecay = confidence_decay
    
    
    def add_children(self, children):
        self.children.append(children)
    
    def add_child(self, child):
        self.children.append(child)
    



class FST:
    
    def __init__(self, start_states, end_states):
        if len(end_states)==0 or len(start_states)==0:
            exit(1)
        self.state = None
        self.status = FST_STATUS.ready
        self.sstates = start_states
        self.estates = end_states
        self.confidence=100
        self.seq={}
        
    
    def process(self, node):
        if self.state == FST_STATUS.success or self.state == FST_STATUS.fail:
            self.reset()
        if self.state is None and self.status == FST_STATUS.ready:
            for s in self.sstates:
                print s.tag
                if node.ntype == s.tag:
                    self.state = s
                    self.status = FST_STATUS.running
                    self.seq[s] = []
                    self.seq[s].append(node)
                    print "Init: {0} {1}".format(s.tag, s.cdecay)
                    return self.status
            for s in self.sstates:
                if s.tag == "epsilon":
                    self.state = s
                    self.status = FST_STATUS.running
                    self.seq[s] = []
                    self.seq[s].append(node)
                    print "Init: {0} {1}".format(s.tag, s.cdecay)
                    return self.status
            self.status=FST_STATUS.fail
            return self.status
        print self.state.tag
        for c in self.state.children:
            if c.tag == node.ntype:
                if c not in self.seq:
                    self.seq[c]=[]
                self.seq[c].append(node)
                self.state=c
                print "{0} {1}".format(c.tag, c.cdecay)
                self.confidence *= c.cdecay
                if c in self.estates:
                    self.status = FST_STATUS.success
                return self.status
        # deal with epsilon transitions last
        for c in self.state.children:
            if c.tag=="epsilon":
                if c not in self.seq:
                    self.seq[c]=[]
                self.seq[c].append(node)
                self.state=c
                print "{0} {1}".format(c.tag, c.cdecay)
                self.confidence *= c.cdecay
                if c in self.estates:
                    self.status = FST_STATUS.success
                return self.status
        self.status = FST_STATUS.fail
        return self.status
            
    
    def reset(self):
        self.state = None
        self.status = FST_STATUS.ready
        self.seq={}
        self.confidence=100
    


fst_unk = FST_State("undef", [], 1)
fst_conj = FST_State("clinker", [], 1)
fst_unk.add_child(fst_unk)
fst_function = FST_State("function", [], 1)
fst_unk.add_child(fst_function)
fst_conj.add_child(fst_function)
fst_name=FST_State("name", [], 1)
fst_function.add_child(fst_name)
fst_unk1 = FST_State("undef", [fst_name], 0.9)
fst_unk2 = FST_State("undef", [fst_unk1], 0.9)
fst_unk1.add_child(fst_unk2)


fst_function.add_child(fst_unk1)
for c in fst_function.children:
    print "child {0}".format(c.tag)

fst_function = FST([fst_unk, fst_conj], [fst_name])

n1 = Node("undef", "?")
n2 = Node("function", "guitar")
n22 = Node("undef", "?")
n3 = Node("name", "Bibi")
ln = [n1, n2, n22, n3]

for l in ln:
    s = fst_function.process(l)
    if s == FST_STATUS.success:
        print "match!"
        print fst_function.confidence
    elif s == FST_STATUS.fail:
        print "fail"
        break
    print s
    
print "\n\n"

class LinkFinder:
    
    def __init__(self, strlink):
        self.idx=0
        self.sstr = strlink
    
    
    def __iter__(self):
        self.idx=0
        return self
    
    
    def next(self):
        if self.idx >= len(self.sstr) or self.idx==-1:
            self.idx=0
            raise StopIteration
        else:
            i = self.sstr.find("<a", self.idx)
            if i == -1:
                self.idx=0
                raise StopIteration
            self.idx=i
            f = self.sstr.find("</a", self.idx, len(self.sstr))
            if f == -1:
                print "could not find ending link tag"
                raise ValueError
            
            fa = self.sstr.find(">", self.idx, f-1)
            if fa == -1:
                print "could not find closing link tag"
                raise ValueError
            self.idx = self.sstr.find(">", f)
            return self.sstr[fa+1:f]


def strip_tags(value):
    out =""
    tog=0
    prev=-1
    for i in range(len(value)):
        if value[i] == "<":
            tog=1
            continue
        
        elif value[i]==">" and tog==1:
            tog=0
            continue
        if tog==0:
            out += value[i]
            
    return out

def strip_whites(value):
    return re.sub(r'(\t+|\n+)', ' ', value)
    
def error(w1, w2):
    if w1.find(w2) >=0:
        return 0
    return float(levenshtein_distance(w1, len(w1)-1, w2, len(w2)-1, {}))/(len(w1)+len(w2))

def levenshtein_distance(w1, i, w2, j, d={}):
    if i==0:
        return j
    elif j==0:
        return i
    a = 0 if w1[i]==w2[j] else 1
    if (i-1,j) not in d:
        d[(i-1,j)]=levenshtein_distance(w1, i-1, w2, j, d)
    if (i,j-1) not in d:
        d[(i,j-1)]=levenshtein_distance(w1, i, w2, j-1, d)
    if (i-1,j-1) not in d:
        d[(i-1,j-1)]=levenshtein_distance(w1, i-1, w2, j-1, d)
    l1 = d[(i-1,j)]+1
    l2 = d[(i,j-1)]+1
    l3 = d[(i-1,j-1)]+a
    
    l=[l1, l2, l3]
    return min(l)
    

def belongs_tag_class(tag_class, w):
    for w2 in tag_class:
        e = error(w, w2)
        #~ print "error({0}, {1}) = {2}".format(w, w2, e)
        if e < 0.1:
            return (w2,e)
    return None


def is_name(w1, w2):
    return w1[0].isupper() and w2[0].isupper()

def is_name_s(w):
    wl=w.split(" ")
    if len(wl) != 2:
        return False
    return is_name(wl[0], wl[1])



def find_node(w, w2=None):
    if w in conjonction:
        return Node("clinker", w)
    
    if w in temporal_link:
        return Node("tlinker", w)
    
    t = belongs_tag_class(function_tags, w)
    if t is not None:
        return Node("function", w)
    t = belongs_tag_class(formation_tags, w)
    if t is not None:
        return Node("formation", w)
    if w2 is not None:
        if is_name(w, w2):
            return Node("name", "{0} {1}".format(w, w2))
    if w[0].isupper():
        for t in tokens:
            e = error(t, w)
            #~ print "{0} {1}".format(t, e)
            if e < 0.1:
                if is_name_s(t):
                    a, b = t.split(" ")
                    return Node("name", "{0} {1}".format(a, b))
    if re.match(r"^[0-9]{4}$", w):
        return Node("date", w)
    
    return Node("undef", w)

print url.format(band+"_(band)")
page = urllib.urlopen(url.format(band+"_(band)")).read()
#~ page = open("{0}.html".format(band), "r").read()

f = open("{0}.html".format(band), "w+")
f.write(page)
f.close()
#~ print page
i = page.index("<b>{0}</b>".format(band))

fin = page.index('<div id="toc" class="toc">', i)


text = page[i:fin]

strip = strip_tags(text)
sentences = strip.split(".")

linkit = LinkFinder(text)

for link in linkit:
    if link.find("[")>=0:
        continue
    if link.find("<")>=0:
        continue
    tokens.append(link)
    print link



#~ belongs_tag_class(formation_tags, "hiring")
i=0
metas=[]
for s in sentences:
    s = s.strip()
    print s
    wds = s.split(" ")
    model=""
    idx=0
    trantab = maketrans("", "")
    ln=[]
    while idx < len(wds):
        w=wds[idx]
        w=w.translate(trantab, ",")
        print w
        if idx < len(wds)-1:
            w2 = wds[idx+1].translate(trantab, ",")
            n = find_node(w, w2)
            if n.ntype=="name":
                if is_name(w, w2):
                    idx+=1
            ln.append(n)
        else:
            n = find_node(w, None)
        idx+=1
        
        st = fst_function.process(n)
        if st == FST_STATUS.success:
            print "match!"
            print fst_function.confidence
            m = Node("meta", "play", [])
            for se in fst_function.seq:
                if se.tag != "undef" and se.tag != "clinker" and se.tag != "tlinker":
                    for nd in fst_function.seq[se]:
                        m.relation_nodes.append(nd)
            metas.append(m)
            fst_function.reset()
        elif st == FST_STATUS.fail:
            fst_function.reset()
            print "fail"
    
    print " ".join(str(l) for l in ln)
    if i > 3:
        break
    i+=1
print "metas"
print metas

block = u"""<div class="block">
        <div style="float: left; height: 100%;">
         <div class='circular picture' style='background: url({0}) no-repeat;'></div>
        </div>
   
        <div class="info">
            <div class="inside-info" style="vertical-align: middle;">
            <p style="display: block" class="name">{1}</p>
            <p style="display: block" class="name">{2}</p>
            </div>
        </div>
    
    </div>"""

with open("site/main.html", "r+") as hfile:
    soup = BeautifulSoup(hfile.read(), 'html.parser')
    soup.body.string=""
    for m in metas:
        if m.value=="play":
            for t in m.relation_nodes:
                if t.ntype=="name":
                    try:
                        fetcher = urllib2.build_opener()
                        searchTerm = t.value.replace(" ", "_")
                        print searchTerm
                        searchUrl = "https://en.wikipedia.org/wiki/{0}".format(searchTerm)
                        f = fetcher.open(searchUrl)
                        soup_name = BeautifulSoup(f, 'html.parser')
                        a = soup_name.select(".image")[0]
                        imageUrl =  "https:{0}".format(a.select("img")[0]["src"])
                    except IndexError:
                        imageUrl=""
                    name=t.value
                elif t.ntype=="function":
                    function = t.value
            soup.body.string += block.format(imageUrl, name, function)
    hfile.seek(0)
    #~ print HTMLParser.HTMLParser().unescape(soup.prettify())
    hfile.write(HTMLParser.HTMLParser().unescape(soup.prettify()))
    hfile.truncate()
        
