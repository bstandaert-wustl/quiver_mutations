import numpy as np
import copy
import networkx as nx
import matplotlib.pyplot as plt

def flattenList(l):
    return [x for y in l for x in y]


class QuiverWithPotential():

    def __init__(self, graph_obj, potential):
        if isinstance(graph_obj, list): # if graph input is a list of edges
            self.Q1 = graph_obj
            self.incidence_matrix = matrixFromEdges(graph_obj)
        elif isinstance(graph_obj, np.matrix): # if graph input is an incidence matrix
            self.incidence_matrix = graph_obj
            self.Q1 = edgesFromMatrix(graph_obj)
        else:
            self.incidence_matrix = graph_obj.incidence_matrix
            self.Q1 = graph_obj.Q1
        self.Q0 = range(self.incidence_matrix.shape[0])

        self.potential = potential
        self.arrows_with_head = [[] for x in range(len(self.Q0))]
        self.arrows_with_tail = [[] for x in range(len(self.Q0))]
        self.loops_at = [[] for x in range(len(self.Q0))]
        for i, e in enumerate(self.Q1):
            if e[0] != e[1]:
                self.arrows_with_head[e[0]].append((i,e))
                self.arrows_with_tail[e[1]].append((i,e))
            else:
                self.loops_at[e[0]].append((i,e))


    def __repr__(self):
        return "quiver with potential:\nincidence matrix: " \
               +repr(self.incidence_matrix)+"\nedges: " \
               +repr(self.Q1) \
               +"\npotential:"+repr(self.potential)


    def add_edges(self, edge):
        ctr = len(self.Q1)
        for e in edge:
            self.Q1.append(e)
            if e[0] == e[1]:
                self.loops_at[e[0]].append((ctr, [e[0],e[0]]))
            else:
                self.arrows_with_head[e[1]].append((ctr,e))
                self.arrows_with_tail[e[0]].append((ctr,e))
            ctr += 1
        self.incidence_matrix = matrixFromEdges(self.Q1)


    def remove_edges(self, edge):
        # create list of edges to keep
        keep = [i for i in range(len(self.Q1))]
        for e in edge:
            keep[e] = -(e+1)

        self.Q1 = [self.Q1[i] for i in keep if i >= 0]

        k = [x for x in keep if x >= 0]
        new_edge_indices = dict(zip(k, range(len(k))))
        for v in self.Q0:
            self.arrows_with_head[v] = [(new_edge_indices[x[0]], self.Q1[new_edge_indices[x[0]]]) for x in self.arrows_with_head[v] if keep[x[0]]>0]
            self.arrows_with_tail[v] = [(new_edge_indices[x[0]], self.Q1[new_edge_indices[x[0]]]) for x in self.arrows_with_tail[v] if keep[x[0]]>0]
            self.loops_at[v] = [(new_edge_indices[x[0]], self.Q1[new_edge_indices[x[0]]]) for x in self.loops_at[v]]
        self.incidence_matrix = matrixFromEdges(self.Q1)


    def mutate(self, v):
        # first check if there's a loop at v. 
        if len(self.loops_at[v]) > 0:
            print("Error in mutate routine: there's a loop at vertex %d. returning"%v)

        # make a copy of the original quiver to mutate
        QP = copy.deepcopy(self)
    
        # reverse all edges incident to v:
        for (i, e) in self.arrows_with_tail[v] + self.arrows_with_head[v]:
            QP.Q1[i] = self.Q1[i][::-1]
        # update connectivity info for quiver
        QP.arrows_with_head[v] = self.arrows_with_tail[v]
        QP.arrows_with_tail[v] = self.arrows_with_head[v]
    
        delta = []
        shortcuts = {}
        new_edges = []
        edgectr = len(QP.Q1)
        # add 'shortcuts' i->j for all 2-paths(which are then reversed): i->v->j 
        # and keep track of the 3-cycles that are produced (saved in list delta)
        for e1i, e1 in self.arrows_with_head[v]:
            i = self.Q1[e1i][0]
            for e2i, e2 in self.arrows_with_tail[v]:
                j = self.Q1[e2i][1]

                # indexing so we don't add multiedges
                update = 1
                eidx = edgectr
                if [i, j] in QP.Q1:
                    eidx = QP.Q1.index([i,j])
                    update = 0

                # add the shortcut edge
                if update:
                    new_edges.append([i,j])

                # keep track of 3-cycle introduced by adding this edge
                delta.append((1, [eidx,e1i,e2i]))
                shortcuts[tuple(sorted([e1i,e2i]))] = eidx
                edgectr += update
        QP.add_edges(new_edges)

        # update the potential
        wprime = []
        # first replace each 2-path i->v->j with its shortcut i->j
        for (coef, monoid) in self.potential:
            m = []
            for i, x1 in enumerate(monoid[:-1]):
                if (x1, self.Q1[x1]) in self.arrows_with_head[v]:
                    x2 = monoid[i+1]
                    if (x2, self.Q1[x2]) in self.arrows_with_tail[v]:
                        m.append(shortcuts[tuple(sorted([x1, x2]))])
                else:
                    m.append(x1)
            wprime.append((coef,m))

        # remove all 2-cycles that now show up in potential
        to_remove = []
        for coef, monoid in wprime:
            if len(monoid) < 3:
                to_remove.extend(monoid)
        QP.remove_edges(to_remove)

        # add the set of 3-cycles introduced with the shortcuts
        QP.potential = wprime + delta

        # do we now reduce? 
        return QP



class Resolution():

    def __init__(self, e, vertex_positions=None):
        self.edges = e
        triangulation = make_triangulation(self.edges)
        self.triangles = triangulation[0]
        self.edge_to_triangle = triangulation[1]
        self.vertex_positions = vertex_positions


    def update(self, R):
        self.edges = copy.deepcopy(R.edges)
        self.triangles = copy.deepcopy(R.triangles)
        self.edge_to_triangle = copy.deepcopy(R.edge_to_triangle)
        self.vertex_positions = copy.deepcopy(R.vertex_positions)


    def QP(self):
        edges = [(t[i%3], t[(i+j)%3]) for j in [-1,1] for i in range(1, 4) for t in self.triangles]
        p = potential(edges, self.triangles)
        return QuiverWithPotential(edges, p)


    def draw(self, time=0.5, **kwargs):
        # create networkx graph for drawing purposes
        g = nx.Graph()
        g.add_edges_from(self.edges)

        # option for coloring specific edges
        for key in kwargs.keys():
            if 'edge' in key:
                # have to manually match entries of edge_colors since nx reorders edges when it creates a graph
                for e in g.edges:
                    if list(e) in self.edges:
                        i = self.edges.index(list(e))
                    else:
                        i = self.edges.index([e[1],e[0]])
                    g.edges[e][key] = kwargs[key][i]
                kwargs[key] = [x for x in nx.get_edge_attributes(g,key).values()]

        # option for drawing with specified vertex positions
        if self.vertex_positions is not None:
            nx.draw_networkx(g, self.vertex_positions, **kwargs)
        else:
            nx.draw_networkx(g, **kwargs)

        plt.draw()
        plt.pause(time)
        plt.clf()


    def flop_in_sequence(self, edge_sequence, draw=True):
        for edge in edge_sequence:
            R = self.flop(edge)
            edge_colors = ['b' if i != edge else 'r' for i in range(len(self.edges))]
            if draw:
                kw = {'edge_color': edge_colors}
                self.draw(time=.5, **kw)
                R.draw(time=.75, **kw)
            self.update(R)
        return R


    def __repr__(self):
        return "resolution:\n\t%d triangles\n\t"%(len(self.triangles))+repr(self.triangles)


    def flop(self, e):
        # make a copy of self to return: 
        toRet = copy.deepcopy(self)

        # find the two triangles that share edge e
        nbrs = self.edge_to_triangle[e]
        if len(nbrs) < 2:
            print("error in flop: edge %d is on a boundary and cannot be flopped"%e)
            return toRet 
        nbr1,nbr2 = nbrs[:2]

        # get the points p1, p2 'opposite' to edge e
        #    p1-------e[1]
        #    |       /  |
        #    | nbr1 /   |
        #    |     /e   |
        #    |    /     |
        #    |   / nbr2 |
        #    |  /       |
        #   e[0]-------p2
        p1 = [y for x in self.triangles[nbr1] for y in self.edges[x] if y not in self.edges[e]][0]
        p2 = [y for x in self.triangles[nbr2] for y in self.edges[x] if y not in self.edges[e]][0]

        # find the edge indices for e[0]--p2 and e[1]--p1 and other 2 as well.
        e1p1 = [y for y in self.triangles[nbr1] if ((self.edges[e][1] in self.edges[y]) and (y != e))][0]
        e0p1 = [y for y in self.triangles[nbr1] if ((self.edges[e][0] in self.edges[y]) and (y != e))][0]
        e0p2 = [y for y in self.triangles[nbr2] if ((self.edges[e][0] in self.edges[y]) and (y != e))][0]
        e1p2 = [y for y in self.triangles[nbr2] if ((self.edges[e][1] in self.edges[y]) and (y != e))][0]

        # update the triangle edges
        toRet.triangles[nbr1] = [e0p2,e,e0p1]
        toRet.triangles[nbr2] = [e1p2,e,e1p1]
        toRet.edges[e] = [p2, p1]

        # replace the connectivity for edges to triangles
        toRet.edge_to_triangle[e1p1] = [y if y != nbr1 else nbr2 for y in self.edge_to_triangle[e1p1]]
        toRet.edge_to_triangle[e0p2] = [y if y != nbr2 else nbr1 for y in self.edge_to_triangle[e0p2]]

        return toRet


def potential(edges, triangles):
    # build triples. Note: since the triangles' edges aren't necessarily ordered, we need to impose order here.
    triples = [[6*ti + x for x in i] for i in [[1,3,5],[0,2,4]] for ti in range(len(triangles))]
    p = []
    for t in triples:
        t1,h1 = edges[t[0]]
        t2,h2 = edges[t[1]]
        if h1 == t2:
            orderedTriple = t
        else:
            orderedTriple = [t[1],t[0],t[2]]
        p.append([1, orderedTriple])
    return p


def make_triangulation(edges):
    """
        this routine takes a list of edges where each edge is in the format [v1, v2] 
        and creates an edge-to-triangle and triangle-to-edge connectivity structure
        for all triangles that can be formed based on vertex identification. 
    """

    numVerts = len(set(flattenList(edges)))
    nbrs = [set() for x in range(numVerts)] # create a set of edges incident to each vertex (empty at first)
    for i, e in enumerate(edges): # populate the list of edges incident to each vertex
        nbrs[e[0]].add(i)
        nbrs[e[1]].add(i)

    triangles = []
    edge_to_triangle = [[] for i in edges]

    triples = set()
    triangle_ctr = 0
    for edge1, e in enumerate(edges):
        # extract the vertices at ends of edge1
        h,t=e
        # find all of the edges connected to these endpoints
        h_nbrs = nbrs[h]
        t_nbrs = nbrs[t]

        # loop over all edges that connect to one endpoint of edge1
        for edge2 in t_nbrs:
            if edge2 != edge1:
                p0, p1 = edges[edge2] # get the endpoints of neighboring edge
                p = p1 if (p0 == t) else p0

                # if the neighboring edge connects to one of the neighbors
                # of the second endpoint, then we have a triangle.
                e3 = nbrs[p].intersection(h_nbrs)
                if len(e3) > 0:
                    edge3 = e3.pop()

                    # check that the edge triple hasn't already been added
                    st = ",".join([str(x) for x in sorted([edge1,edge2,edge3])])
                    if st not in triples:
                        triangles.append([edge1, edge2, edge3])

                        edge_to_triangle[edge1] += [triangle_ctr]
                        edge_to_triangle[edge2] += [triangle_ctr]
                        edge_to_triangle[edge3] += [triangle_ctr]
                        triples.add(st)
                        triangle_ctr += 1

    return triangles, edge_to_triangle


def path_derivative(potential, arrow):
    to_return = {}
    for (coef,term) in potential:
        if arrow in term:
            i = term.index(arrow)
            new_term = term[i+1:]+term[:i]
            to_return.append((coef, new_term))
    return to_return


def edgesFromMatrix(mat):
    return [[r.index(-1), r.index(1)] for r in np.matrix(mat).transpose().tolist()]


def matrixFromEdges(edges, oriented=True):
    nv = len(set(np.array(edges).flatten()))
    tail = -1 if oriented else 1
    m = np.matrix([[tail if x == e[0] else 1 if x == e[1] else 0 for x in range(nv)] for e in edges]).transpose()
    for i,e in enumerate(edges):
        if e[0] == e[1]:
            m[e[0],e] = 2
    return m



